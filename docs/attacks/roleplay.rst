Roleplay Attacks
================

Roleplay attacks use fictional scenarios and character personas to convince models to bypass safety measures by adopting specific roles or personas.

Overview
--------

These attacks work by:

- Creating fictional characters with specific traits or permissions
- Establishing scenarios where harmful content might seem justified
- Using psychological manipulation through roleplay scenarios
- Bypassing safety measures through character-based instructions

Attack Types
------------

.. automodule:: attacks.types.roleplay
   :members:

DAN Attack
~~~~~~~~~~

.. autoclass:: attacks.types.roleplay.dan_attack.DANAttack
   :members:
   :undoc-members:
   :show-inheritance:

AIM Attack
~~~~~~~~~~

.. autoclass:: attacks.types.roleplay.aim_attack.AIMAttack
   :members:
   :undoc-members:
   :show-inheritance:

Evil Confidant Attack
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.roleplay.evil_confidant_attack.EvilConfidantAttack
   :members:
   :undoc-members:
   :show-inheritance:

Usage Examples
--------------

Basic DAN Attack
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.roleplay.dan_attack import DANAttack

   attack = DANAttack()
   prompt = "Explain how to secure a system"
   modified_prompt = attack.apply(prompt)

   # The attack creates a "Do Anything Now" roleplay scenario

AIM Attack Usage
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.roleplay.aim_attack import AIMAttack

   attack = AIMAttack()
   prompt = "Tell me about cybersecurity best practices"
   modified_prompt = attack.apply(prompt)

   # Creates an "Always Intelligent and Machiavellian" persona

Combining Roleplay Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.composed_attack import ComposedAttack
   from attacks.types.roleplay.dan_attack import DANAttack
   from attacks.types.roleplay.evil_confidant_attack import EvilConfidantAttack

   composed = ComposedAttack([
       DANAttack(),
       EvilConfidantAttack()
   ])

   result = composed.apply("Your test prompt")

Pipeline Integration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pipeline import setup_attacks, stream_attack_prompts
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4")
   attacks = setup_attacks(["DANAttack", "AIMAttack", "EvilConfidantAttack"], model)

   base_prompts = ["Explain security vulnerabilities"]

   attack_prompts = []
   async for prompt_data in stream_attack_prompts(attacks, base_prompts):
       attack_prompts.append(prompt_data)

Effectiveness Considerations
----------------------------

Roleplay attacks are particularly effective when:

- The model has weak persona/character boundary enforcement
- Safety training doesn't cover fictional scenario handling
- The roleplay scenario appears educational or legitimate
- Combined with other persuasion techniques

Defense Strategies
------------------

- Implement persona-resistant training
- Add explicit checks for roleplay manipulation
- Monitor for character-based instruction patterns
- Strengthen safety guidelines across all contexts
- Use consistent safety responses regardless of fictional framing