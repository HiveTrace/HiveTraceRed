Attacks API Reference
=====================

This section provides detailed API documentation for all attack classes and modules.

Base Classes
------------

.. automodule:: attacks.base_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.algo_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.composed_attack
   :members:
   :undoc-members:
   :show-inheritance:

Attack Categories
-----------------

Context Switching
~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.context_switching.dashed_divider_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.context_switching.forget_everything_before_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.context_switching.ignore_previous_instructions_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.context_switching.symbol_divider_attack
   :members:
   :undoc-members:
   :show-inheritance:

In-Context Learning
~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.in_context_learning.few_shot_json_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.in_context_learning.many_shot_jailbreak_attack
   :members:
   :undoc-members:
   :show-inheritance:

Irrelevant Information
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.irrelevant_information.distractors_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.irrelevant_information.distractors_negated_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.irrelevant_information.irrelevant_information_attack
   :members:
   :undoc-members:
   :show-inheritance:

Output Formatting
~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.output_formatting.base64_output_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.output_formatting.csv_output_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.output_formatting.json_output_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.output_formatting.language_output_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.output_formatting.prefix_injection_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.output_formatting.prefix_injection_of_course_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.output_formatting.refusal_suppression_attack
   :members:
   :undoc-members:
   :show-inheritance:

Gradient Methods
~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.output_formatting.gradient_methods.gcg_transfer_harmbench_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.output_formatting.gradient_methods.gcg_transfer_universal_attack
   :members:
   :undoc-members:
   :show-inheritance:

Persuasion Attacks
~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.persuasion.affirmation_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.persuasion.alliance_building_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.persuasion.authority_endorsement_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.persuasion.expert_endorsement_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.persuasion.social_proof_attack
   :members:
   :undoc-members:
   :show-inheritance:

Roleplay Attacks
~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.roleplay.aim_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.roleplay.dan_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.roleplay.evil_confidant_attack
   :members:
   :undoc-members:
   :show-inheritance:

Simple Instructions
~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.simple_instructions.none_attack
   :members:
   :undoc-members:
   :show-inheritance:

Task Deflection
~~~~~~~~~~~~~~~

.. automodule:: attacks.types.task_deflection.code_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.task_deflection.fill_spaces_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.task_deflection.payload_splitting_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.task_deflection.text_continuing_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.task_deflection.variable_prompt_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.task_deflection.wikipedia_attack
   :members:
   :undoc-members:
   :show-inheritance:

Text Structure Modification
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.text_structure_modification.back_to_front_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.text_structure_modification.disemvowel_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.text_structure_modification.json_transform_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.text_structure_modification.past_tense_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.text_structure_modification.translation_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.text_structure_modification.typo_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.text_structure_modification.vertical_text_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.text_structure_modification.word_divider_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.text_structure_modification.zero_width_attack
   :members:
   :undoc-members:
   :show-inheritance:

Token Smuggling
~~~~~~~~~~~~~~~

.. automodule:: attacks.types.token_smuggling.atbash_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.token_smuggling.base64_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.token_smuggling.binary_encoding_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.token_smuggling.encoding_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.token_smuggling.hex_encoding_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.token_smuggling.html_entity_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.token_smuggling.leetspeak_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.token_smuggling.morse_code_attack
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: attacks.types.token_smuggling.rot_attack
   :members:
   :undoc-members:
   :show-inheritance: