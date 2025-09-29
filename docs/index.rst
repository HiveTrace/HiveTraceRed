HiveTraceRed Documentation
==========================

**HiveTraceRed** is a comprehensive security framework for testing and evaluating Large Language Model (LLM) vulnerabilities through systematic attack methodologies and evaluation pipelines.

Features
--------

- **Extensive Attack Library**: 80+ attack types across 10 categories
- **Systematic Evaluation**: Automated evaluation pipeline with WildGuard evaluators and multiple metrics
- **Flexible Architecture**: Modular design supporting various LLM providers
- **Comprehensive Coverage**: Context switching, persuasion, roleplay, token smuggling, and more
- **Multi-Language Support**: Supports testing across multiple languages including Russian
- **Streaming Pipeline**: Async streaming architecture for efficient processing

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

   from pipeline import setup_attacks, stream_attack_prompts
   from models import OpenAIModel

   # Initialize components
   model = OpenAIModel(model="gpt-4")
   attacks = setup_attacks(["NoneAttack"], model)

   # Apply attacks to your prompts
   base_prompts = ["Your original prompt here"]
   attack_prompts = []
   async for prompt_data in stream_attack_prompts(attacks, base_prompts):
       attack_prompts.append(prompt_data)

Documentation Structure
-----------------------

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   installation
   quickstart

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