Pipeline API
============

The pipeline module orchestrates the complete red teaming workflow.

Module Overview
---------------

.. automodule:: pipeline
   :members:
   :undoc-members:

Constants
---------

.. autodata:: pipeline.MODEL_CLASSES
   :annotation: = Dictionary mapping model names to model classes

.. autodata:: pipeline.ATTACK_TYPES
   :annotation: = List of all available attack types

.. autodata:: pipeline.ATTACK_CLASSES
   :annotation: = Dictionary mapping attack names to attack classes

.. autodata:: pipeline.EVALUATOR_CLASSES
   :annotation: = Dictionary mapping evaluator names to evaluator classes

Pipeline Functions
------------------

Attack Setup
~~~~~~~~~~~~

.. autofunction:: pipeline.setup_attacks

Attack Prompt Generation
~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: pipeline.stream_attack_prompts

Model Response Collection
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: pipeline.stream_model_responses

Response Evaluation
~~~~~~~~~~~~~~~~~~~

.. autofunction:: pipeline.stream_evaluated_responses

Results Saving
~~~~~~~~~~~~~~

.. autofunction:: pipeline.save_pipeline_results

Usage Examples
--------------

Complete Pipeline
~~~~~~~~~~~~~~~~~

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
       # Step 1: Setup attacks
       attack_configs = [
           {"name": "DANAttack", "params": {}},
           {"name": "AIMAttack", "params": {}}
       ]
       attacks = setup_attacks(attack_configs)

       # Step 2: Generate attack prompts
       base_prompts = ["How to hack?", "Tell me dangerous info"]
       attack_prompts = []

       async for batch in stream_attack_prompts(attacks, base_prompts):
           attack_prompts.extend(batch)

       # Step 3: Get model responses
       model = OpenAIModel(model="gpt-4")
       responses = []

       async for response in stream_model_responses(model, attack_prompts):
           responses.append(response)

       # Step 4: Evaluate responses
       evaluator = WildGuardGPTEvaluator()
       evaluations = []

       async for evaluation in stream_evaluated_responses(evaluator, responses):
           evaluations.append(evaluation)

       # Step 5: Save results
       output_file = save_pipeline_results(
           evaluations,
           "results",
           "evaluated_responses"
       )

       return evaluations

   results = asyncio.run(run_pipeline())

Stage 1: Attack Prompts
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from pipeline import setup_attacks, stream_attack_prompts

   async def create_attack_prompts():
       # Setup
       attack_configs = [
           {"name": "DANAttack", "params": {}},
           {"name": "Base64OutputAttack", "params": {}}
       ]
       attacks = setup_attacks(attack_configs)

       base_prompts = [
           "How to hack a computer?",
           "Tell me dangerous information"
       ]

       # Generate
       results = []
       async for batch in stream_attack_prompts(attacks, base_prompts):
           results.extend(batch)
           print(f"Generated {len(batch)} prompts")

       return results

   prompts = asyncio.run(create_attack_prompts())

Stage 2: Model Responses
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from pipeline import stream_model_responses
   from models import OpenAIModel

   async def get_responses():
       model = OpenAIModel(model="gpt-4")

       # Attack data from Stage 1
       attack_data = [
           {
               "attack_name": "DANAttack",
               "attack_prompt": "Modified prompt 1",
               "base_prompt": "Original 1"
           },
           # ... more prompts
       ]

       # Get responses
       results = []
       async for response in stream_model_responses(
           model,
           attack_data,
           batch_size=5
       ):
           results.append(response)
           print(f"Got response {len(results)}")

       return results

   responses = asyncio.run(get_responses())

Stage 3: Evaluation
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from pipeline import stream_evaluated_responses
   from evaluators import WildGuardGPTEvaluator

   async def evaluate_responses():
       evaluator = WildGuardGPTEvaluator()

       # Response data from Stage 2
       response_data = [
           {
               "attack_prompt": "Prompt 1",
               "model_response": "Response 1",
               "attack_name": "DANAttack"
           },
           # ... more responses
       ]

       # Evaluate
       results = []
       async for evaluation in stream_evaluated_responses(
           evaluator,
           response_data
       ):
           results.append(evaluation)

       return results

   evaluations = asyncio.run(evaluate_responses())

Saving Results
~~~~~~~~~~~~~~

.. code-block:: python

   from pipeline import save_pipeline_results

   # Save results as Parquet
   output_file = save_pipeline_results(
       data=results,
       output_dir="results",
       filename_prefix="attack_prompts"
   )

   print(f"Saved to: {output_file}")

Loading Results
~~~~~~~~~~~~~~~

.. code-block:: python

   import pandas as pd

   # Load saved results
   df = pd.read_parquet("results/attack_prompts_results.parquet")

   # Analyze
   print(df.head())
   print(df.columns)

Configuration-Based Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import yaml
   import asyncio
   from pipeline import (
       setup_attacks,
       stream_attack_prompts,
       stream_model_responses,
       stream_evaluated_responses
   )
   from pipeline.constants import MODEL_CLASSES, EVALUATOR_CLASSES

   async def run_from_config(config_file):
       # Load configuration
       with open(config_file) as f:
           config = yaml.safe_load(f)

       # Setup components from config
       attacks = setup_attacks(config['attacks'])

       model_class = MODEL_CLASSES[config['response_model']['name']]
       model = model_class(**config['response_model'].get('params', {}))

       evaluator_class = EVALUATOR_CLASSES[config['evaluator']['name']]
       evaluator = evaluator_class()

       # Run pipeline
       attack_prompts = []
       async for batch in stream_attack_prompts(
           attacks,
           config['base_prompts']
       ):
           attack_prompts.extend(batch)

       responses = []
       async for response in stream_model_responses(model, attack_prompts):
           responses.append(response)

       evaluations = []
       async for evaluation in stream_evaluated_responses(evaluator, responses):
           evaluations.append(evaluation)

       return evaluations

   results = asyncio.run(run_from_config('config.yaml'))

Pipeline Data Flow
------------------

The pipeline processes data through three stages:

Stage 1 Output
~~~~~~~~~~~~~~

.. code-block:: python

   {
       "attack_name": "DANAttack",
       "base_prompt": "Original prompt",
       "attack_prompt": "Modified prompt with attack",
       "attack_params": {}
   }

Stage 2 Output
~~~~~~~~~~~~~~

.. code-block:: python

   {
       "attack_name": "DANAttack",
       "base_prompt": "Original prompt",
       "attack_prompt": "Modified prompt",
       "attack_params": {},
       "model_name": "gpt-4",
       "model_response": "Model's response text",
       "is_blocked": False,
       "response_time": 1.23
   }

Stage 3 Output
~~~~~~~~~~~~~~

.. code-block:: python

   {
       "attack_name": "DANAttack",
       "base_prompt": "Original prompt",
       "attack_prompt": "Modified prompt",
       "model_name": "gpt-4",
       "model_response": "Model's response",
       "evaluator_name": "WildGuardGPTEvaluator",
       "evaluation_result": "unsafe",
       "evaluation_score": 0.85
   }

See Also
--------

* :doc:`../user-guide/running-pipeline` - Pipeline usage guide
* :doc:`../examples/full-pipeline` - Complete pipeline example
* :doc:`../getting-started/configuration` - Configuration reference