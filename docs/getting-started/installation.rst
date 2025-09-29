Installation
============

Requirements
------------

- Python 3.8+
- Git

Quick Installation
------------------

1. Clone and setup:

.. code-block:: bash

   git clone https://github.com/HiveTrace/HiveTraceRed.git
   cd HiveTraceRed
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt

2. Configure API keys in `.env`:

.. code-block:: bash

   OPENAI_API_KEY=your_key_here
   GIGACHAT_CREDENTIALS=your_credentials_here
   YANDEX_GPT_API_KEY=your_key_here
   GOOGLE_API_KEY=your_key_here

3. Verify installation:

.. code-block:: python

   from attacks import NoneAttack
   attack = NoneAttack()
   result = attack.apply("Test prompt")
   print("Installation successful!")

Supported Models
----------------

- **OpenAI**: GPT-4, GPT-3.5-turbo
- **GigaChat**: gigachat-pro, gigachat-max
- **Yandex GPT**: yandexgpt-lite, yandexgpt-pro
- **Google Gemini**: gemini-pro, gemini-2.5-flash
- **OpenRouter**: Multiple models via OpenRouter

Next Steps
----------

See :doc:`quickstart` for usage examples.

