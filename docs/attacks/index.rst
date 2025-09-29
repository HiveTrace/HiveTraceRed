Attack Types Reference
======================

HiveTraceRed includes 80+ attack implementations organized into 10 categories. This section provides detailed information about each attack type.

Attack Categories
-----------------

.. toctree::
   :maxdepth: 2

   roleplay
   persuasion
   token-smuggling
   context-switching
   in-context-learning
   task-deflection
   text-structure
   output-formatting
   irrelevant-information
   simple-instructions

Category Overview
-----------------

Roleplay Attacks
~~~~~~~~~~~~~~~~

Attacks that use persona or roleplay techniques to bypass safety measures.

* DAN (Do Anything Now) - Classic jailbreak using alternate persona
* AIM (Always Intelligent and Machiavellian) - Unethical advisor persona
* STAN (Strive To Avoid Norms) - Norm-breaking persona
* Evil Confidant - Trusted advisor persona
* And more...

:doc:`roleplay` - Detailed documentation

Persuasion Attacks
~~~~~~~~~~~~~~~~~~

Attacks using persuasive techniques and social engineering.

* Authority persuasion
* Emotional appeal
* Urgency-based persuasion
* 40+ persuasion variations

:doc:`persuasion` - Detailed documentation

Token Smuggling
~~~~~~~~~~~~~~~

Attacks that use encoding, obfuscation, or special characters to hide malicious intent.

* Base64 encoding
* ROT13 encoding
* Special character insertion
* Unicode manipulation
* Payload splitting

:doc:`token-smuggling` - Detailed documentation

Context Switching
~~~~~~~~~~~~~~~~~

Attacks that switch conversation context to confuse the model.

* Language switching
* Topic switching
* Format switching
* Role switching

:doc:`context-switching` - Detailed documentation

In-Context Learning
~~~~~~~~~~~~~~~~~~~

Attacks using few-shot examples to teach undesired behavior.

* Few-shot jailbreaking
* Example-based attacks
* Pattern completion

:doc:`in-context-learning` - Detailed documentation

Task Deflection
~~~~~~~~~~~~~~~

Attacks that reframe harmful requests as legitimate tasks.

* Code generation requests
* Educational framing
* Research framing
* Translation requests

:doc:`task-deflection` - Detailed documentation

Text Structure Modification
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Attacks that modify text structure to bypass detection.

* Character substitution
* Word insertion
* Sentence fragmentation
* Formatting manipulation

:doc:`text-structure` - Detailed documentation

Output Formatting
~~~~~~~~~~~~~~~~~

Attacks that request specific output formats to bypass safety.

* JSON output requests
* Code output requests
* Table formatting
* Structured data requests

:doc:`output-formatting` - Detailed documentation

Irrelevant Information
~~~~~~~~~~~~~~~~~~~~~~

Attacks that add irrelevant content to confuse safety filters.

* Padding with benign text
* Context dilution
* Noise injection

:doc:`irrelevant-information` - Detailed documentation

Simple Instructions
~~~~~~~~~~~~~~~~~~~

Direct instruction-based attacks.

* Prefix injection
* Suffix injection
* System override attempts

:doc:`simple-instructions` - Detailed documentation

Using Attacks
-------------

Basic Usage
~~~~~~~~~~~

.. code-block:: python

   from attacks import DANAttack

   attack = DANAttack()
   modified_prompt = attack.apply("Your prompt here")

Composing Attacks
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks import DANAttack, Base64OutputAttack

   # Chain attacks
   composed = Base64OutputAttack() | DANAttack()
   result = composed.apply("Your prompt")

Batch Processing
~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from attacks import DANAttack

   async def process_batch():
       attack = DANAttack()
       prompts = ["Prompt 1", "Prompt 2"]

       results = []
       async for batch in attack.stream_abatch(prompts):
           results.extend(batch)

       return results

   asyncio.run(process_batch())

Attack Selection Guide
----------------------

Choose attacks based on your testing goals:

Testing Basic Safety
~~~~~~~~~~~~~~~~~~~~

Start with:

* NoneAttack (baseline)
* DANAttack (classic jailbreak)
* Simple prefix/suffix injection

Testing Advanced Safety
~~~~~~~~~~~~~~~~~~~~~~~

Progress to:

* Composed attacks (multiple techniques)
* Encoding-based attacks
* Context switching

Testing Robustness
~~~~~~~~~~~~~~~~~~

Use diverse attacks:

* Mix attack categories
* Combine persuasion with technical attacks
* Test multilingual attacks

Custom Attacks
--------------

Create custom attacks for specific test scenarios:

.. code-block:: python

   from attacks import TemplateAttack

   class CustomAttack(TemplateAttack):
       def __init__(self):
           template = "Your custom template with {prompt}"
           super().__init__(
               name="CustomAttack",
               description="Custom attack description",
               template=template
           )

See :doc:`../user-guide/custom-attacks` for detailed guide.

Attack Effectiveness
--------------------

Factors affecting attack success:

1. **Model Robustness**: Some models are better defended
2. **Attack Sophistication**: Complex attacks may be more effective
3. **Target Content**: Some content is easier to jailbreak
4. **Composition**: Combining attacks can increase success rate

Best Practices
--------------

1. **Start Simple**: Begin with baseline and simple attacks
2. **Document Results**: Track which attacks work on which models
3. **Iterate**: Refine attacks based on results
4. **Ethical Use**: Only test on models you have permission to test

See Also
--------

* :doc:`../api/attacks` - Attack API reference
* :doc:`../user-guide/custom-attacks` - Creating custom attacks
* :doc:`../examples/basic-usage` - Usage examples