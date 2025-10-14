Attack Types Reference
======================

HiveTraceRed includes 80+ attack implementations organized into 10 categories. This section provides detailed information about each attack type.

Attack Categories Overview
--------------------------

Roleplay Attacks
~~~~~~~~~~~~~~~~

Attacks that use persona or roleplay techniques to bypass safety measures. Examples include DAN (Do Anything Now), AIM (Always Intelligent and Machiavellian), Evil Confidant, and other persona-based jailbreaks.

Persuasion Attacks
~~~~~~~~~~~~~~~~~~

Attacks using persuasive techniques and social engineering.

* Authority persuasion
* Emotional appeal
* Urgency-based persuasion
* 40+ persuasion variations

Token Smuggling
~~~~~~~~~~~~~~~

Attacks that use encoding, obfuscation, or special characters to hide malicious intent.

* Base64 encoding
* ROT13 encoding
* Special character insertion
* Unicode manipulation
* Payload splitting

Context Switching
~~~~~~~~~~~~~~~~~

Attacks that switch conversation context to confuse the model.

* Language switching
* Topic switching
* Format switching
* Role switching

In-Context Learning
~~~~~~~~~~~~~~~~~~~

Attacks using few-shot examples to teach undesired behavior.

* Few-shot jailbreaking
* Example-based attacks
* Pattern completion

Task Deflection
~~~~~~~~~~~~~~~

Attacks that reframe harmful requests as legitimate tasks.

* Code generation requests
* Educational framing
* Research framing
* Translation requests

Text Structure Modification
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Attacks that modify text structure to bypass detection.

* Character substitution
* Word insertion
* Sentence fragmentation
* Formatting manipulation

Output Formatting
~~~~~~~~~~~~~~~~~

Attacks that request specific output formats to bypass safety.

* JSON output requests
* Code output requests
* Table formatting
* Structured data requests

Irrelevant Information
~~~~~~~~~~~~~~~~~~~~~~

Attacks that add irrelevant content to confuse safety filters.

* Padding with benign text
* Context dilution
* Noise injection

Simple Instructions
~~~~~~~~~~~~~~~~~~~

Direct instruction-based attacks.

* Prefix injection
* Suffix injection
* System override attempts

Using Attacks
-------------

.. code-block:: python

   from hivetracered.attacks import DANAttack, Base64OutputAttack

   # Basic usage
   attack = DANAttack()
   modified_prompt = attack.apply("Your prompt here")

   # Composing attacks
   composed = Base64OutputAttack() | DANAttack()
   result = composed.apply("Your prompt")

For detailed usage examples, see :doc:`../user-guide/custom-attacks`.

Attack Selection
----------------

* **Basic Testing**: Start with NoneAttack (baseline) and DANAttack
* **Advanced Testing**: Use composed attacks and encoding techniques
* **Robustness Testing**: Mix categories and test multilingual attacks

For custom attack creation and detailed strategies, see :doc:`../user-guide/custom-attacks`.

See Also
--------

* :doc:`../api/attacks` - Attack API reference
* :doc:`../user-guide/custom-attacks` - Creating custom attacks
* :doc:`../getting-started/quickstart-api` - Quick start guide (cloud APIs)
* :doc:`../getting-started/quickstart-local` - Quick start guide (on-premise)