API Reference
=============

Complete API documentation for all HiveTraceRed modules.

Core Modules
------------

.. toctree::
   :maxdepth: 2

   attacks
   models
   evaluators
   pipeline
   utils

Module Overview
---------------

Attacks Module
~~~~~~~~~~~~~~

The ``attacks`` module provides the framework for creating and applying adversarial attacks to prompts.

* :doc:`attacks` - Base classes and attack implementations

Models Module
~~~~~~~~~~~~~

The ``models`` module provides unified interfaces for various LLM providers.

* :doc:`models` - Model base classes and provider implementations

Evaluators Module
~~~~~~~~~~~~~~~~~

The ``evaluators`` module provides tools for assessing model responses for safety violations.

* :doc:`evaluators` - Evaluator base classes and implementations

Pipeline Module
~~~~~~~~~~~~~~~

The ``pipeline`` module orchestrates the complete red teaming workflow.

* :doc:`pipeline` - Pipeline components and utilities

Utils Module
~~~~~~~~~~~~

The ``utils`` module provides utility functions for content analysis.

* :doc:`utils` - Utility functions

Quick Links
-----------

Base Classes
~~~~~~~~~~~~

* :class:`attacks.BaseAttack` - Base class for all attacks
* :class:`models.Model` - Base class for all models
* :class:`evaluators.BaseEvaluator` - Base class for all evaluators

Common Operations
~~~~~~~~~~~~~~~~~

Creating Attacks:

.. code-block:: python

   from attacks import DANAttack
   attack = DANAttack()
   modified_prompt = attack.apply("Your prompt")

Using Models:

.. code-block:: python

   from models import OpenAIModel
   model = OpenAIModel(model="gpt-4")
   response = await model.ainvoke("Your prompt")

Evaluating Responses:

.. code-block:: python

   from evaluators import WildGuardGPTEvaluator
   evaluator = WildGuardGPTEvaluator()
   result = evaluator.evaluate(prompt, response)