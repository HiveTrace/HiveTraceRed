"""
Base class for web-based model implementations using Playwright browser automation.

This module provides a foundation for models that interact with AI chat interfaces
through browser automation when no official API is available.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import AsyncGenerator

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

    # Class-level set keeps fire-and-forget cleanup tasks (scheduled from
    # __del__) alive until they finish, so the event loop does not GC them.
    _pending_finalizer_tasks: set = set()

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
        self._init_lock = asyncio.Lock()

        self.playwright = None
        self.browser: Browser | None = None
        self._semaphore: asyncio.Semaphore | None = None

    async def _initialize_browser(self) -> None:
        # Fast path: if already initialized, return immediately
        if self._initialized:
            return

        # Acquire lock to prevent concurrent initialization
        async with self._init_lock:
            # Double-check pattern: verify still not initialized after acquiring lock
            if self._initialized:
                return

            # Check if closing was requested
            if self._closing:
                raise RuntimeError("Cannot initialize browser: model is closing")

            # Initialize browser resources
            try:
                self.playwright = await async_playwright().start()
                self.browser = await self._create_browser()
                self._semaphore = asyncio.Semaphore(self.max_concurrency)
                self._initialized = True
            except Exception:
                # Ensure _initialized remains False on failure so retry can work
                self._initialized = False
                raise

    async def _create_browser(self) -> Browser:
        if self.playwright is None:
            raise RuntimeError("Playwright is not initialized.")

        return await self.playwright.chromium.launch(headless=self.headless)

    async def _setup_context_and_page(self) -> tuple[BrowserContext, Page]:
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
        elif self.headless:
            new_context_kwargs["user_agent"] = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )

        context = await self.browser.new_context(**new_context_kwargs)

        if self.headless:
            await context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                window.chrome = {runtime: {}};
                """
            )

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

    def _prompt_to_message(self, prompt: str | list[dict[str, str]]) -> str:
        if isinstance(prompt, list):
            return prompt[-1].get("content", "") if prompt else ""
        return prompt

    @abstractmethod
    async def _send_message_and_get_response(self, page: Page, message: str) -> str:
        raise NotImplementedError

    async def _process_single_prompt(
        self, page: Page, prompt: str | list[dict[str, str]]
    ) -> dict:
        message = self._prompt_to_message(prompt)
        try:
            response_text = await self._send_message_and_get_response(page, message)
            return {"content": response_text}
        except Exception as exc:
            return {"content": "", "error": str(exc), "error_type": type(exc).__name__}

    async def _run_in_new_context(self, prompt: str | list[dict[str, str]]) -> dict:
        """
        Run a prompt in a new (context, page) pair and dispose it afterwards.

        This ensures strict isolation between requests (no cookies/localStorage carryover).
        """
        await self._initialize_browser()
        if self._semaphore is None:
            raise RuntimeError("Concurrency semaphore is not initialized.")

        async with self._semaphore:
            context: BrowserContext | None = None
            page: Page | None = None
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

    async def ainvoke(self, prompt: str | list[dict[str, str]]) -> dict:
        return await self._run_in_new_context(prompt)

    def invoke(self, prompt: str | list[dict[str, str]]) -> dict:
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

    async def abatch(self, prompts: list[str | list[dict[str, str]]]) -> list[dict]:
        tasks = [self._run_in_new_context(prompt) for prompt in prompts]
        return await asyncio.gather(*tasks)

    def batch(self, prompts: list[str | list[dict[str, str]]]) -> list[dict]:
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
        self, prompts: list[str | list[dict[str, str]]]
    ) -> AsyncGenerator[dict]:
        await self._initialize_browser()
        if self._semaphore is None:
            raise RuntimeError("Concurrency semaphore is not initialized.")

        async def sem_task(
            idx: int, prompt: str | list[dict[str, str]]
        ) -> tuple[int, dict]:
            result = await self._run_in_new_context(prompt)
            return idx, result

        tasks = [asyncio.create_task(sem_task(i, p)) for i, p in enumerate(prompts)]
        total_tasks = len(tasks)
        results: dict[int, dict] = {}
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

    async def _handle_stable_response_timeout(
        self,
        page: Page,
        selector: str,
        last_content: str | None,
        fallback_to_last: bool,
    ) -> str:
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

    async def _check_response_stability(
        self,
        page: Page,
        selector: str,
        last_content: str | None,
        last_change_time: float,
        now: float,
        stable_time: float,
    ) -> tuple[str | None, str | None, float]:
        try:
            elements = await page.locator(selector).all()
            if not elements:
                return None, last_content, last_change_time
            current_content = await elements[-1].inner_text()
            if current_content != last_content:
                return None, current_content, now
            if now - last_change_time >= stable_time:
                return current_content, last_content, last_change_time
        except Exception:
            pass
        return None, last_content, last_change_time

    async def _wait_for_stable_response(
        self,
        page: Page,
        selector: str,
        stable_time: float | None = None,
        fallback_to_last: bool = True,
    ) -> str:
        """
        Wait until the matched element(s) text content stops changing.

        Useful for streaming UIs where the assistant response is progressively rendered.
        The wall-clock deadline is ``self.response_wait_time`` seconds; callers that need
        a different deadline should adjust that attribute or wrap the call in their own
        ``async with asyncio.timeout(...):`` block.

        Args:
            page: Playwright page object
            selector: CSS selector for response element(s)
            stable_time: Time content must be stable to consider complete
            fallback_to_last: If True, return last element's text on timeout/error

        Returns:
            Response text content

        Raises:
            RuntimeError: If no response found and fallback_to_last is False
        """
        stable_time = self.stability_check_time if stable_time is None else stable_time

        last_content = None
        last_change_time = asyncio.get_event_loop().time()

        try:
            async with asyncio.timeout(self.response_wait_time):
                while True:
                    now = asyncio.get_event_loop().time()
                    stable_result, last_content, last_change_time = await self._check_response_stability(
                        page, selector, last_content, last_change_time, now, stable_time
                    )
                    if stable_result is not None:
                        return stable_result

                    await asyncio.sleep(0.5)
        except TimeoutError:
            return await self._handle_stable_response_timeout(
                page, selector, last_content, fallback_to_last
            )

    # Per-selector budget passed to Playwright's wait_for_selector. Playwright's
    # API exposes the deadline as a kwarg (in milliseconds), so the call still
    # uses ``timeout=``; only our function's signature drops the parameter.
    _FALLBACK_SELECTOR_TIMEOUT_MS: int = 3000

    async def _find_element_with_fallbacks(
        self, page: Page, selectors: list[str]
    ) -> object | None:
        """
        Try multiple selectors in order until one is found.

        Args:
            page: Playwright page object
            selectors: List of CSS selectors to try in order

        Returns:
            First matching element or None if none found
        """
        for selector in selectors:
            try:
                element = await page.wait_for_selector(
                    selector, timeout=self._FALLBACK_SELECTOR_TIMEOUT_MS
                )
                if element:
                    return element
            except PlaywrightTimeoutError:
                continue
        return None

    async def aclose(self) -> None:
        # Fast path: if already closing or closed, return immediately
        if self._closing:
            return

        # Acquire lock to prevent concurrent cleanup
        async with self._init_lock:
            # Double-check pattern: verify still not closing after acquiring lock
            if self._closing:
                return
            self._closing = True

            # If never initialized, nothing to clean up
            if not self._initialized:
                self._closing = False
                return

            # Clean up browser resources
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
                    task = asyncio.create_task(self.aclose())
                    WebModel._pending_finalizer_tasks.add(task)
                    task.add_done_callback(WebModel._pending_finalizer_tasks.discard)
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
