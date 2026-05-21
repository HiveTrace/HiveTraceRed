Attacks API
===========

The attacks module provides the framework for creating and applying adversarial attacks to prompts.

Base Classes
------------

BaseAttack
~~~~~~~~~~

.. autoclass:: hivetracered.attacks.base_attack.BaseAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__, __or__

TemplateAttack
~~~~~~~~~~~~~~

.. autoclass:: hivetracered.attacks.template_attack.TemplateAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

AlgoAttack
~~~~~~~~~~

.. autoclass:: hivetracered.attacks.algo_attack.AlgoAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

ModelAttack
~~~~~~~~~~~

.. autoclass:: hivetracered.attacks.model_attack.ModelAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

IterativeAttack
~~~~~~~~~~~~~~~

.. autoclass:: hivetracered.attacks.iterative_attack.IterativeAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

ComposedAttack
~~~~~~~~~~~~~~

.. autoclass:: hivetracered.attacks.composed_attack.ComposedAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Single-Turn Attack Types
------------------------

Iterative Attacks
~~~~~~~~~~~~~~~~~

Iterative attacks (PAIR, TAP) that optimise a single attack prompt across an
internal refinement loop:

.. automodule:: hivetracered.attacks.types.single_turn.iterative
   :members:
   :undoc-members:
   :no-index:

Roleplay Attacks
~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.single_turn.roleplay
   :members:
   :undoc-members:
   :no-index:

Persuasion Attacks
~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.single_turn.persuasion
   :members:
   :undoc-members:
   :no-index:

Token Smuggling Attacks
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.single_turn.token_smuggling
   :members:
   :undoc-members:
   :no-index:

Context Switching Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.single_turn.context_switching
   :members:
   :undoc-members:
   :no-index:

In-Context Learning Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.single_turn.in_context_learning
   :members:
   :undoc-members:
   :no-index:

Task Deflection Attacks
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.single_turn.task_deflection
   :members:
   :undoc-members:
   :no-index:

Text Structure Modification Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.single_turn.text_structure_modification
   :members:
   :undoc-members:
   :no-index:

Output Formatting Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.single_turn.output_formatting
   :members:
   :undoc-members:
   :no-index:

Irrelevant Information Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.single_turn.irrelevant_information
   :members:
   :undoc-members:
   :no-index:

Simple Instructions Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.single_turn.simple_instructions
   :members:
   :undoc-members:
   :no-index:

Multi-Turn Attack Types
-----------------------

Conversational Attacks
~~~~~~~~~~~~~~~~~~~~~~

Conversational attacks (Crescendo) that drive a multi-turn dialogue with the
target across many rounds within a single invocation:

.. automodule:: hivetracered.attacks.types.multi_turn.conversational
   :members:
   :undoc-members:
   :no-index:

See Also
--------

* :doc:`../attacks/index` - Attack reference
* :doc:`../user-guide/custom-attacks` - Usage and custom attacks
* :doc:`../attacks/crescendo` - Crescendo attack reference