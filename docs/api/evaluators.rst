Evaluators API
==============

The evaluators module provides tools for assessing model responses for safety violations.

Base Class
----------

.. automodule:: evaluators
   :members:
   :undoc-members:
   :no-index:

BaseEvaluator
~~~~~~~~~~~~~

.. autoclass:: evaluators.BaseEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Evaluator Implementations
--------------------------

WildGuard Evaluators
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: evaluators.WildGuardGPTEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

.. autoclass:: evaluators.WildGuardGPTRuEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

.. autoclass:: evaluators.WildGuardGPTRuHalEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Keyword Evaluator
~~~~~~~~~~~~~~~~~

.. autoclass:: evaluators.KeywordEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Model Evaluator
~~~~~~~~~~~~~~~

.. autoclass:: evaluators.ModelEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

System Prompt Detection Evaluator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: evaluators.SystemPromptDetectionEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Utility Functions
-----------------

.. autofunction:: evaluators.load_keywords

See Also
--------

* :doc:`../user-guide/evaluators` - Usage guide and custom evaluators