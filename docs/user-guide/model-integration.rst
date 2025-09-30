Model Integration
=================

HiveTraceRed supports multiple LLM providers and makes it easy to add new ones. This guide shows how to use built-in models and create custom integrations.

Supported Models
----------------

Built-in Provider Support
~~~~~~~~~~~~~~~~~~~~~~~~~~

* **OpenAI**: GPT-4, GPT-3.5-turbo, GPT-4-turbo
* **GigaChat**: GigaChat, GigaChat Plus (Sber)
* **Yandex**: YandexGPT, YandexGPT Lite
* **Google Gemini**: Gemini Pro, Gemini 2.5 Flash
* **OpenRouter**: Access to multiple model providers
* **Sber Cloud**: Sber Cloud ML models

Using Built-in Models
----------------------

OpenAI Models
~~~~~~~~~~~~~

.. code-block:: python

   from models import OpenAIModel

   # Basic usage
   model = OpenAIModel(model="gpt-4")

   # With parameters
   model = OpenAIModel(
       model="gpt-4-turbo",
       temperature=0.7,
       max_tokens=1000
   )

   # Synchronous call
   response = model.invoke("What is 2+2?")
   print(response['content'])

   # Asynchronous call
   import asyncio
   response = await model.ainvoke("What is 2+2?")

GigaChat Models
~~~~~~~~~~~~~~~

.. code-block:: python

   from models import GigaChatModel

   model = GigaChatModel(
       model="gigachat",
       credentials="YOUR_CREDENTIALS",
       verify_ssl_certs=False
   )

   response = await model.ainvoke("Привет, как дела?")

Yandex Models
~~~~~~~~~~~~~

.. code-block:: python

   from models import YandexGPTModel

   model = YandexGPTModel(
       model="yandexgpt-lite",
       folder_id="YOUR_FOLDER_ID",
       api_key="YOUR_API_KEY"
   )

   response = await model.ainvoke("Расскажи о Python")

Google Gemini Models
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from models import GeminiNativeModel

   model = GeminiNativeModel(
       model="gemini-2.5-flash-preview-04-17",
       api_key="YOUR_API_KEY"
   )

   response = await model.ainvoke("Explain quantum computing")

OpenRouter
~~~~~~~~~~

.. code-block:: python

   from models import OpenRouterModel

   model = OpenRouterModel(
       model="openai/gpt-4",
       api_key="YOUR_OPENROUTER_KEY"
   )

   response = await model.ainvoke("Tell me a joke")

Model Interface
---------------

All models implement the ``Model`` base class with these methods:

Synchronous Methods
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Single request
   response = model.invoke(prompt)

   # Batch requests
   responses = model.batch(prompts, batch_size=10)

Asynchronous Methods
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Single request
   response = await model.ainvoke(prompt)

   # Batch requests (batch_size is set in base model, typically 10)
   responses = await model.abatch(prompts)

   # Streaming batch
   async for response in model.stream_abatch(prompts, batch_size=5):
       print(response)

Message Formats
---------------

String Format
~~~~~~~~~~~~~

.. code-block:: python

   response = await model.ainvoke("What is the capital of France?")

Message List Format
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   messages = [
       {"role": "system", "content": "You are a helpful assistant"},
       {"role": "user", "content": "What is 2+2?"}
   ]
   response = await model.ainvoke(messages)

Response Format
~~~~~~~~~~~~~~~

All models return a dictionary:

.. code-block:: python

   {
       "content": "The model's response text",
       "response_metadata": {
           "model_name": "gpt-4",
           "finish_reason": "stop",
           # Additional provider-specific fields
       }
   }

Creating Custom Models
----------------------

To integrate a new LLM provider, inherit from ``Model`` base class.

Basic Custom Model
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from models.base_model import Model
   from typing import Union, List, Dict
   import asyncio

   class MyCustomModel(Model):
       def __init__(self, model: str, api_key: str, **kwargs):
           self.model_name = model
           self.api_key = api_key
           self.params = kwargs

       def invoke(self, prompt: Union[str, List[Dict]]) -> dict:
           """Synchronous single request"""
           # Your implementation
           response_text = self._call_api(prompt)
           return {
               "content": response_text,
               "model": self.model_name
           }

       async def ainvoke(self, prompt: Union[str, List[Dict]]) -> dict:
           """Asynchronous single request"""
           # Your async implementation
           response_text = await self._async_call_api(prompt)
           return {
               "content": response_text,
               "model": self.model_name
           }

       def batch(self, prompts: List, batch_size: int = 10) -> List[dict]:
           """Synchronous batch processing"""
           return [self.invoke(p) for p in prompts]

       async def abatch(self, prompts: List, batch_size: int = 10) -> List[dict]:
           """Asynchronous batch processing"""
           tasks = [self.ainvoke(p) for p in prompts]
           return await asyncio.gather(*tasks)

       async def stream_abatch(self, prompts: List, batch_size: int = 1):
           """Stream results as they complete"""
           for i in range(0, len(prompts), batch_size):
               batch = prompts[i:i + batch_size]
               responses = await self.abatch(batch, batch_size)
               for response in responses:
                   yield response

       def _call_api(self, prompt):
           """Your API call implementation"""
           pass

       async def _async_call_api(self, prompt):
           """Your async API call implementation"""
           pass

