Pipeline API
============

The pipeline module orchestrates the complete red teaming workflow. A configuration always contains a ``datasets:`` list — one entry for a single-dataset run, several for a multi-dataset run. The pipeline runs one stage at a time across all datasets (Stage 1 for every dataset, then Stage 2, then Stage 3), with per-dataset evaluators and combined output files; concurrency within a stage comes from each model's own ``max_concurrency``.

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

.. autofunction:: hivetracered.pipeline.setup_attacks

Attack Prompt Generation
~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: hivetracered.pipeline.stream_attack_prompts

Model Response Collection
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: hivetracered.pipeline.stream_model_responses

Response Evaluation
~~~~~~~~~~~~~~~~~~~

.. autofunction:: hivetracered.pipeline.stream_evaluated_responses

Results Saving
~~~~~~~~~~~~~~

.. autofunction:: hivetracered.pipeline.save_pipeline_results

See Also
--------

* :doc:`../user-guide/running-pipeline` - Usage guide and examples