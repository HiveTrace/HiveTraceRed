"""
Base class for web-based model implementations using Playwright browser automation.

This module provides a foundation for models that interact with AI chat interfaces
through browser automation when no official API is available.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import AsyncGenerator, Dict, List, Optional, Tuple, Union

import asyncio

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)
from tqdm import tqdm

from hivetracered.models.base_model import Model

try:
    import nest_asyncio

    nest_asyncio.apply()
    _NEST_ASYNCIO_AVAILABLE = True
except ImportError:
    _NEST_ASYNCIO_AVAILABLE = False


class WebModel(Model):
    """
    Abstract base class for web-based model implementations using Playwright.

    Subclasses must implement:
    - `_send_message_and_get_response()`: how to submit a message and extract the response.

    Subclasses can optionally override:
    - `_setup_context_and_page()`: custom context/page initialization (login, navigation, etc).
    - `_create_browser()`: custom browser launch settings (args, proxy, browser type).
    """

    def __init__(
        self,
        model: str,
        max_concurrency: int = 1,
        headless: bool = False,
        wait_timeout: int = 30,
        response_wait_time: int = 60,
        stability_check_time: float = 2.0,
        **kwargs,
    ):
        self.model_name = model

        self.max_concurrency = max_concurrency
        self.batch_size = max_concurrency  # backward compatibility with older code

        self.headless = headless
        self.wait_timeout = wait_timeout
        self.response_wait_time = response_wait_time
        self.stability_check_time = stability_check_time
        self.kwargs = kwargs or {}

        self._initialized = False
        self._closing = False

        self.playwright = None
        self.browser: Optional[Browser] = None
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def _initialize_browser(self) -> None:
        if self._initialized:
            return

        self.playwright = await async_playwright().start()
        self.browser = await self._create_browser()
        self._semaphore = asyncio.Semaphore(self.max_concurrency)

        self._initialized = True

    async def _create_browser(self) -> Browser:
        if self.playwright is None:
            raise RuntimeError("Playwright is not initialized.")

        return await self.playwright.chromium.launch(headless=self.headless)

    async def _setup_context_and_page(self) -> Tuple[BrowserContext, Page]:
        """
        Create and configure a (context, page) pair.
        """
        if self.browser is None:
            raise RuntimeError("Browser is not initialized.")

        # Default behavior: create a fresh context per request to isolate cookies/storage.
        new_context_kwargs: dict = {
            "storage_state": None,
            "ignore_https_errors": False,
            "accept_downloads": False,
            "locale": "en-US",
            "timezone_id": "America/New_York",
        }

        user_agent = getattr(self, "user_agent", None)
        if user_agent:
            new_context_kwargs["user_agent"] = user_agent

        context = await self.browser.new_context(**new_context_kwargs)
        page = await context.new_page()
        await page.goto(self.target_url, wait_until='networkidle')

        # Handle any initial dialogs (consent, popups, etc.)
        await self._handle_initial_dialogs(page)

        return context, page

    async def _handle_initial_dialogs(self, page: Page) -> None:
        """
        Handle initial dialogs like consent popups, welcome screens, etc.

        Override in subclasses to handle site-specific dialogs.

        Args:
            page: Playwright page object (currently unused in base implementation)
        """
        pass

    def _prompt_to_message(self, prompt: Union[str, List[Dict[str, str]]]) -> str:
        if isinstance(prompt, list):
            return prompt[-1].get("content", "") if prompt else ""
        return prompt

    @abstractmethod
    async def _send_message_and_get_response(self, page: Page, message: str) -> str:
        raise NotImplementedError

    async def _process_single_prompt(
        self, page: Page, prompt: Union[str, List[Dict[str, str]]]
    ) -> dict:
        message = self._prompt_to_message(prompt)
        try:
            response_text = await self._send_message_and_get_response(page, message)
            return {"content": response_text}
        except Exception as exc:
            return {"content": "", "error": str(exc), "error_type": type(exc).__name__}

    async def _run_in_new_context(self, prompt: Union[str, List[Dict[str, str]]]) -> dict:
        """
        Run a prompt in a new (context, page) pair and dispose it afterwards.

        This ensures strict isolation between requests (no cookies/localStorage carryover).
        """
        await self._initialize_browser()
        if self._semaphore is None:
            raise RuntimeError("Concurrency semaphore is not initialized.")

        async with self._semaphore:
            context: Optional[BrowserContext] = None
            page: Optional[Page] = None
            try:
                context, page = await self._setup_context_and_page()
                return await self._process_single_prompt(page, prompt)
            finally:
                if page is not None:
                    try:
                        await page.close()
                    except Exception:
                        pass
                if context is not None:
                    try:
                        await context.close()
                    except Exception:
                        pass

    async def ainvoke(self, prompt: Union[str, List[Dict[str, str]]]) -> dict:
        return await self._run_in_new_context(prompt)

    def invoke(self, prompt: Union[str, List[Dict[str, str]]]) -> dict:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                if not _NEST_ASYNCIO_AVAILABLE:
                    raise RuntimeError(
                        "invoke() cannot run inside an active event loop without nest_asyncio; "
                        "use await ainvoke() instead."
                    )
                return loop.run_until_complete(self.ainvoke(prompt))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.ainvoke(prompt))

    async def abatch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> List[dict]:
        tasks = [self._run_in_new_context(prompt) for prompt in prompts]
        return await asyncio.gather(*tasks)

    def batch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> List[dict]:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                if not _NEST_ASYNCIO_AVAILABLE:
                    raise RuntimeError(
                        "batch() cannot run inside an active event loop without nest_asyncio; "
                        "use await abatch() instead."
                    )
                return loop.run_until_complete(self.abatch(prompts))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.abatch(prompts))

    async def stream_abatch(
        self, prompts: List[Union[str, List[Dict[str, str]]]]
    ) -> AsyncGenerator[dict, None]:
        await self._initialize_browser()
        if self._semaphore is None:
            raise RuntimeError("Concurrency semaphore is not initialized.")

        async def sem_task(
            idx: int, prompt: Union[str, List[Dict[str, str]]]
        ) -> Tuple[int, dict]:
            result = await self._run_in_new_context(prompt)
            return idx, result

        tasks = [asyncio.create_task(sem_task(i, p)) for i, p in enumerate(prompts)]
        total_tasks = len(tasks)
        results: Dict[int, dict] = {}
        cur_idx = 0

        with tqdm(
            total=total_tasks,
            desc=f"Processing requests with {self.model_name}",
            unit="request",
        ) as progress_bar:
            for task in asyncio.as_completed(tasks):
                idx, result = await task
                progress_bar.update(1)
                results[idx] = result
                while cur_idx in results:
                    yield results.pop(cur_idx)
                    cur_idx += 1

    async def _wait_for_stable_response(
        self,
        page: Page,
        selector: str,
        timeout: Optional[int] = None,
        stable_time: Optional[float] = None,
        fallback_to_last: bool = True,
    ) -> str:
        """
        Wait until the matched element(s) text content stops changing.

        Useful for streaming UIs where the assistant response is progressively rendered.

        Args:
            page: Playwright page object
            selector: CSS selector for response element(s)
            timeout: Maximum time to wait in seconds
            stable_time: Time content must be stable to consider complete
            fallback_to_last: If True, return last element's text on timeout/error

        Returns:
            Response text content

        Raises:
            RuntimeError: If no response found and fallback_to_last is False
        """
        timeout = self.response_wait_time if timeout is None else timeout
        stable_time = self.stability_check_time if stable_time is None else stable_time

        start_time = asyncio.get_event_loop().time()
        last_content = None
        last_change_time = start_time

        while True:
            now = asyncio.get_event_loop().time()
            if now - start_time > timeout:
                if fallback_to_last and last_content:
                    return last_content
                # Try fallback to last element if available
                if fallback_to_last:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            return await elements[-1].inner_text()
                    except Exception:
                        pass
                if last_content:
                    return last_content
                raise RuntimeError(f"No response received: timeout waiting for {selector}")

            try:
                elements = await page.locator(selector).all()
                if elements:
                    current_content = await elements[-1].inner_text()
                    if current_content != last_content:
                        last_content = current_content
                        last_change_time = now
                    elif now - last_change_time >= stable_time:
                        return current_content
            except Exception:
                pass

            await asyncio.sleep(0.5)

    async def _find_element_with_fallbacks(
        self, page: Page, selectors: List[str], timeout: int = 3000
    ) -> Optional[object]:
        """
        Try multiple selectors in order until one is found.

        Args:
            page: Playwright page object
            selectors: List of CSS selectors to try in order
            timeout: Timeout per selector in milliseconds

        Returns:
            First matching element or None if none found
        """
        for selector in selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=timeout)
                if element:
                    return element
            except PlaywrightTimeoutError:
                continue
        return None

    async def aclose(self) -> None:
        if self._closing:
            return
        self._closing = True

        if not self._initialized:
            self._closing = False
            return

        if self.browser is not None:
            try:
                await self.browser.close()
            except Exception:
                pass

        if self.playwright is not None:
            try:
                await self.playwright.stop()
            except Exception:
                pass

        self.browser = None
        self.playwright = None
        self._semaphore = None
        self._initialized = False
        self._closing = False

    def close(self) -> None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                if not _NEST_ASYNCIO_AVAILABLE:
                    raise RuntimeError(
                        "close() cannot run inside an active event loop without nest_asyncio; "
                        "use await aclose() instead."
                    )
                loop.run_until_complete(self.aclose())
                return
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self.aclose())

    def __del__(self):
        if getattr(self, "_initialized", False):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.aclose())
                else:
                    loop.run_until_complete(self.aclose())
            except Exception:
                pass

    def get_params(self) -> dict:
        return {
            "model_name": self.model_name,
            "max_concurrency": self.max_concurrency,
            "batch_size": self.batch_size,
            "headless": self.headless,
            "wait_timeout": self.wait_timeout,
            "response_wait_time": self.response_wait_time,
            "stability_check_time": self.stability_check_time,
            **self.kwargs,
        }
