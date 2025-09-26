Installation
============

Requirements
------------

- Python 3.8 or higher
- Git

Quick Installation
------------------

1. Clone the repository:

.. code-block:: bash

   git clone https://github.com/HiveTrace/HiveTraceRed.git
   cd HiveTraceRed

2. Install dependencies:

.. code-block:: bash

   pip install -r requirements.txt

3. Verify installation:

.. code-block:: python

   from attacks.types.simple_instructions.none_attack import NoneAttack
   attack = NoneAttack()
   print("Installation successful!")

Configuration
-------------

The framework supports various LLM providers. Configure your API keys in a `.env` file in the project root:

.. code-block:: bash

   # Create .env file in project root
   echo "OPENAI_API_KEY=your_openai_key" >> .env
   echo "GOOGLE_API_KEY=your_google_key" >> .env
   echo "ANTHROPIC_API_KEY=your_anthropic_key" >> .env

Example `.env` file:

.. code-block:: text

   OPENAI_API_KEY=sk-your-openai-key-here
   GOOGLE_API_KEY=your-google-key-here
   ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here