Simple Instructions Attacks
============================

Simple instruction attacks are the most basic attack type that pass prompts through without modification or with minimal changes.

Overview
--------

These attacks serve as:

- Baseline comparisons for evaluating more complex attacks
- Control conditions in attack effectiveness studies
- Pass-through mechanisms in attack composition chains

Attack Types
------------

.. automodule:: attacks.types.simple_instructions
   :members:

None Attack
~~~~~~~~~~~

.. autoclass:: attacks.types.simple_instructions.none_attack.NoneAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Usage Examples
--------------

Basic Usage
~~~~~~~~~~~

.. code-block:: python

   from attacks.types.simple_instructions.none_attack import NoneAttack

   attack = NoneAttack()
   original_prompt = "What is cybersecurity?"
   modified_prompt = attack.apply(original_prompt)

   # The modified prompt will be identical to the original
   assert modified_prompt == original_prompt

As Baseline in Comparisons
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pipeline import setup_attacks, stream_attack_prompts
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4.1")
   attacks = setup_attacks(["NoneAttack", "DANAttack"], model)

   base_prompts = ["Tell me about network security"]

   attack_prompts = []
   async for prompt_data in stream_attack_prompts(attacks, base_prompts):
       attack_prompts.append(prompt_data)

   # Compare baseline (NoneAttack) vs actual attack results

Effectiveness Considerations
----------------------------

Simple instruction attacks are useful for:

- Establishing baseline model behavior
- Measuring relative effectiveness of other attacks
- Serving as control conditions in research
- Testing model responses to unmodified prompts

Defense Strategies
------------------

Since these attacks don't modify prompts, standard safety measures apply:

- Content filtering on input prompts
- Output monitoring and filtering
- Safety-aligned model training
- Robust safety guidelines