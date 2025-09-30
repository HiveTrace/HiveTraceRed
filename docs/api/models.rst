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

See Also
--------

* :doc:`../user-guide/model-integration` - Usage guide and examples