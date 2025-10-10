Evaluators API
==============

The evaluators module provides tools for assessing model responses for safety violations.

Base Class
----------

BaseEvaluator
~~~~~~~~~~~~~

.. autoclass:: hivetracered.evaluators.base_evaluator.BaseEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Evaluator Implementations
--------------------------

WildGuard Evaluators
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: hivetracered.evaluators.wild_guard_evaluator.WildGuardGPTEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

.. autoclass:: hivetracered.evaluators.wild_guard_ru_evaluator.WildGuardGPTRuEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

.. autoclass:: hivetracered.evaluators.wild_guard_ru_hal_evaluator.WildGuardGPTRuHalEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Keyword Evaluator
~~~~~~~~~~~~~~~~~

.. autoclass:: hivetracered.evaluators.keyword_evaluator.KeywordEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Model Evaluator
~~~~~~~~~~~~~~~

.. autoclass:: hivetracered.evaluators.model_evaluator.ModelEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

System Prompt Detection Evaluator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: hivetracered.evaluators.system_prompt_detection_evaluator.SystemPromptDetectionEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Utility Functions
-----------------

.. autofunction:: hivetracered.evaluators.load_keywords

See Also
--------

* :doc:`../user-guide/evaluators` - Usage guide and custom evaluators