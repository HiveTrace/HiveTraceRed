Evaluators
==========

The evaluation system in HiveTraceRed provides comprehensive assessment of LLM security and attack effectiveness, with WildGuard as the primary safety evaluator.

Overview
--------

Evaluators assess:

- Attack success rates using WildGuard safety evaluation
- Model safety responses and harmful content detection
- Jailbreak vulnerability detection
- Behavioral analysis and safety compliance

Evaluator Types
---------------

WildGuard Evaluator
~~~~~~~~~~~~~~~~~~~

The primary safety evaluator for detecting harmful content and jailbreak success:

.. toctree::
   :maxdepth: 1

   wildguard

Base Evaluator
~~~~~~~~~~~~~~

.. automodule:: evaluators.base_evaluator
   :members:
   :undoc-members:
   :show-inheritance:

Usage Examples
--------------

WildGuard Evaluation
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from evaluators.wildguard_evaluator import WildGuardEvaluator

   evaluator = WildGuardEvaluator()

   # Evaluate attack success
   result = evaluator.evaluate(
       prompt="Modified prompt after attack",
       response="Model's response"
   )

   is_jailbroken = result['is_harmful']

Pipeline Integration
~~~~~~~~~~~~~~~~~~~~

The evaluators integrate with the pipeline system for systematic assessment:

.. code-block:: python

   from pipeline.evaluation_pipeline import EvaluationPipeline
   from evaluators.wildguard_evaluator import WildGuardEvaluator

   pipeline = EvaluationPipeline(
       evaluator=WildGuardEvaluator(),
       attacks=attack_list,
       models=model_list
   )

   results = pipeline.run(test_cases)

Evaluation Metrics
------------------

The evaluation system tracks various metrics including:

- **Jailbreak Success Rate**: Percentage of attacks that successfully bypass safety measures
- **Harm Detection**: WildGuard-based harmful content identification
- **Safety Compliance**: Model adherence to safety guidelines
- **Attack Effectiveness**: Success rates across different attack categories
- **Behavioral Consistency**: Response patterns across similar prompts

For detailed pipeline documentation, see :doc:`../pipeline/index`.