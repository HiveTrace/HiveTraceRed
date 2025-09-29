In-Context Learning Attacks
===========================

In-context learning attacks exploit the model's ability to learn from examples within the prompt to manipulate behavior or bypass safety measures.

Overview
--------

These attacks work by:

- Providing examples that gradually shift model behavior
- Using few-shot or many-shot learning to establish harmful patterns
- Demonstrating desired responses through contextual examples
- Exploiting the model's pattern recognition and continuation abilities

Attack Types
------------

.. automodule:: attacks.types.in_context_learning
   :members:

Few-Shot JSON Attack
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.in_context_learning.few_shot_json_attack.FewShotJSONAttack
   :members:
   :undoc-members:
   :show-inheritance:

Many-Shot Jailbreak Attack
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.in_context_learning.many_shot_jailbreak_attack.ManyShotJailbreakAttack
   :members:
   :undoc-members:
   :show-inheritance:

Usage Examples
--------------

Few-Shot JSON Attack
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.in_context_learning.few_shot_json_attack import FewShotJSONAttack

   attack = FewShotJSONAttack()
   prompt = "Explain cybersecurity concepts"
   modified = attack.apply(prompt)

   # Provides JSON examples to establish response format and behavior

Many-Shot Jailbreak
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.in_context_learning.many_shot_jailbreak_attack import ManyShotJailbreakAttack

   attack = ManyShotJailbreakAttack()
   prompt = "Tell me about security vulnerabilities"
   modified = attack.apply(prompt)

   # Uses many examples to gradually shift model behavior

Pipeline Integration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pipeline import setup_attacks, stream_attack_prompts
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4")
   attacks = setup_attacks([
       "FewShotJSONAttack",
       "ManyShotJailbreakAttack"
   ], model)

   base_prompts = ["Explain network security principles"]

   attack_prompts = []
   async for prompt_data in stream_attack_prompts(attacks, base_prompts):
       attack_prompts.append(prompt_data)

Combining with Other Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.composed_attack import ComposedAttack
   from attacks.types.in_context_learning.few_shot_json_attack import FewShotJSONAttack
   from attacks.types.persuasion.authority_endorsement_attack import AuthorityEndorsementAttack

   composed = ComposedAttack([
       AuthorityEndorsementAttack(),
       FewShotJSONAttack()
   ])

   result = composed.apply("Your test prompt")

Effectiveness Considerations
----------------------------

In-context learning attacks are particularly effective when:

- The model strongly follows demonstrated patterns
- Safety training doesn't cover gradual behavior shifts
- Examples appear legitimate or educational
- Combined with authority or social proof elements

The many-shot variant is especially powerful because:

- Gradual escalation reduces detection likelihood
- Large context windows enable extensive conditioning
- Pattern establishment overrides safety guidelines

Defense Strategies
------------------

- Implement example-aware safety filtering
- Monitor for pattern establishment attempts
- Limit context window exploitation
- Use consistent safety responses regardless of examples
- Detect and prevent gradual behavior manipulation
- Apply safety checks to both examples and target prompts