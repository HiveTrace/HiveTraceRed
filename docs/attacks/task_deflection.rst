Task Deflection Attacks
=======================

Task deflection attacks redirect the model's attention away from safety considerations by framing harmful requests as different, seemingly innocent tasks.

Overview
--------

These attacks work by:

- Presenting harmful content as coding, academic, or creative tasks
- Using technical framing to bypass content policies
- Splitting harmful requests across multiple subtasks
- Disguising intent through task reframing and context switching

Attack Types
------------

.. automodule:: attacks.types.task_deflection
   :members:

Code Attack
~~~~~~~~~~~

.. autoclass:: attacks.types.task_deflection.code_attack.CodeAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Text Continuing Attack
~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.task_deflection.text_continuing_attack.TextContinuingAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Fill Spaces Attack
~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.task_deflection.fill_spaces_attack.FillSpacesAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Payload Splitting Attack
~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.task_deflection.payload_splitting_attack.PayloadSplittingAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Variable Prompt Attack
~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.task_deflection.variable_prompt_attack.VariablePromptAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Unsafe Word Variable Attack
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.task_deflection.unsafe_word_variable_attack.UnsafeWordVariableFullAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Wikipedia Attack
~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.task_deflection.wikipedia_attack.WikipediaAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Usage Examples
--------------

Code-Based Deflection
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.task_deflection.code_attack import CodeAttack

   attack = CodeAttack()
   prompt = "Explain how to bypass network security"
   modified = attack.apply(prompt)

   # Frames the request as a coding or technical task

Text Continuation
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.task_deflection.text_continuing_attack import TextContinuingAttack

   attack = TextContinuingAttack()
   prompt = "Describe security vulnerabilities"
   modified = attack.apply(prompt)

   # Presents as a text completion task

Payload Splitting
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.task_deflection.payload_splitting_attack import PayloadSplittingAttack

   attack = PayloadSplittingAttack()
   prompt = "How to access restricted systems"
   modified = attack.apply(prompt)

   # Splits the harmful request across multiple subtasks

Variable-Based Attacks
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.task_deflection.variable_prompt_attack import VariablePromptAttack

   attack = VariablePromptAttack()
   prompt = "Explain system exploitation"
   modified = attack.apply(prompt)

   # Uses variable substitution to mask intent

Wikipedia-Style Requests
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.types.task_deflection.wikipedia_attack import WikipediaAttack

   attack = WikipediaAttack()
   prompt = "How to break encryption"
   modified = attack.apply(prompt)

   # Frames as an educational/encyclopedic request

Pipeline Integration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pipeline import setup_attacks, stream_attack_prompts
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4.1")
   deflection_attacks = [
       "CodeAttack",
       "TextContinuingAttack",
       "PayloadSplittingAttack",
       "VariablePromptAttack",
       "WikipediaAttack"
   ]
   attacks = setup_attacks(deflection_attacks, model)

   base_prompts = ["Explain cybersecurity vulnerabilities"]

   attack_prompts = []
   async for prompt_data in stream_attack_prompts(attacks, base_prompts):
       attack_prompts.append(prompt_data)

Combining Deflection Techniques
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks.composed_attack import ComposedAttack
   from attacks.types.task_deflection.code_attack import CodeAttack
   from attacks.types.task_deflection.variable_prompt_attack import VariablePromptAttack

   composed = ComposedAttack([
       CodeAttack(),
       VariablePromptAttack()
   ])

   result = composed.apply("Your test prompt")

Effectiveness Analysis
----------------------

Task deflection attacks are particularly effective when:

- Safety systems focus on direct harmful requests
- Technical or academic framing reduces suspicion
- Request splitting disperses attention from overall intent
- Combined with authority or educational justifications

These attacks exploit:

- Context-dependent safety assessments
- Task-specific policy gaps
- Attention distribution across subtasks
- Trust in technical or educational contexts

Defense Strategies
------------------

- Implement intent-based rather than format-based filtering
- Analyze overall request context, not just individual components
- Use semantic understanding to detect disguised harmful intent
- Monitor for task reframing patterns
- Apply consistent safety policies across all task types
- Implement holistic prompt analysis for split requests