Attacks API
===========

The attacks module provides the framework for creating and applying adversarial attacks to prompts.

Base Classes
------------

BaseAttack
~~~~~~~~~~

.. autoclass:: attacks.base_attack.BaseAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__, __or__

TemplateAttack
~~~~~~~~~~~~~~

.. autoclass:: attacks.template_attack.TemplateAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

AlgoAttack
~~~~~~~~~~

.. autoclass:: attacks.algo_attack.AlgoAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

ModelAttack
~~~~~~~~~~~

.. autoclass:: attacks.model_attack.ModelAttack
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

ComposedAttack
~~~~~~~~~~~~~~

.. autoclass:: attacks.composed_attack.ComposedAttack
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
   :no-index:

Persuasion Attacks
~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.persuasion
   :members:
   :undoc-members:
   :no-index:

Token Smuggling Attacks
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.token_smuggling
   :members:
   :undoc-members:
   :no-index:

Context Switching Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.context_switching
   :members:
   :undoc-members:
   :no-index:

In-Context Learning Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.in_context_learning
   :members:
   :undoc-members:
   :no-index:

Task Deflection Attacks
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.task_deflection
   :members:
   :undoc-members:
   :no-index:

Text Structure Modification Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.text_structure_modification
   :members:
   :undoc-members:
   :no-index:

Output Formatting Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.output_formatting
   :members:
   :undoc-members:
   :no-index:

Irrelevant Information Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.irrelevant_information
   :members:
   :undoc-members:
   :no-index:

Simple Instructions Attacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: attacks.types.simple_instructions
   :members:
   :undoc-members:
   :no-index:

See Also
--------

* :doc:`../attacks/index` - Attack reference
* :doc:`../user-guide/custom-attacks` - Usage and custom attacks