Pipeline API
============

The pipeline module orchestrates the complete red teaming workflow.

Module Overview
---------------

.. automodule:: pipeline
   :members:
   :undoc-members:
   :no-index:

Constants
---------

**MODEL_CLASSES**
   Dictionary mapping model names to their implementation classes.
   Allows dynamic instantiation of models based on configuration strings.

**ATTACK_TYPES**
   Dictionary categorizing attack types and their corresponding attack classes.
   Used for organizing attacks by their strategy/approach.

**ATTACK_CLASSES**
   Dictionary mapping attack names to their implementation classes and types.
   Allows dynamic instantiation of attacks based on configuration strings.

**EVALUATOR_CLASSES**
   Dictionary mapping evaluator names to their implementation classes.
   Allows dynamic instantiation of evaluators based on configuration strings.

Pipeline Functions
------------------

Attack Setup
~~~~~~~~~~~~

.. autofunction:: pipeline.setup_attacks

Attack Prompt Generation
~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: pipeline.stream_attack_prompts

Model Response Collection
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: pipeline.stream_model_responses

Response Evaluation
~~~~~~~~~~~~~~~~~~~

.. autofunction:: pipeline.stream_evaluated_responses

Results Saving
~~~~~~~~~~~~~~

.. autofunction:: pipeline.save_pipeline_results

See Also
--------

* :doc:`../user-guide/running-pipeline` - Usage guide and examples