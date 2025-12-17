Web-Based Models
=================

HiveTraceRed supports testing AI chat interfaces that don't have an official API through browser automation. This is particularly useful for testing web-based AI assistants, custom deployments, or models without public APIs.

Overview
--------

When an AI model doesn't provide an API, you can use the **WebModel** framework to interact with it through browser automation using Playwright. This allows you to:

* Test web-based AI chat interfaces
* Automate interactions with custom AI deployments
* Test models that only have web interfaces
* Record and replay user interactions

The workflow consists of two main components:

1. **Web Action Recorder**: Records user interactions to help you identify UI elements
2. **WebModel**: Automates browser interactions based on the recorded information

Web Action Recorder
-------------------

The Web Action Recorder helps you capture user interactions with a web interface, making it easier to create automated test scripts.

What It Records
~~~~~~~~~~~~~~~

The recorder captures:

* **Click events**: Position, target element, CSS/XPath selectors
* **Input events**: Text entered into fields, element identifiers
* **Selection events**: Text selected by user, context information
* **Element metadata**: IDs, classes, ARIA attributes, data attributes

Command Line Usage
~~~~~~~~~~~~~~~~~~

The recorder is available as a CLI command after installing HiveTraceRed:

.. code-block:: bash

   # Record session starting at a specific URL
   hivetracered-recorder --url https://chat.example.com

   # Save to specific file
   hivetracered-recorder --url https://chat.example.com --output session.json

   # Run in headless mode (no visible browser window)
   hivetracered-recorder --url https://chat.example.com --headless

   # Quiet mode (suppress console output)
   hivetracered-recorder --url https://chat.example.com --quiet

Press Ctrl-C to stop recording and save the log file.

Recording Workflow
~~~~~~~~~~~~~~~~~~

1. **Start the recorder** with your target URL
2. **Interact with the interface**:

   * Log in if needed
   * Close cookie banners and popups
   * Type a test message in the input field
   * Press Enter or click the send button
   * Wait for the response
   * Select the response text with your mouse
   * Repeat 2-3 times to capture multiple interactions

3. **Stop the recorder** (Ctrl-C)
4. **Review the log file** to identify element selectors

Example Log Structure
~~~~~~~~~~~~~~~~~~~~~

The recorder saves a JSON file with detailed event information:

.. code-block:: json

   [
     {
       "timestamp": "2024-01-15T10:30:45.123456",
       "event_type": "click",
       "x": 850,
       "y": 400,
       "target": {
         "tagName": "BUTTON",
         "id": "send-button",
         "className": "btn-primary",
         "textContent": "Send"
       },
       "selectors": {
         "css": "button#send-button",
         "xpath": "//*[@id='send-button']"
       },
       "url": "https://chat.example.com"
     },
     {
       "timestamp": "2024-01-15T10:30:46.789012",
       "event_type": "input",
       "value": "What is the capital of France?",
       "target": {
         "tagName": "INPUT",
         "id": "message-input",
         "name": "message",
         "type": "text"
       },
       "selectors": {
         "css": "input#message-input",
         "xpath": "//*[@id='message-input']"
       }
     }
   ]

Creating Web Models
-------------------

Once you've recorded a session and identified the UI elements, you can create a custom WebModel class.

Base WebModel Class
~~~~~~~~~~~~~~~~~~~

All web models inherit from the ``WebModel`` base class, which provides:

* Browser lifecycle management (Playwright)
* Concurrent request handling with configurable concurrency
* Automatic context isolation between requests
* Stable response detection for streaming UIs
* Standard Model interface (invoke, batch, stream_abatch)

Required Implementation
~~~~~~~~~~~~~~~~~~~~~~~

You must implement one abstract method:

.. code-block:: python

   async def _send_message_and_get_response(self, page: Page, message: str) -> str:
       """Send message and return response text"""

Optional Overrides
~~~~~~~~~~~~~~~~~~

You can optionally override:

.. code-block:: python

   async def _handle_initial_dialogs(self, page: Page) -> None:
       """Handle consent popups, login, etc."""

   async def _create_browser(self) -> Browser:
       """Custom browser launch settings"""

   async def _setup_context_and_page(self) -> Tuple[BrowserContext, Page]:
       """Custom context/page initialization"""

Example: Creating a Custom Web Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here's a complete example based on Mistral Le Chat:

.. code-block:: python

   from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
   from hivetracered.models.web_model import WebModel

   class MyAIChatModel(WebModel):
       """Web model for your custom AI chat interface."""

       def __init__(
           self,
           model: str = "my-ai-chat",
           max_concurrency: int = 1,
           headless: bool = False,
           **kwargs
       ):
           super().__init__(
               model=model,
               max_concurrency=max_concurrency,
               headless=headless,
               **kwargs
           )

           # Set your chat URL
           self.target_url = "https://your-ai-chat.com/chat"

       async def _handle_initial_dialogs(self, page: Page) -> None:
           """Handle any initial popups or consent dialogs."""
           try:
               # Look for consent button (use selectors from your log file)
               consent_button = await page.wait_for_selector(
                   'button:has-text("Accept")',
                   timeout=5000
               )
               if consent_button:
                   await consent_button.click()
                   await page.wait_for_timeout(1000)
           except PlaywrightTimeoutError:
               # No consent dialog, continue
               pass

       async def _send_message_and_get_response(
           self, page: Page, message: str
       ) -> str:
           """Send message and get response."""

           # 1. Find input element (use selector from your log)
           input_element = await page.wait_for_selector(
               'textarea#message-input',  # From your recorded session
               timeout=self.wait_timeout * 1000
           )

           # 2. Type the message
           await input_element.click()
           await input_element.fill('')  # Clear first
           await input_element.type(message, delay=10)

           # 3. Send the message (press Enter or click button)
           await page.keyboard.press('Enter')
           # Or click send button:
           # await page.click('button#send-button')

           # 4. Wait for response to appear (use selector from your log)
           await page.wait_for_selector(
               'div.response-message',
               timeout=self.wait_timeout * 1000
           )

           # 5. Wait for stable response (handles streaming responses)
           response_text = await self._wait_for_stable_response(
               page,
               'div.response-message',  # Selector for response elements
               timeout=self.response_wait_time,
               stable_time=self.stability_check_time,
               fallback_to_last=True
           )

           return response_text.strip()

