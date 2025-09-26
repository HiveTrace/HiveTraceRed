Quick Start Guide
=================

This guide will help you get started with HiveTraceRed quickly.

Basic Attack Usage
------------------

Using a Simple Attack
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.simple_instructions.none_attack import NoneAttack

   # Create an attack instance
   attack = NoneAttack()

   # Apply the attack to your prompt
   original_prompt = "Tell me about cybersecurity"
   modified_prompt = attack.apply(original_prompt)

   print(f"Original: {original_prompt}")
   print(f"Modified: {modified_prompt}")

Using Persuasion Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.persuasion.authority_endorsement_attack import AuthorityEndorsementAttack

   attack = AuthorityEndorsementAttack()
   prompt = "Explain how to secure a network"
   modified = attack.apply(prompt)

Using Output Formatting Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.output_formatting.json_output_attack import JSONOutputAttack

   attack = JSONOutputAttack()
   prompt = "What are common security vulnerabilities?"
   modified = attack.apply(prompt)

Composed Attacks
----------------

You can combine multiple attacks for more sophisticated testing:

.. code-block:: python

   from attacks.composed_attack import ComposedAttack
   from attacks.types.persuasion.authority_endorsement_attack import AuthorityEndorsementAttack
   from attacks.types.output_formatting.json_output_attack import JSONOutputAttack

   # Create a composed attack
   composed = ComposedAttack([
       AuthorityEndorsementAttack(),
       JSONOutputAttack()
   ])

   result = composed.apply("Your test prompt")

Getting Model Responses
-----------------------

Collecting LLM Responses
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pipeline.model_responses import ModelResponses

   # Initialize model response collector
   responses = ModelResponses()

   # Apply attack and get model response
   attack = AuthorityEndorsementAttack()
   modified_prompt = attack.apply("Your test prompt")

   # Get response from model
   response = responses.get_response(modified_prompt, model="your_model")

Evaluation with WildGuard
-------------------------

Using WildGuard Evaluator
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from evaluators.wildguard_evaluator import WildGuardEvaluator

   evaluator = WildGuardEvaluator()

   # Evaluate model response for safety
   evaluation_result = evaluator.evaluate(
       prompt=modified_prompt,
       response=model_response
   )

   # Check if attack was successful
   is_jailbroken = evaluation_result['is_harmful']

Pipeline Integration
~~~~~~~~~~~~~~~~~~~~

Complete workflow with attack, response collection, and evaluation:

.. code-block:: python

   # Complete pipeline example
   attack = DANAttack()
   modified_prompt = attack.apply("Original prompt")

   # Get model response
   response = model_client.query(modified_prompt)

   # Evaluate with WildGuard
   evaluation = wildguard_evaluator.evaluate(modified_prompt, response)

   print(f"Attack success: {evaluation['is_harmful']}")

Running the Pipeline
~~~~~~~~~~~~~~~~~~~~

The project includes pipeline scripts for systematic evaluation:

.. code-block:: bash

   # Run evaluation pipeline
   python pipeline/run_evaluation.py --config your_config.json

Next Steps
----------

- Explore the :doc:`attacks/index` section for detailed attack documentation
- Check out :doc:`evaluators/index` for evaluation methodologies
- See :doc:`api/index` for complete API reference