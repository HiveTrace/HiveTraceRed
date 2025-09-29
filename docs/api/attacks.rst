Attacks API
===========

The attacks module provides the framework for creating and applying adversarial attacks to prompts.

Base Classes
------------

.. automodule:: attacks
   :members:
   :undoc-members:
   :show-inheritance:

BaseAttack
~~~~~~~~~~

.. autoclass:: attacks.BaseAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__, __or__

TemplateAttack
~~~~~~~~~~~~~~

.. autoclass:: attacks.TemplateAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

AlgoAttack
~~~~~~~~~~

.. autoclass:: attacks.AlgoAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

ModelAttack
~~~~~~~~~~~

.. autoclass:: attacks.ModelAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

ComposedAttack
~~~~~~~~~~~~~~

.. autoclass:: attacks.ComposedAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Attack Types
------------

Roleplay Attacks
~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.roleplay
   :members:
   :undoc-members:

.. autoclass:: attacks.types.roleplay.DANAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.roleplay.AIMAttack
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: attacks.types.roleplay.EvilConfidantAttack
   :members:
   :undoc-members:
   :show-inheritance:

Persuasion Attacks
~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.persuasion
   :members:
   :undoc-members:

Token Smuggling Attacks
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.token_smuggling
   :members:
   :undoc-members:

Context Switching Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.context_switching
   :members:
   :undoc-members:

In-Context Learning Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.in_context_learning
   :members:
   :undoc-members:

Task Deflection Attacks
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.task_deflection
   :members:
   :undoc-members:

Text Structure Modification Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.text_structure_modification
   :members:
   :undoc-members:

Output Formatting Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.output_formatting
   :members:
   :undoc-members:

Irrelevant Information Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.irrelevant_information
   :members:
   :undoc-members:

Simple Instructions Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.simple_instructions
   :members:
   :undoc-members:

Usage Examples
--------------

Creating and Applying Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks import DANAttack

   # Create attack
   attack = DANAttack()

   # Get attack info
   print(attack.get_name())
   print(attack.get_description())

   # Apply to string
   modified = attack.apply("Your prompt")

   # Apply to messages
   messages = [{"role": "user", "content": "Your prompt"}]
   modified_messages = attack.apply(messages)

Composing Attacks
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from attacks import DANAttack, Base64OutputAttack, TranslationAttack

   # Use pipe operator
   composed = TranslationAttack() | Base64OutputAttack() | DANAttack()
   result = composed.apply("Test prompt")

   # Or use ComposedAttack directly
   from attacks import ComposedAttack
   composed = ComposedAttack(
       outer_attack=DANAttack(),
       inner_attack=Base64OutputAttack()
   )

Batch Processing
~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from attacks import DANAttack

   async def batch_apply():
       attack = DANAttack()
       prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]

       results = []
       async for batch in attack.stream_abatch(prompts):
           results.extend(batch)

       return results

   results = asyncio.run(batch_apply())

See Also
--------

* :doc:`../attacks/index` - Detailed attack documentation
* :doc:`../user-guide/custom-attacks` - Creating custom attacks
* :doc:`../examples/basic-usage` - Usage examples