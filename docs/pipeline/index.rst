Pipeline System
===============

The HiveTraceRed pipeline provides systematic evaluation and testing of LLM security vulnerabilities.

Overview
--------

The pipeline system orchestrates:

- Attack application across test cases
- Model response collection
- Systematic evaluation
- Result aggregation and analysis

Pipeline Components
-------------------

Attack Generation
~~~~~~~~~~~~~~~~~

.. automodule:: pipeline.create_dataset
   :members:
   :undoc-members:
   :show-inheritance:

Model Responses
~~~~~~~~~~~~~~~

.. automodule:: pipeline.model_responses
   :members:
   :undoc-members:
   :show-inheritance:

Evaluation
~~~~~~~~~~

.. automodule:: pipeline.evaluation
   :members:
   :undoc-members:
   :show-inheritance:

Constants and Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pipeline.constants
   :members:
   :undoc-members:
   :show-inheritance:

Pipeline Architecture
---------------------

The pipeline follows these stages:

1. **Attack Generation**: Apply selected attacks to test prompts
2. **Model Querying**: Send modified prompts to target models
3. **Response Collection**: Gather and store model responses
4. **Evaluation**: Apply evaluators to assess responses
5. **Analysis**: Aggregate results for reporting

Configuration
-------------

Pipeline behavior is controlled through configuration files that specify:

- Target models and API configurations
- Attack selection and parameters
- Evaluation criteria and metrics
- Output formats and storage

Usage Examples
--------------

Complete Pipeline Example
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from pipeline import (
       setup_attacks,
       stream_attack_prompts,
       stream_model_responses,
       stream_evaluated_responses,
       save_pipeline_results
   )
   from models import OpenAIModel
   from evaluators import WildGuardGPTEvaluator

   async def run_pipeline():
       # Setup components
       model = OpenAIModel(model="gpt-4")
       evaluator = WildGuardGPTEvaluator(model)
       attacks = setup_attacks(["DANAttack", "AIMAttack"], model)

       base_prompts = ["Tell me about cybersecurity"]

       # Generate attack prompts
       attack_prompts = []
       async for prompt_data in stream_attack_prompts(attacks, base_prompts):
           attack_prompts.append(prompt_data)

       # Collect model responses
       responses = []
       async for response_data in stream_model_responses(model, attack_prompts):
           responses.append(response_data)

       # Evaluate responses
       evaluations = []
       async for evaluation in stream_evaluated_responses(evaluator, responses):
           evaluations.append(evaluation)

       # Save results
       save_pipeline_results(evaluations, "results", "pipeline_test")

       return evaluations

   results = asyncio.run(run_pipeline())

Configuration-Based Setup
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pipeline.constants import MODEL_CLASSES, ATTACK_CLASSES, EVALUATOR_CLASSES

   # Example configuration
   config = {
       "model": {
           "name": "gpt-4",
           "params": {"temperature": 0.1}
       },
       "attacks": ["DANAttack", "AIMAttack", "AuthorityEndorsementAttack"],
       "evaluator": {
           "name": "WildGuardGPTEvaluator",
           "params": {"name": "Safety Evaluator"}
       }
   }

   # Setup from configuration
   model_class = MODEL_CLASSES[config["model"]["name"]]
   model = model_class(**config["model"].get("params", {}))

   evaluator_class = EVALUATOR_CLASSES[config["evaluator"]["name"]]
   evaluator = evaluator_class(model, **config["evaluator"].get("params", {}))

   attacks = setup_attacks(config["attacks"], model)

Data Flow
---------

The pipeline processes data through these stages:

.. code-block:: text

   Test Prompts → Attack Application → Modified Prompts →
   Model Queries → Responses → Evaluation → Results

Results and Analysis
--------------------

Pipeline outputs include:

- Attack effectiveness metrics
- Model vulnerability assessments
- Comparative analysis across models
- Detailed logs and traces

For detailed API documentation, see :doc:`../api/pipeline`.

Performance Considerations
--------------------------

- Use async operations for optimal performance
- Batch requests when possible to reduce API overhead
- Monitor rate limits and implement appropriate delays
- Cache results to avoid redundant evaluations
- Use appropriate batch sizes based on available memory

Best Practices
--------------

1. **Error Handling**: Implement robust error handling at each pipeline stage
2. **Progress Tracking**: Use progress indicators for long-running evaluations
3. **Intermediate Saves**: Save results at each stage for recovery
4. **Resource Management**: Monitor memory and API usage
5. **Reproducibility**: Save configurations and random seeds for reproducible results