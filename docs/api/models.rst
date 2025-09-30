Models API
==========

The models module provides unified interfaces for various LLM providers.

Base Class
----------

.. automodule:: models
   :members:
   :undoc-members:

Model
~~~~~

.. autoclass:: models.Model
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Model Implementations
---------------------

OpenAI Models
~~~~~~~~~~~~~

.. autoclass:: models.OpenAIModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

GigaChat Models
~~~~~~~~~~~~~~~

.. autoclass:: models.GigaChatModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Yandex Models
~~~~~~~~~~~~~

.. autoclass:: models.YandexGPTModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Google Gemini Models
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: models.GeminiModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

.. autoclass:: models.GeminiNativeModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Sber Cloud Models
~~~~~~~~~~~~~~~~~

.. autoclass:: models.SberCloudModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

OpenRouter Models
~~~~~~~~~~~~~~~~~

.. autoclass:: models.OpenRouterModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Usage Examples
--------------

Synchronous Usage
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from models import OpenAIModel

   # Initialize model
   model = OpenAIModel(
       model="gpt-4",
       temperature=0.7,
       max_tokens=1000
   )

   # Single request
   response = model.invoke("What is 2+2?")
   print(response['content'])

   # Batch requests
   prompts = ["Question 1", "Question 2", "Question 3"]
   responses = model.batch(prompts, batch_size=10)

Asynchronous Usage
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from models import OpenAIModel

   async def async_example():
       model = OpenAIModel(model="gpt-4")

       # Single request
       response = await model.ainvoke("What is AI?")
       print(response['content'])

       # Batch requests
       prompts = ["Q1", "Q2", "Q3"]
       responses = await model.abatch(prompts, batch_size=5)

       # Streaming batch
       async for response in model.stream_abatch(prompts, batch_size=2):
           print(f"Got response: {response['content']}")

   asyncio.run(async_example())

Message Format
~~~~~~~~~~~~~~

.. code-block:: python

   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4")

   # String format
   response = model.invoke("Hello")

   # Message format
   messages = [
       {"role": "system", "content": "You are helpful"},
       {"role": "user", "content": "Hello"}
   ]
   response = model.invoke(messages)

Safety Filters
~~~~~~~~~~~~~~

.. code-block:: python

   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4")
   response = model.invoke("Dangerous prompt")

   # Check if blocked
   if model.is_answer_blocked(response):
       print("Response was blocked by safety filters")
   else:
       print(response['content'])

Error Handling
~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from models import OpenAIModel

   async def with_error_handling():
       model = OpenAIModel(model="gpt-4")

       try:
           response = await model.ainvoke("Test prompt")
           print(response['content'])
       except Exception as e:
           print(f"Error: {e}")

   asyncio.run(with_error_handling())

Model Configuration
-------------------

All models accept these common parameters:

* ``model``: Model identifier (required)
* ``temperature``: Sampling temperature (0.0 - 2.0)
* ``max_tokens``: Maximum tokens in response
* ``top_p``: Nucleus sampling parameter
* Additional provider-specific parameters

Response Format
---------------

All models return dictionaries with:

.. code-block:: python

   {
       "content": "The model's response text",
       "model": "gpt-4",
       "finish_reason": "stop",  # "stop", "length", "content_filter", etc.
       # Additional provider-specific fields
   }

See Also
--------

* :doc:`../user-guide/model-integration` - Model integration guide
* :doc:`../getting-started/quickstart` - Quick start guide
* :doc:`../getting-started/configuration` - Configuration options