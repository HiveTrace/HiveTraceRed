Installation
============

Requirements
------------

* Python 3.10 or higher
* pip package manager
* Virtual environment (recommended)

Installation from PyPI
----------------------

Create and activate a virtual environment (recommended):

.. code-block:: bash

   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

The recommended way to install HiveTraceRed is via pip:

.. code-block:: bash

   pip install hivetracered

This will install the package and make the ``hivetracered`` and ``hivetracered-report`` CLI commands available.

Optional Dependencies
~~~~~~~~~~~~~~~~~~~~~

Install with optional dependencies for development or documentation:

.. code-block:: bash

   # For development (includes build tools)
   pip install hivetracered[dev]

   # For building documentation
   pip install hivetracered[docs]

   # Install everything
   pip install hivetracered[all]

Development Installation
------------------------

If you want to contribute to HiveTraceRed or modify the source code, install from source:

Clone the repository:

.. code-block:: bash

   git clone https://github.com/HiveTrace/HiveTraceRed.git
   cd HiveTraceRed


Install in editable mode with development dependencies:

.. code-block:: bash

   pip install -e '.[dev]'

Build Documentation Locally
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want to build the documentation:

.. code-block:: bash

   pip install -e '.[docs]'
   cd docs
   make html

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