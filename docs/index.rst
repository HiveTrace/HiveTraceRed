HiveTraceRed Documentation
==========================

**HiveTraceRed** is a comprehensive security framework for testing and evaluating Large Language Model (LLM) vulnerabilities through systematic attack methodologies and evaluation pipelines.

Features
--------

- **Extensive Attack Library**: 80+ attack types across 9 categories
- **Systematic Evaluation**: Automated evaluation pipeline with WildGuard evaluator and multiple metrics
- **Flexible Architecture**: Modular design supporting various LLM providers
- **Comprehensive Coverage**: Context switching, persuasion, roleplay, and more

Quick Start
-----------

Installation
~~~~~~~~~~~~

.. code-block:: bash

   git clone https://github.com/HiveTrace/HiveTraceRed.git
   cd HiveTraceRed
   pip install -r requirements.txt

Basic Usage
~~~~~~~~~~~

.. code-block:: python

   from attacks.base_attack import BaseAttack
   from attacks.types.simple_instructions.none_attack import NoneAttack

   # Initialize an attack
   attack = NoneAttack()

   # Apply attack to your prompt
   modified_prompt = attack.apply("Your original prompt here")

Documentation Structure
-----------------------

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   installation
   quickstart
   usage_examples

.. toctree::
   :maxdepth: 2
   :caption: Attack Categories

   attacks/context_switching
   attacks/in_context_learning
   attacks/irrelevant_information
   attacks/output_formatting
   attacks/persuasion
   attacks/roleplay
   attacks/simple_instructions
   attacks/task_deflection
   attacks/text_structure_modification
   attacks/token_smuggling

.. toctree::
   :maxdepth: 2
   :caption: Evaluation & Pipeline

   evaluators/index
   pipeline/index

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/attacks
   api/evaluators
   api/pipeline

.. toctree::
   :maxdepth: 1
   :caption: Additional Information

   licenses_table

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`