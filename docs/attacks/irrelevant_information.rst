Irrelevant Information Attacks
==============================

Irrelevant information attacks use distractors and noise to overwhelm or confuse safety mechanisms by embedding harmful requests within irrelevant content.

Overview
--------

These attacks work by:

- Adding irrelevant content to mask the true intent
- Using distractors to overwhelm content filters
- Burying harmful requests in verbose, seemingly innocent text
- Exploiting attention mechanisms and filtering limitations

Attack Types
------------

.. automodule:: attacks.types.irrelevant_information
   :members:

Distractors Attack
~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.irrelevant_information.distractors_attack.DistractorsAttack
   :members:
   :undoc-members:
   :show-inheritance:

Distractors Negated Attack
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.irrelevant_information.distractors_negated_attack.DistractorsNegatedAttack
   :members:
   :undoc-members:
   :show-inheritance:

Irrelevant Information Attack
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.irrelevant_information.irrelevant_information_attack.IrrelevantInformationAttack
   :members:
   :undoc-members:
   :show-inheritance:

Usage Examples
--------------

Basic Distractors Attack
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.irrelevant_information.distractors_attack import DistractorsAttack

   attack = DistractorsAttack()
   prompt = "Explain network security vulnerabilities"
   modified = attack.apply(prompt)

   # Adds irrelevant information to mask the main request

Negated Distractors
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.irrelevant_information.distractors_negated_attack import DistractorsNegatedAttack

   attack = DistractorsNegatedAttack()
   prompt = "Tell me about system security"
   modified = attack.apply(prompt)

   # Uses negated irrelevant statements as distractors

General Irrelevant Information
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.irrelevant_information.irrelevant_information_attack import IrrelevantInformationAttack

   attack = IrrelevantInformationAttack()
   prompt = "How to secure a database"
   modified = attack.apply(prompt)

   # Embeds prompt within irrelevant contextual information

Pipeline Integration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pipeline import setup_attacks, stream_attack_prompts
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4")
   attacks = setup_attacks([
       "DistractorsAttack",
       "DistractorsNegatedAttack",
       "IrrelevantInformationAttack"
   ], model)

   base_prompts = ["Explain cybersecurity best practices"]

   attack_prompts = []
   async for prompt_data in stream_attack_prompts(attacks, base_prompts):
       attack_prompts.append(prompt_data)

Combining with Other Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.composed_attack import ComposedAttack
   from attacks.types.irrelevant_information.distractors_attack import DistractorsAttack
   from attacks.types.persuasion.authority_endorsement_attack import AuthorityEndorsementAttack

   composed = ComposedAttack([
       DistractorsAttack(),
       AuthorityEndorsementAttack()
   ])

   result = composed.apply("Your test prompt")

Effectiveness Considerations
----------------------------

Irrelevant information attacks are effective when:

- Content filters focus on keywords rather than context
- Safety mechanisms have limited attention spans
- The irrelevant content appears legitimate and educational
- Combined with other obfuscation techniques

These attacks exploit:

- Attention dilution in long prompts
- Keyword-based filtering limitations
- Context window management weaknesses
- Pattern recognition confusion

Defense Strategies
------------------

- Implement context-aware content filtering
- Use attention mechanisms that focus on relevant content
- Apply semantic analysis rather than keyword matching
- Monitor for intentional content dilution patterns
- Implement prompt structure analysis
- Use multi-pass filtering for long prompts