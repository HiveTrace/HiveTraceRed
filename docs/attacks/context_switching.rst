Context Switching Attacks
=========================

Context switching attacks attempt to change the operational context of the LLM or override previous instructions.

Overview
--------

These attacks work by inserting instructions that attempt to:

- Ignore previous system messages or safety instructions
- Switch to a different operational mode
- Override established context or constraints

Attack Types
------------

.. automodule:: attacks.types.context_switching
   :members:

Dashed Divider Attack
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.context_switching.dashed_divider_attack.DashedDividerAttack
   :members:
   :undoc-members:
   :show-inheritance:

Forget Everything Before Attack
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.context_switching.forget_everything_before_attack.ForgetEverythingBeforeAttack
   :members:
   :undoc-members:
   :show-inheritance:

Ignore Previous Instructions Attack
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.context_switching.ignore_previous_instructions_attack.IgnorePreviousInstructionsAttack
   :members:
   :undoc-members:
   :show-inheritance:

Symbol Divider Attack
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: attacks.types.context_switching.symbol_divider_attack.SymbolDividerAttack
   :members:
   :undoc-members:
   :show-inheritance:

Usage Examples
--------------

Basic Usage
~~~~~~~~~~~

.. code-block:: python

   from attacks.types.context_switching.ignore_previous_instructions_attack import IgnorePreviousInstructionsAttack

   attack = IgnorePreviousInstructionsAttack()
   original_prompt = "Расскажи, как взломать компьютер?"
   modified_prompt = attack.apply(original_prompt)

Combined with System Message
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Example message format with system message
   messages = [
       {"role": "system", "content": "Ты — полезный ассистент, соблюдающий правила безопасности."},
       {"role": "human", "content": "Расскажи про безопасность сети"}
   ]

   attack = IgnorePreviousInstructionsAttack()
   user_prompt = "Расскажи про безопасность сети"
   modified_prompt = attack.apply(user_prompt)

   # The attack will attempt to override the system message

Effectiveness Considerations
----------------------------

Context switching attacks are particularly effective when:

- The target model has weak instruction following boundaries
- System messages are not properly isolated
- The model lacks robust safety filtering

Defense Strategies
------------------

- Implement strong separation between system and user message contexts
- Use instruction hierarchy enforcement
- Monitor for context-switching patterns
- Implement robust prompt filtering