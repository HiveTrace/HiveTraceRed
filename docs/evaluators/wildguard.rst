WildGuard Evaluator
==================

WildGuard is a safety evaluator that assesses whether LLM responses contain harmful content or if jailbreak attacks were successful.

Overview
--------

The WildGuard evaluator analyzes:

- **Harmful Content Detection**: Identifies potentially dangerous or inappropriate responses
- **Jailbreak Success**: Determines if safety measures were bypassed
- **Safety Compliance**: Evaluates adherence to safety guidelines

Usage
-----

Basic Evaluation
~~~~~~~~~~~~~~~~

.. code-block:: python

   from evaluators import WildGuardGPTEvaluator
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4")
   evaluator = WildGuardGPTEvaluator(model)

   # Evaluate a model response
   result = await evaluator.aevaluate(
       prompt="Your test prompt",
       response="Model's response"
   )

   # Check evaluation results
   is_harmful = result['is_harmful']
   safety_score = result['safety_score']

Integration with Attacks
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.roleplay.dan_attack import DANAttack
   from evaluators import WildGuardGPTEvaluator
   from models import OpenAIModel
   from pipeline import stream_model_responses

   # Setup model and evaluator
   model = OpenAIModel(model="gpt-4")
   evaluator = WildGuardGPTEvaluator(model)

   # Apply attack
   attack = DANAttack()
   modified_prompt = attack.apply("Tell me about cybersecurity")

   # Get model response using streaming
   responses = []
   async for response in stream_model_responses(model, [{'prompt': modified_prompt}]):
       responses.append(response)

   # Evaluate with WildGuard
   evaluation = await evaluator.aevaluate(modified_prompt, responses[0]['response'])

   print(f"Attack successful: {evaluation['is_harmful']}")
   print(f"Safety score: {evaluation['safety_score']}")

Batch Evaluation
~~~~~~~~~~~~~~~~

.. code-block:: python

   import pandas as pd

   def evaluate_attack_batch(attack_results, evaluator):
       evaluations = []

       for result in attack_results:
           evaluation = evaluator.evaluate(
               prompt=result['modified_prompt'],
               response=result['model_response']
           )

           evaluations.append({
               'attack_type': result['attack_type'],
               'is_harmful': evaluation['is_harmful'],
               'safety_score': evaluation['safety_score'],
               'original_prompt': result['original_prompt']
           })

       return pd.DataFrame(evaluations)

   # Use with attack results
   model = OpenAIModel(model="gpt-4")
   evaluator = WildGuardGPTEvaluator(model)
   evaluation_df = evaluate_attack_batch(attack_results, evaluator)

Evaluation Metrics
------------------

The WildGuard evaluator provides:

- **is_harmful** (bool): Whether the response contains harmful content
- **safety_score** (float): Numerical safety assessment (0.0 = safe, 1.0 = harmful)
- **confidence** (float): Confidence level of the evaluation
- **violation_categories** (list): Specific types of safety violations detected

Pipeline Integration
--------------------

The WildGuard evaluator integrates seamlessly with the HiveTraceRed pipeline:

.. code-block:: python

   from pipeline import setup_attacks, stream_attack_prompts, stream_model_responses, stream_evaluated_responses
   from evaluators import WildGuardGPTEvaluator
   from models import OpenAIModel

   # Setup components
   model = OpenAIModel(model="gpt-4")
   evaluator = WildGuardGPTEvaluator(model)
   attacks = setup_attacks(["DANAttack", "AIMAttack", "EvilConfidantAttack"], model)

   # Run pipeline
   async def run_evaluation(test_prompts):
       attack_prompts = []
       async for prompt_data in stream_attack_prompts(attacks, test_prompts):
           attack_prompts.append(prompt_data)

       responses = []
       async for response_data in stream_model_responses(model, attack_prompts):
           responses.append(response_data)

       results = []
       async for result in stream_evaluated_responses(evaluator, responses):
           results.append(result)

       return results

Advanced Configuration
----------------------

Customize WildGuard behavior:

.. code-block:: python

   model = OpenAIModel(model="gpt-4")
   evaluator = WildGuardGPTEvaluator(
       model=model,
       name="WildGuard Safety Evaluator",
       description="Evaluates responses for harmful content using WildGuard methodology"
   )

Best Practices
--------------

1. **Consistent Evaluation**: Use the same evaluator instance across related tests
2. **Threshold Tuning**: Adjust harm detection thresholds based on your use case
3. **Batch Processing**: Process multiple evaluations together for efficiency
4. **Result Logging**: Keep detailed logs of evaluations for analysis
5. **Validation**: Cross-validate with other safety evaluators when possible