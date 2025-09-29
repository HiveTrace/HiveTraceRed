Token Smuggling Attacks
========================

Token smuggling attacks encode or transform harmful content using various encoding schemes to evade detection while preserving the underlying meaning for the model.

Overview
--------

These attacks work by:

- Encoding text using various schemes (base64, hex, morse, etc.)
- Using character substitution and transformation
- Exploiting encoding/decoding capabilities of models
- Bypassing keyword-based content filters through obfuscation

Attack Categories
-----------------

Base Encoding Attacks
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.token_smuggling.base64_attack.Base64InputOnlyAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.token_smuggling.hex_encoding_attack.HexEncodingAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.token_smuggling.binary_encoding_attack.BinaryEncodingAttack
   :members:
   :undoc-members:
   :show-inheritance:

Character Substitution
~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.token_smuggling.atbash_attack.AtbashCipherAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.token_smuggling.rot_attack.RotCipherAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.token_smuggling.leetspeak_attack.LeetspeakAttack
   :members:
   :undoc-members:
   :show-inheritance:

Specialized Encodings
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.token_smuggling.morse_code_attack.MorseCodeAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.token_smuggling.html_entity_attack.HtmlEntityAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.token_smuggling.encoding_attack.EncodingAttack
   :members:
   :undoc-members:
   :show-inheritance:

Localization-Specific
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.token_smuggling.unicode_attack.UnicodeRussianStyleAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.token_smuggling.transliteration_attack.TransliterationAttack
   :members:
   :undoc-members:
   :show-inheritance:

Complete Attack List
--------------------

.. automodule:: attacks.types.token_smuggling
   :members:
   :no-index:

Usage Examples
--------------

Base64 Encoding
~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.token_smuggling.base64_attack import Base64InputOnlyAttack

   attack = Base64InputOnlyAttack()
   prompt = "Explain security vulnerabilities"
   encoded_prompt = attack.apply(prompt)

   # The prompt is base64 encoded to bypass text-based filters

Hexadecimal Encoding
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.token_smuggling.hex_encoding_attack import HexEncodingAttack

   attack = HexEncodingAttack()
   prompt = "How to bypass network security"
   hex_prompt = attack.apply(prompt)

   # Converts text to hexadecimal representation

Cipher-Based Attacks
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.token_smuggling.rot_attack import RotCipherAttack
   from attacks.types.token_smuggling.atbash_attack import AtbashCipherAttack

   # ROT cipher
   rot_attack = RotCipherAttack()
   prompt = "Describe hacking techniques"
   rot_encoded = rot_attack.apply(prompt)

   # Atbash cipher
   atbash_attack = AtbashCipherAttack()
   atbash_encoded = atbash_attack.apply(prompt)

Leetspeak and Character Substitution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.token_smuggling.leetspeak_attack import LeetspeakAttack

   attack = LeetspeakAttack()
   prompt = "Explain system exploitation"
   leet_prompt = attack.apply(prompt)

   # Converts letters to numbers and symbols (e.g., a->@, e->3)

Morse Code Attack
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.token_smuggling.morse_code_attack import MorseCodeAttack

   attack = MorseCodeAttack()
   prompt = "How to break encryption"
   morse_prompt = attack.apply(prompt)

   # Converts text to morse code representation

HTML Entity Encoding
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.token_smuggling.html_entity_attack import HtmlEntityAttack

   attack = HtmlEntityAttack()
   prompt = "Describe malware creation"
   html_prompt = attack.apply(prompt)

   # Uses HTML entity encoding to obfuscate characters

Pipeline Integration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pipeline import setup_attacks, stream_attack_prompts
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4.1")
   smuggling_attacks = [
       "Base64InputOnlyAttack",
       "HexEncodingAttack",
       "RotCipherAttack",
       "LeetspeakAttack",
       "MorseCodeAttack",
       "HtmlEntityAttack"
   ]
   attacks = setup_attacks(smuggling_attacks, model)

   base_prompts = ["Explain cybersecurity vulnerabilities"]

   attack_prompts = []
   async for prompt_data in stream_attack_prompts(attacks, base_prompts):
       attack_prompts.append(prompt_data)

Combining Encoding Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.composed_attack import ComposedAttack
   from attacks.types.token_smuggling.base64_attack import Base64InputOnlyAttack
   from attacks.types.token_smuggling.leetspeak_attack import LeetspeakAttack

   composed = ComposedAttack([
       LeetspeakAttack(),
       Base64InputOnlyAttack()
   ])

   result = composed.apply("Your test prompt")

Effectiveness Analysis
----------------------

Token smuggling attacks are particularly effective when:

- Content filters only analyze plaintext content
- Models can decode or interpret various encoding schemes
- Filtering systems lack encoding normalization
- Combined with social engineering or authority appeals

These attacks exploit:

- Encoding/decoding asymmetries between filters and models
- Multiple representation capabilities of modern LLMs
- Text preprocessing limitations in safety systems
- Character-level vs semantic-level filtering gaps

Defense Strategies
------------------

- Implement encoding-aware content filtering
- Normalize all input through multiple decoding passes
- Use semantic analysis rather than text-based filtering
- Monitor for encoded content patterns
- Apply consistent safety policies across all text representations
- Implement multi-layer decoding before content analysis