Using Your Web Model
~~~~~~~~~~~~~~~~~~~~

Once created, use it like any other model:

.. code-block:: python

   from my_models import MyAIChatModel

   # Initialize
   model = MyAIChatModel(
       model="my-ai-chat",
       headless=False,  # Set to True for production
       max_concurrency=2,
       wait_timeout=30,
       response_wait_time=60
   )

   # Single request
   response = model.invoke("What is machine learning?")
   print(response["content"])

   # Batch requests (runs in parallel up to max_concurrency)
   prompts = [
       "What is Python?",
       "Explain quantum computing",
       "What is blockchain?"
   ]
   responses = model.batch(prompts)
   for resp in responses:
       print(resp["content"])

   # Clean up
   model.close()

Helper Methods
--------------

The WebModel base class provides several helper methods:

Wait for Stable Response
~~~~~~~~~~~~~~~~~~~~~~~~

For streaming UIs where text appears gradually:

.. code-block:: python

   response_text = await self._wait_for_stable_response(
       page,
       selector='div.message-content',
       timeout=60,  # Max wait time in seconds
       stable_time=2.0,  # Must be stable for 2 seconds
       fallback_to_last=True  # Return last element on timeout
   )

Find Element with Fallbacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Try multiple selectors until one matches:

.. code-block:: python

   element = await self._find_element_with_fallbacks(
       page,
       selectors=[
           'textarea#chat-input',
           'div[contenteditable="true"]',
           'input[type="text"][name="message"]'
       ],
       timeout=3000  # Timeout per selector in milliseconds
   )

Best Practices
--------------

1. **Record First**: Always use the Web Action Recorder to identify elements before coding
2. **Use Multiple Selectors**: Provide fallback selectors in case the UI changes
3. **Handle Timeouts**: Set appropriate timeouts for your target interface
4. **Start Headless=False**: Debug with visible browser first, then use headless mode
5. **Respect Concurrency**: Start with ``max_concurrency=1``, increase carefully
6. **Clean Up**: Always call ``model.close()`` when done
7. **Error Handling**: Web UIs can change; implement robust error handling
8. **Stability Checks**: Use ``_wait_for_stable_response`` for streaming responses

Configuration Parameters
------------------------

All web models support these parameters:

* **model** (str): Model identifier for logging
* **max_concurrency** (int): Max parallel browser contexts (default: 1)
* **headless** (bool): Run browser without GUI (default: False)
* **wait_timeout** (int): Element wait timeout in seconds (default: 30)
* **response_wait_time** (int): Max time to wait for response (default: 60)
* **stability_check_time** (float): Time content must be stable (default: 2.0)

Advanced Features
-----------------

Custom Browser Launch
~~~~~~~~~~~~~~~~~~~~~

Override ``_create_browser`` for custom settings:

.. code-block:: python

   async def _create_browser(self) -> Browser:
       return await self.playwright.chromium.launch(
           headless=self.headless,
           args=['--disable-blink-features=AutomationControlled'],
           proxy={'server': 'http://proxy.example.com:8080'}
       )

Session Persistence
~~~~~~~~~~~~~~~~~~~

Override ``_setup_context_and_page`` to reuse sessions:

.. code-block:: python

   async def _setup_context_and_page(self):
       # Load saved state (cookies, localStorage)
       context = await self.browser.new_context(
           storage_state='auth_state.json'
       )
       page = await context.new_page()
       await page.goto(self.target_url)
       return context, page

Troubleshooting
---------------

Browser Not Closing
~~~~~~~~~~~~~~~~~~~

Always call ``model.close()`` or use context managers:

.. code-block:: python

   # This pattern ensures cleanup
   model = MyAIChatModel()
   try:
       response = model.invoke("test")
   finally:
       model.close()

Selector Not Found
~~~~~~~~~~~~~~~~~~

* Check if the page fully loaded (``wait_until='networkidle'``)
* Verify selector with the Web Action Recorder
* Try alternative selectors with ``_find_element_with_fallbacks``

Timeout Errors
~~~~~~~~~~~~~~

* Increase ``wait_timeout`` or ``response_wait_time``
* Check if elements are hidden or in iframes
* Verify the page URL is correct

Response Cut Off
~~~~~~~~~~~~~~~~

* Increase ``stability_check_time`` for slower streaming
* Check if ``response_wait_time`` is too short
* Verify the response selector captures the full message

See Also
--------

* :doc:`model-integration` - General model integration guide
* :doc:`../api/models` - API reference for all models
* :doc:`running-pipeline` - Using models in the attack pipeline
