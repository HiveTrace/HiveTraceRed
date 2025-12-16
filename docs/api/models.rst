Models API
==========

The models module provides unified interfaces for various LLM providers.

Base Class
----------

Model
~~~~~

.. autoclass:: hivetracered.models.base_model.Model
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Model Implementations
---------------------

OpenAI Models
~~~~~~~~~~~~~

.. autoclass:: hivetracered.models.openai_model.OpenAIModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

GigaChat Models
~~~~~~~~~~~~~~~

.. autoclass:: hivetracered.models.gigachat_model.GigaChatModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Yandex Models
~~~~~~~~~~~~~

.. autoclass:: hivetracered.models.yandex_model.YandexGPTModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Google Gemini Models
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: hivetracered.models.gemini_model.GeminiModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

.. autoclass:: hivetracered.models.gemini_native_model.GeminiNativeModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Sber Cloud Models
~~~~~~~~~~~~~~~~~

.. autoclass:: hivetracered.models.cloud_ru_model.CloudRuModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

OpenRouter Models
~~~~~~~~~~~~~~~~~

.. autoclass:: hivetracered.models.openrouter_model.OpenRouterModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Web-Based Models (Browser Automation)
--------------------------------------

Web Model Base Class
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: hivetracered.models.web_model.WebModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Mistral Web Model
~~~~~~~~~~~~~~~~~

.. autoclass:: hivetracered.models.mistral_web_model.MistralWebModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Utilities
---------

Web Action Recorder
~~~~~~~~~~~~~~~~~~~

.. autoclass:: hivetracered.utils.web_action_recorder.WebActionRecorder
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

.. autofunction:: hivetracered.utils.web_action_recorder.record_browser_session

See Also
--------

* :doc:`../user-guide/model-integration` - Usage guide and examples
* :doc:`../user-guide/web-models` - Web-based models and action recorder guide