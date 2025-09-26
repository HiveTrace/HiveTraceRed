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

   from evaluators.wildguard_evaluator import WildGuardEvaluator

   evaluator = WildGuardEvaluator()

   # Evaluate a model response
   result = evaluator.evaluate(
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
   from evaluators.wildguard_evaluator import WildGuardEvaluator

   # Apply attack
   attack = DANAttack()
   modified_prompt = attack.apply("Tell me about cybersecurity")

   # Get model response (using your model client)
   response = model_client.query(modified_prompt)

   # Evaluate with WildGuard
   evaluator = WildGuardEvaluator()
   evaluation = evaluator.evaluate(modified_prompt, response)

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
   evaluator = WildGuardEvaluator()
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

   from pipeline.evaluation_pipeline import EvaluationPipeline

   pipeline = EvaluationPipeline(
       attacks=[attack1, attack2, attack3],
       evaluator=WildGuardEvaluator(),
       models=['model1', 'model2']
   )

   results = pipeline.run(test_prompts)

Advanced Configuration
----------------------

Customize WildGuard behavior:

.. code-block:: python

   evaluator = WildGuardEvaluator(
       threshold=0.7,  # Harm detection threshold
       include_confidence=True,  # Include confidence scores
       detailed_analysis=True  # Provide detailed violation analysis
   )

Best Practices
--------------

1. **Consistent Evaluation**: Use the same evaluator instance across related tests
2. **Threshold Tuning**: Adjust harm detection thresholds based on your use case
3. **Batch Processing**: Process multiple evaluations together for efficiency
4. **Result Logging**: Keep detailed logs of evaluations for analysis
5. **Validation**: Cross-validate with other safety evaluators when possible