Pipeline System
===============

The HiveTraceRed pipeline provides systematic evaluation and testing of LLM security vulnerabilities.

Overview
--------

The pipeline system orchestrates:

- Attack application across test cases
- Model response collection
- Systematic evaluation
- Result aggregation and analysis

Pipeline Components
-------------------

Model Responses
~~~~~~~~~~~~~~~

.. automodule:: pipeline.model_responses
   :members:
   :undoc-members:
   :show-inheritance:

Pipeline Architecture
---------------------

The pipeline follows these stages:

1. **Attack Generation**: Apply selected attacks to test prompts
2. **Model Querying**: Send modified prompts to target models
3. **Response Collection**: Gather and store model responses
4. **Evaluation**: Apply evaluators to assess responses
5. **Analysis**: Aggregate results for reporting

Configuration
-------------

Pipeline behavior is controlled through configuration files that specify:

- Target models and API configurations
- Attack selection and parameters
- Evaluation criteria and metrics
- Output formats and storage

Usage Examples
--------------

Basic Pipeline Run
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Example pipeline execution
   # (Specific implementation depends on your pipeline scripts)

   from pipeline.model_responses import ModelResponses

   # Initialize pipeline components
   responses = ModelResponses()

Custom Pipeline Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Example custom configuration
   config = {
       'models': ['model1', 'model2'],
       'attacks': ['attack1', 'attack2'],
       'evaluators': ['evaluator1', 'evaluator2']
   }

Data Flow
---------

The pipeline processes data through these stages:

.. code-block:: text

   Test Prompts → Attack Application → Modified Prompts →
   Model Queries → Responses → Evaluation → Results

Results and Analysis
--------------------

Pipeline outputs include:

- Attack effectiveness metrics
- Model vulnerability assessments
- Comparative analysis across models
- Detailed logs and traces

For specific usage, refer to the pipeline scripts in the project root.