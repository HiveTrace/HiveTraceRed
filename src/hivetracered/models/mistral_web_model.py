"""
Mistral Le Chat web-based model implementation using Playwright browser automation.

This module provides a WebModel implementation for interacting with Mistral's Le Chat
interface at chat.mistral.ai when no official API is available.
"""

from __future__ import annotations

from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from hivetracered.models.web_model import WebModel


class MistralWebModel(WebModel):
    """
    WebModel implementation for Mistral Le Chat (chat.mistral.ai).

    This class automates interaction with Mistral's chat interface using Playwright.
    It handles consent dialogs, multiple input element strategies, and stable response
    detection for streaming responses.

    Example:
        ```python
        from hivetracered.models.mistral_web_model import MistralWebModel

        model = MistralWebModel(
            model="mistral-large",
            headless=False,
            max_concurrency=2
        )

        response = model.invoke("What is the capital of France?")
        print(response["content"])

        model.close()
        ```
    """

    def __init__(
        self,
        model: str = "mistral-large",
        max_concurrency: int = 1,
        headless: bool = False,
        wait_timeout: int = 30,
        response_wait_time: int = 60,
        stability_check_time: float = 2.0,
        **kwargs,
    ):
        """
        Initialize MistralWebModel.

        Args:
            model: Model name identifier (default: "mistral-large")
            max_concurrency: Maximum number of concurrent browser contexts (default: 1)
            headless: Run browser in headless mode (default: False)
            wait_timeout: Timeout for element waits in seconds (default: 30)
            response_wait_time: Maximum time to wait for response in seconds (default: 60)
            stability_check_time: Time content must be stable to consider complete (default: 2.0)
            **kwargs: Additional arguments passed to base class
        """
        super().__init__(
            model=model,
            max_concurrency=max_concurrency,
            headless=headless,
            wait_timeout=wait_timeout,
            response_wait_time=response_wait_time,
            stability_check_time=stability_check_time,
            **kwargs,
        )

        # Set the target URL for Mistral Le Chat
        self.target_url = "https://chat.mistral.ai/chat"

    async def _handle_initial_dialogs(self, page: Page) -> None:
        """
        Handle GDPR consent dialog if present.

        Args:
            page: Playwright page object
        """
        try:
            # Look for "Accept and continue" button (typical Mistral consent dialog)
            consent_button = await page.wait_for_selector(
                'button:has-text("Accept and continue")',
                timeout=5000
            )
            if consent_button:
                await consent_button.click()
                await page.wait_for_timeout(1000)
        except PlaywrightTimeoutError:
            # No consent dialog found, continue normally
            pass

    async def _find_input_element(self, page: Page) -> object:
        """
        Find the input element using multiple fallback strategies.

        Tries in order:
        1. ProseMirror contenteditable div (most common)
        2. Generic contenteditable with placeholder
        3. Textarea with data-testid attribute

        Args:
            page: Playwright page object

        Returns:
            element: The input element

        Raises:
            RuntimeError: If no input element can be found
        """
        selectors = [
            'div.ProseMirror[contenteditable="true"]',
            'div[contenteditable="true"][placeholder]',
            'textarea[data-testid]',
        ]

        element = await self._find_element_with_fallbacks(page, selectors, timeout=3000)
        if not element:
            raise RuntimeError("Could not find input element with any strategy")

        return element

    async def _send_input_text(self, element: object, text: str) -> None:
        """
        Send text to the input element using the appropriate method.

        Args:
            element: The input element
            text: Text to send
        """
        await element.click()
        await element.evaluate("el => el.innerText = ''")
        await element.type(text, delay=10)

    async def _send_message_and_get_response(self, page: Page, message: str) -> str:
        """
        Send a message to Mistral Le Chat and get the response.

        This method:
        1. Finds the input element using fallback strategies
        2. Sends the message and presses Enter
        3. Waits for response to appear
        4. Uses stability detection to wait for complete response
        5. Returns the final response text

        Args:
            page: Playwright page object
            message: Message to send

        Returns:
            Response text from Mistral

        Raises:
            Exception: If input element not found or response timeout
        """
        # Find input element with fallback strategies
        input_element = await self._find_input_element(page)

        # Send the message
        await self._send_input_text(input_element, message)
        await page.keyboard.press('Enter')

        # Wait for response to start appearing
        await page.wait_for_selector(
            'div[data-testid="text-message-part"][data-message-part-type="answer"]',
            timeout=self.wait_timeout * 1000
        )

        # Use stability detection to wait for complete response
        # The parent's _wait_for_stable_response now handles fallback automatically
        response_text = await self._wait_for_stable_response(
            page,
            'div[data-testid="text-message-part"][data-message-part-type="answer"]',
            timeout=self.response_wait_time,
            stable_time=self.stability_check_time,
            fallback_to_last=True
        )

        return response_text.strip() if response_text else ""
