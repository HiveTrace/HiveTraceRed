Installation
============

Requirements
------------

* Python 3.10 or higher
* pip package manager
* Virtual environment (recommended)

Basic Installation
------------------

Clone the repository:

.. code-block:: bash

   git clone https://github.com/HiveTrace/HiveTraceRed.git
   cd HiveTraceRed

Create and activate a virtual environment (recommended):

.. code-block:: bash

   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

Install dependencies:

.. code-block:: bash

   pip install -r requirements.txt

Additional Dependencies for Documentation
------------------------------------------

If you want to build the documentation locally:

.. code-block:: bash

   pip install sphinx furo sphinx-autodoc-typehints

Environment Setup
-----------------

Create a ``.env`` file in the project root with your API keys:

.. code-block:: bash

   cp .env.template .env

Edit ``.env`` and add your API credentials:

.. code-block:: bash

   # OpenAI
   OPENAI_API_KEY=your_openai_api_key_here

   # GigaChat
   GIGACHAT_CREDENTIALS=your_gigachat_credentials_here

   # Yandex Cloud
   YANDEX_FOLDER_ID=your_folder_id
   YANDEX_API_KEY=your_api_key

   # Google Gemini
   GOOGLE_API_KEY=your_google_api_key_here

.. note::
   You only need to configure API keys for the LLM providers you plan to use.

Next Steps
----------

:doc:`quickstart` - Run your first red teaming test