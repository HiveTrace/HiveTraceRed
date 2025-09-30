Pipeline API
============

The pipeline module orchestrates the complete red teaming workflow.

Module Overview
---------------

.. automodule:: pipeline
   :members:
   :undoc-members:

Constants
---------

.. autodata:: pipeline.MODEL_CLASSES
   :annotation: = Dictionary mapping model names to model classes

.. autodata:: pipeline.ATTACK_TYPES
   :annotation: = List of all available attack types

.. autodata:: pipeline.ATTACK_CLASSES
   :annotation: = Dictionary mapping attack names to attack classes

.. autodata:: pipeline.EVALUATOR_CLASSES
   :annotation: = Dictionary mapping evaluator names to evaluator classes

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