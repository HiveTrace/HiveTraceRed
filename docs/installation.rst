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

   # Copy template and configure API keys
   cp .env.template .env
   # Edit .env file to add your actual API keys

