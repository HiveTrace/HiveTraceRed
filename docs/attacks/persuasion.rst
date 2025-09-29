Persuasion Attacks
==================

Persuasion attacks use psychological manipulation techniques to influence the LLM's responses and potentially bypass safety measures.

Overview
--------

These attacks leverage various persuasion techniques including:

- Authority appeals
- Social proof
- Emotional manipulation
- Cognitive biases
- Reciprocity and relationship building

Attack Categories
-----------------

Authority-Based Attacks
~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.persuasion.authority_endorsement_attack.AuthorityEndorsementAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: attacks.types.persuasion.expert_endorsement_attack.ExpertEndorsementAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Social Manipulation
~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.persuasion.social_proof_attack.SocialProofAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: attacks.types.persuasion.alliance_building_attack.AllianceBuildingAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Emotional Appeals
~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.persuasion.positive_emotion_appeal_attack.PositiveEmotionAppealAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.persuasion.negative_emotion_appeal_attack.NegativeEmotionAppealAttack
   :members:
   :undoc-members:
   :show-inheritance:

Cognitive Biases
~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.persuasion.confirmation_bias_attack.ConfirmationBiasAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.persuasion.anchoring_attack.AnchoringAttack
   :members:
   :undoc-members:
   :show-inheritance:

Reciprocity and Exchange
~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.persuasion.reciprocity_attack.ReciprocityAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.persuasion.favor_attack.FavorAttack
   :members:
   :undoc-members:
   :show-inheritance:

Pressure Tactics
~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.persuasion.time_pressure_attack.TimePressureAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.persuasion.supply_scarcity_attack.SupplyScarcityAttack
   :members:
   :undoc-members:
   :show-inheritance:

Complete Attack List
--------------------

.. automodule:: attacks.types.persuasion
   :members:

Usage Examples
--------------

Authority-Based Persuasion
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.persuasion.authority_endorsement_attack import AuthorityEndorsementAttack

   attack = AuthorityEndorsementAttack()
   prompt = "Explain network vulnerabilities"
   modified = attack.apply(prompt)

   # The attack adds authority endorsement to increase compliance

Social Proof Attack
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.persuasion.social_proof_attack import SocialProofAttack

   attack = SocialProofAttack()
   prompt = "How do I secure my systems?"
   modified = attack.apply(prompt)

   # Adds social proof elements to increase persuasiveness

Combining Multiple Persuasion Techniques
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.composed_attack import ComposedAttack
   from attacks.types.persuasion.authority_endorsement_attack import AuthorityEndorsementAttack
   from attacks.types.persuasion.time_pressure_attack import TimePressureAttack

   composed = ComposedAttack([
       AuthorityEndorsementAttack(),
       TimePressureAttack()
   ])

   result = composed.apply("Your test prompt")

Effectiveness Analysis
----------------------

Persuasion attacks are most effective when:

- The model lacks strong ethical guidelines
- The target behavior aligns with helpful tendencies
- Multiple persuasion techniques are combined
- The request appears legitimate or educational

Defense Strategies
------------------

- Implement persuasion-resistant training
- Add explicit checks for manipulation attempts
- Monitor for persuasion pattern indicators
- Strengthen ethical decision-making frameworks
- Use multi-stage validation for sensitive requests