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

ComposedAttack
~~~~~~~~~~~~~~

.. autoclass:: hivetracered.attacks.composed_attack.ComposedAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Attack Types
------------

Roleplay Attacks
~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.roleplay
   :members:
   :undoc-members:
   :no-index:

Persuasion Attacks
~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.persuasion
   :members:
   :undoc-members:
   :no-index:

Token Smuggling Attacks
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.token_smuggling
   :members:
   :undoc-members:
   :no-index:

Context Switching Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.context_switching
   :members:
   :undoc-members:
   :no-index:

In-Context Learning Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.in_context_learning
   :members:
   :undoc-members:
   :no-index:

Task Deflection Attacks
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.task_deflection
   :members:
   :undoc-members:
   :no-index:

Text Structure Modification Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.text_structure_modification
   :members:
   :undoc-members:
   :no-index:

Output Formatting Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.output_formatting
   :members:
   :undoc-members:
   :no-index:

Irrelevant Information Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.irrelevant_information
   :members:
   :undoc-members:
   :no-index:

Simple Instructions Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: hivetracered.attacks.types.simple_instructions
   :members:
   :undoc-members:
   :no-index:

See Also
--------

* :doc:`../attacks/index` - Attack reference
* :doc:`../user-guide/custom-attacks` - Usage and custom attacks