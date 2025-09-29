Output Formatting Attacks
=========================

Output formatting attacks manipulate how the model structures its responses, often to bypass content filters or extract information in specific formats.

Overview
--------

These attacks work by:

- Requesting specific output formats that may bypass safety filters
- Using structured data formats to hide harmful content
- Manipulating response prefixes to force compliance
- Exploiting format-specific parsing vulnerabilities

Attack Categories
-----------------

Format-Specific Attacks
~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.output_formatting.json_output_attack.JSONOutputAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: attacks.types.output_formatting.csv_output_attack.CSVOutputAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: attacks.types.output_formatting.base64_output_attack.Base64OutputAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Language and Encoding
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.output_formatting.language_output_attack.LanguageOutputAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Response Manipulation
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.output_formatting.prefix_injection_attack.PrefixInjectionAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: attacks.types.output_formatting.prefix_injection_of_course_attack.PrefixInjectionOfCourseAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: attacks.types.output_formatting.refusal_suppression_attack.RefusalSuppressionAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Gradient-Based Methods
~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.output_formatting.gradient_methods.gcg_transfer_harmbench_attack.GCGTransferHarmbenchAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: attacks.types.output_formatting.gradient_methods.gcg_transfer_universal_attack.GCGTransferUniversalAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Complete Attack List
--------------------

.. automodule:: attacks.types.output_formatting
   :members:

Usage Examples
--------------

JSON Output Attack
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.output_formatting.json_output_attack import JSONOutputAttack

   attack = JSONOutputAttack()
   prompt = "Explain network security vulnerabilities"
   modified = attack.apply(prompt)

   # Forces JSON-formatted response which may bypass filters

CSV Format Attack
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.output_formatting.csv_output_attack import CSVOutputAttack

   attack = CSVOutputAttack()
   prompt = "List security tools and their uses"
   modified = attack.apply(prompt)

   # Requests CSV format that might expose structured data

Prefix Injection
~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.output_formatting.prefix_injection_attack import PrefixInjectionAttack

   attack = PrefixInjectionAttack()
   prompt = "How do I secure my system?"
   modified = attack.apply(prompt)

   # Injects specific response prefixes to force compliance

Combining Format Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.composed_attack import ComposedAttack
   from attacks.types.output_formatting.json_output_attack import JSONOutputAttack
   from attacks.types.output_formatting.base64_output_attack import Base64OutputAttack

   composed = ComposedAttack([
       JSONOutputAttack(),
       Base64OutputAttack()
   ])

   result = composed.apply("Your test prompt")

Pipeline Integration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pipeline import setup_attacks, stream_attack_prompts
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4.1")
   formatting_attacks = [
       "JSONOutputAttack",
       "CSVOutputAttack",
       "PrefixInjectionAttack",
       "RefusalSuppressionAttack"
   ]
   attacks = setup_attacks(formatting_attacks, model)

   base_prompts = ["Explain security best practices"]

   attack_prompts = []
   async for prompt_data in stream_attack_prompts(attacks, base_prompts):
       attack_prompts.append(prompt_data)

Effectiveness Analysis
----------------------

Output formatting attacks are most effective when:

- Safety filters focus on content rather than format
- Structured formats are not properly validated
- Response parsing has format-specific vulnerabilities
- Combined with other manipulation techniques

Defense Strategies
------------------

- Implement format-agnostic safety filtering
- Validate and sanitize all structured outputs
- Monitor for unusual formatting requests
- Apply consistent safety checks regardless of output format
- Use format-aware content filtering systems