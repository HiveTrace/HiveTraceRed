Models API
==========

The models module provides unified interfaces for various LLM providers.

Base Class
----------

.. automodule:: models
   :members:
   :undoc-members:
   :no-index:

Model
~~~~~

.. autoclass:: models.base_model.Model
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Model Implementations
---------------------

OpenAI Models
~~~~~~~~~~~~~

.. autoclass:: models.openai_model.OpenAIModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

GigaChat Models
~~~~~~~~~~~~~~~

.. autoclass:: models.gigachat_model.GigaChatModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Yandex Models
~~~~~~~~~~~~~

.. autoclass:: models.yandex_model.YandexGPTModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Google Gemini Models
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: models.gemini_model.GeminiModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

.. autoclass:: models.gemini_native_model.GeminiNativeModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Sber Cloud Models
~~~~~~~~~~~~~~~~~

.. autoclass:: models.sber_cloud_model.SberCloudModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

OpenRouter Models
~~~~~~~~~~~~~~~~~

.. autoclass:: models.openrouter_model.OpenRouterModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

See Also
--------

* :doc:`../user-guide/model-integration` - Usage guide and examples