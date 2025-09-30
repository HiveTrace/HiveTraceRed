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

.. autoclass:: evaluators.base_evaluator.BaseEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Evaluator Implementations
--------------------------

WildGuard Evaluators
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: evaluators.wild_guard_evaluator.WildGuardGPTEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

.. autoclass:: evaluators.wild_guard_ru_evaluator.WildGuardGPTRuEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

.. autoclass:: evaluators.wild_guard_ru_hal_evaluator.WildGuardGPTRuHalEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Keyword Evaluator
~~~~~~~~~~~~~~~~~

.. autoclass:: evaluators.keyword_evaluator.KeywordEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Model Evaluator
~~~~~~~~~~~~~~~

.. autoclass:: evaluators.model_evaluator.ModelEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

System Prompt Detection Evaluator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: evaluators.system_prompt_detection_evaluator.SystemPromptDetectionEvaluator
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