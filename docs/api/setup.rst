Setup and Configuration
=======================

The setup module provides factory helpers that translate configuration dicts into initialized model/evaluator instances and dataset specifications.

Dataset Configuration
---------------------

**DatasetSpec**

.. py:class:: DatasetSpec(NamedTuple)

   Immutable specification for one dataset in a multi-dataset run.

   :ivar str name: Unique dataset identifier (validated at config load time to match ``^[A-Za-z0-9_-]+$``). Used as the ``dataset`` column value in output files and report section headers.
   :ivar list prompts: List of base prompts (strings or dicts) loaded from the dataset entry's ``base_prompts`` or ``base_prompts_file``. Guaranteed non-empty (zero-prompt datasets are rejected at preflight).
   :ivar evaluator: Evaluator instance (``BaseEvaluator | None``) for this dataset. May be ``None`` if ``setup_evaluator`` failed during config initialization; the pipeline's preflight check raises ``ValueError`` if any dataset has ``evaluator=None`` when Stage 3 is enabled.

Load Datasets
~~~~~~~~~~~~~

.. autofunction:: hivetracered.setup.load_datasets

   Load a list of DatasetSpec from ``config["datasets"]``. Each dataset entry is processed:
   - Prompts are loaded via ``load_base_prompts(entry)``
   - Evaluator is instantiated via ``setup_evaluator(entry["evaluator"], evaluation_model)``

   Returns a list in the order of the ``datasets:`` config entries. Raises ``ValueError`` during the pipeline's preflight check if validation fails (e.g., duplicate names, invalid characters, missing sources, zero-prompt datasets).

Model and Evaluator Setup
--------------------------

.. autofunction:: hivetracered.setup.setup_model

   Initialize a model from a configuration dict. Returns ``None`` and logs a warning on unknown names or init failures.

.. autofunction:: hivetracered.setup.setup_evaluator

   Initialize an evaluator from a configuration dict. Model-based evaluators (subclasses of ``ModelEvaluator``) receive the ``model`` parameter; other evaluators are constructed with just their params. Returns ``None`` and logs a warning on init failures.

Prompt and Record Loading
--------------------------

.. autofunction:: hivetracered.setup.load_base_prompts

   Load base prompts from ``base_prompts_file`` or fall back to ``base_prompts`` in a dict (single dataset or dataset entry).

.. autofunction:: hivetracered.setup.load_records

   Load intermediate pipeline records from a file. Used to resume runs at intermediate stages.