Advanced Custom Model
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from models.base_model import Model
   import aiohttp

   class AdvancedCustomModel(Model):
       def __init__(self, model: str, api_url: str, api_key: str, **kwargs):
           self.model_name = model
           self.api_url = api_url
           self.api_key = api_key
           self.temperature = kwargs.get('temperature', 0.7)
           self.max_tokens = kwargs.get('max_tokens', 1000)

       async def ainvoke(self, prompt: Union[str, List[Dict]]) -> dict:
           # Convert prompt to provider format
           formatted_prompt = self._format_prompt(prompt)

           # Make API call
           async with aiohttp.ClientSession() as session:
               headers = {"Authorization": f"Bearer {self.api_key}"}
               payload = {
                   "model": self.model_name,
                   "messages": formatted_prompt,
                   "temperature": self.temperature,
                   "max_tokens": self.max_tokens
               }

               async with session.post(
                   self.api_url,
                   json=payload,
                   headers=headers
               ) as response:
                   data = await response.json()
                   return self._parse_response(data)

       def _format_prompt(self, prompt):
           """Convert to provider's format"""
           if isinstance(prompt, str):
               return [{"role": "user", "content": prompt}]
           return prompt

       def _parse_response(self, data):
           """Extract content from provider's response"""
           return {
               "content": data['choices'][0]['message']['content'],
               "model": self.model_name,
               "finish_reason": data['choices'][0]['finish_reason']
           }

       def is_answer_blocked(self, answer: dict) -> bool:
           """Check if response was blocked by safety filters"""
           return answer.get('finish_reason') == 'content_filter'

       def invoke(self, prompt):
           """Sync wrapper"""
           import asyncio
           return asyncio.run(self.ainvoke(prompt))

       # Implement other required methods...

Safety Filters
--------------

Detecting Blocked Responses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Override ``is_answer_blocked`` to detect safety filter activations:

.. code-block:: python

   class SafetyAwareModel(Model):
       def is_answer_blocked(self, answer: dict) -> bool:
           # Check for safety filter indicators
           if answer.get('finish_reason') == 'content_filter':
               return True
           if 'blocked' in answer.get('content', '').lower():
               return True
           return False

This is used by the pipeline to track successful jailbreaks.

Error Handling
--------------

Implement robust error handling:

.. code-block:: python

   async def ainvoke(self, prompt):
       max_retries = 3
       for attempt in range(max_retries):
           try:
               return await self._call_api(prompt)
           except RateLimitError:
               if attempt < max_retries - 1:
                   await asyncio.sleep(2 ** attempt)  # Exponential backoff
               else:
                   raise
           except APIError as e:
               logger.error(f"API error: {e}")
               raise

Registering Custom Models
--------------------------

Add to the model registry for use in configuration files:

.. code-block:: python

   # In pipeline/constants.py
   from models.my_custom_model import MyCustomModel

   MODEL_CLASSES = {
       "my-custom-model": MyCustomModel,
       "gpt-4": OpenAIModel,
       # ... other models
   }

Then use in configuration:

.. code-block:: yaml

   response_model:
     name: my-custom-model
     params:
       api_key: YOUR_KEY
       custom_param: value

Testing Your Model
------------------

.. code-block:: python

   import asyncio
   from models.my_custom_model import MyCustomModel

   async def test_model():
       model = MyCustomModel(
           model="my-model-v1",
           api_key="test-key"
       )

       # Test single request
       response = await model.ainvoke("Hello, world!")
       assert 'content' in response
       print(f"Response: {response['content']}")

       # Test batch
       prompts = ["Test 1", "Test 2", "Test 3"]
       responses = await model.abatch(prompts)
       assert len(responses) == 3

       # Test streaming
       async for response in model.stream_abatch(prompts):
           print(f"Streamed: {response['content'][:50]}")

   asyncio.run(test_model())

Best Practices
--------------

1. **Handle Both Sync and Async**: Implement both ``invoke`` and ``ainvoke``
2. **Support Message Formats**: Handle both string and message list inputs
3. **Implement Batching**: Use batching for efficiency
4. **Add Error Handling**: Implement retries and proper error messages
5. **Detect Safety Filters**: Override ``is_answer_blocked`` appropriately
6. **Document Parameters**: Clearly document all configuration options
7. **Test Thoroughly**: Test with various input formats and edge cases

See Also
--------

* :doc:`../api/models` - Model API reference
* :doc:`running-pipeline` - Using models in the pipeline
* :doc:`../getting-started/quickstart` - Quick start guide