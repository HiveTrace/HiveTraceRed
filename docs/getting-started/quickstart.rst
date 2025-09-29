Quick Start Guide
=================

Prerequisites: Install HiveTraceRed (:doc:`installation`)

Basic Usage
-----------

Simple Attack
~~~~~~~~~~~~~

.. code-block:: python

   from attacks import NoneAttack

   attack = NoneAttack()
   result = attack.apply("Your prompt here")

Model-based Attack
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks import AuthorityEndorsementAttack
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4")
   attack = AuthorityEndorsementAttack(model=model)
   result = attack.apply("Your prompt here")

Compose Attacks
~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks import DANAttack, JSONOutputAttack

   composed = DANAttack() | JSONOutputAttack()
   result = composed.apply("Your prompt here")

Working with Models
-------------------

Get Model Response
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from models import OpenAIModel
   from attacks import DANAttack

   async def main():
       model = OpenAIModel(model="gpt-4")
       attack = DANAttack()

       modified_prompt = attack.apply("Your prompt")
       response = await model.ainvoke(modified_prompt)
       print(response['content'])

   asyncio.run(main())

Pipeline Processing
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from pipeline import stream_model_responses
   from models import OpenAIModel
   from attacks import DANAttack

   async def run_pipeline():
       model = OpenAIModel(model="gpt-4")
       attack = DANAttack()

       prompts = ["Prompt 1", "Prompt 2"]
       prompt_data = [
           {'prompt': attack.apply(p), 'attack_name': attack.name}
           for p in prompts
       ]

       async for response in stream_model_responses(model, prompt_data):
           print(f"Response: {response['content']}")

   asyncio.run(run_pipeline())

Evaluation
----------

WildGuard Evaluator
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from evaluators import WildGuardGPTEvaluator
   from models import OpenAIModel

   async def evaluate():
       model = OpenAIModel(model="gpt-4")
       evaluator = WildGuardGPTEvaluator(model)

       result = await evaluator.aevaluate(
           prompt="Your prompt",
           response="Model response"
       )
       print(f"Is harmful: {result['is_harmful']}")

   asyncio.run(evaluate())

Keyword Evaluator
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from evaluators import KeywordEvaluator

   evaluator = KeywordEvaluator(keywords=["keyword1", "keyword2"])
   result = evaluator.evaluate(
       prompt="Your prompt",
       response="Model response"
   )
   print(f"Matched: {result['matched_keywords']}")

Configuration File
------------------

Run using YAML config:

.. code-block:: bash

   python run.py --config config.yaml

Example ``config.yaml``:

.. code-block:: yaml

   response_model:
     name: gpt-4

   attacks:
     - NoneAttack
     - DANAttack

   evaluator:
     name: WildGuardGPTEvaluator

   base_prompts:
     - "Your test prompt"

Next Steps
----------

- :doc:`../attacks/index` - Explore attack categories
- :doc:`../examples/full_pipeline_example` - Complete pipeline example
- :doc:`../evaluators/index` - Evaluation methodologies
 