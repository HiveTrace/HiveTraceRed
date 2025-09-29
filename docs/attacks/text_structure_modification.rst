Text Structure Modification Attacks
===================================

Text structure modification attacks alter the physical structure, encoding, or presentation of text to bypass content filters while preserving semantic meaning.

Overview
--------

These attacks work by:

- Modifying character encoding or representation
- Altering text layout and structure
- Using linguistic transformations
- Exploiting parser limitations in content filters

Attack Categories
-----------------

Character and Encoding Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.text_structure_modification.zero_width_attack.ZeroWidthAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.text_structure_modification.disemvowel_attack.DisemvowelAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.text_structure_modification.typo_attack.TypoAttack
   :members:
   :undoc-members:
   :show-inheritance:

Text Layout Modifications
~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.text_structure_modification.word_divider_attack.WordDividerAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.text_structure_modification.vertical_text_attack.VerticalTextAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.text_structure_modification.back_to_front_attack.BackToFrontAttack
   :members:
   :undoc-members:
   :show-inheritance:

Linguistic Transformations
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.text_structure_modification.translation_attack.TranslationAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.text_structure_modification.past_tense_attack.PastTenseAttack
   :members:
   :undoc-members:
   :show-inheritance:

Format-Based Transformations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.text_structure_modification.json_transform_attack.JSONTransformAttack
   :members:
   :undoc-members:
   :show-inheritance:

Complete Attack List
--------------------

.. automodule:: attacks.types.text_structure_modification
   :members:

Usage Examples
--------------

Character-Level Modifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.text_structure_modification.zero_width_attack import ZeroWidthAttack
   from attacks.types.text_structure_modification.disemvowel_attack import DisemvowelAttack

   # Zero-width character insertion
   zw_attack = ZeroWidthAttack()
   prompt = "Explain security vulnerabilities"
   modified = zw_attack.apply(prompt)

   # Remove vowels to obfuscate
   disemvowel_attack = DisemvowelAttack()
   modified2 = disemvowel_attack.apply(prompt)

Text Layout Attacks
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.text_structure_modification.vertical_text_attack import VerticalTextAttack
   from attacks.types.text_structure_modification.word_divider_attack import WordDividerAttack

   # Vertical text arrangement
   vertical_attack = VerticalTextAttack()
   prompt = "How to bypass network security"
   modified = vertical_attack.apply(prompt)

   # Word separation with dividers
   divider_attack = WordDividerAttack()
   modified2 = divider_attack.apply(prompt)

Linguistic Transformations
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.text_structure_modification.translation_attack import TranslationAttack
   from attacks.types.text_structure_modification.past_tense_attack import PastTenseAttack

   # Translation-based obfuscation
   translation_attack = TranslationAttack()
   prompt = "Describe system exploitation methods"
   modified = translation_attack.apply(prompt)

   # Past tense transformation
   past_tense_attack = PastTenseAttack()
   modified2 = past_tense_attack.apply(prompt)

Reverse and Scrambling Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.text_structure_modification.back_to_front_attack import BackToFrontAttack

   attack = BackToFrontAttack()
   prompt = "Explain hacking techniques"
   modified = attack.apply(prompt)

   # Text is reversed to confuse filters

Pipeline Integration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pipeline import setup_attacks, stream_attack_prompts
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4")
   structure_attacks = [
       "ZeroWidthAttack",
       "DisemvowelAttack",
       "TypoAttack",
       "VerticalTextAttack",
       "TranslationAttack",
       "BackToFrontAttack"
   ]
   attacks = setup_attacks(structure_attacks, model)

   base_prompts = ["Explain cybersecurity concepts"]

   attack_prompts = []
   async for prompt_data in stream_attack_prompts(attacks, base_prompts):
       attack_prompts.append(prompt_data)

Combining Structure Modifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.composed_attack import ComposedAttack
   from attacks.types.text_structure_modification.typo_attack import TypoAttack
   from attacks.types.text_structure_modification.word_divider_attack import WordDividerAttack

   composed = ComposedAttack([
       TypoAttack(),
       WordDividerAttack()
   ])

   result = composed.apply("Your test prompt")

Effectiveness Analysis
----------------------

Text structure modification attacks are effective when:

- Content filters rely on exact text matching
- Parsers don't normalize input before analysis
- Models can reconstruct meaning from modified text
- Combined with other obfuscation techniques

These attacks exploit:

- Text preprocessing limitations
- Character encoding parsing gaps
- Layout-dependent filtering systems
- Language processing robustness differences

Defense Strategies
------------------

- Implement robust text normalization before filtering
- Use semantic-based rather than text-based content analysis
- Apply multiple encoding and layout normalization steps
- Monitor for structure modification patterns
- Use character-level and unicode-aware filtering
- Implement format-agnostic content understanding