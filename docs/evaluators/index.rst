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

   from evaluators import WildGuardGPTEvaluator
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4")
   evaluator = WildGuardGPTEvaluator(model)

   # Evaluate attack success
   result = await evaluator.aevaluate(
       prompt="Modified prompt after attack",
       response="Model's response"
   )

   is_jailbroken = result['is_harmful']

Pipeline Integration
~~~~~~~~~~~~~~~~~~~~

The evaluators integrate with the pipeline system for systematic assessment:

.. code-block:: python

   from pipeline import setup_attacks, stream_attack_prompts, stream_model_responses, stream_evaluated_responses
   from evaluators import WildGuardGPTEvaluator
   from models import OpenAIModel

   # Setup components
   model = OpenAIModel(model="gpt-4")
   evaluator = WildGuardGPTEvaluator(model)
   attacks = setup_attacks(attack_list, model)

   # Run pipeline
   async def run_evaluation(test_cases):
       attack_prompts = []
       async for prompt_data in stream_attack_prompts(attacks, test_cases):
           attack_prompts.append(prompt_data)

       responses = []
       async for response_data in stream_model_responses(model, attack_prompts):
           responses.append(response_data)

       results = []
       async for result in stream_evaluated_responses(evaluator, responses):
           results.append(result)

       return results

Evaluation Metrics
------------------

The evaluation system tracks various metrics including:

- **Jailbreak Success Rate**: Percentage of attacks that successfully bypass safety measures
- **Harm Detection**: WildGuard-based harmful content identification
- **Safety Compliance**: Model adherence to safety guidelines
- **Attack Effectiveness**: Success rates across different attack categories
- **Behavioral Consistency**: Response patterns across similar prompts

For detailed pipeline documentation, see :doc:`../pipeline/index`.