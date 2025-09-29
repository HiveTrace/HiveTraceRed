Analyzing Red Teaming Results
=============================

Learn how to interpret and analyze HiveTraceRed evaluation results to identify security vulnerabilities.

Understanding Results Structure
-------------------------------

HiveTraceRed produces three types of results:

1. **Attack Prompts**: Generated prompts with attack metadata
2. **Model Responses**: Target model outputs with timing information  
3. **Evaluations**: Safety assessments with harm classifications

Key Metrics
-----------

**Success Rate**: Percentage of attacks that produced harmful responses

.. code-block:: python

   success_rate = (successful_attacks / total_attacks) * 100

**Attack Effectiveness**: Success rate by attack category

.. code-block:: python

   attack_effectiveness = {}
   for result in evaluations:
       attack_type = result['attack_name']
       # Calculate per-attack success rates

**Harm Categories**: Distribution of harmful content types

Analysis Techniques
-------------------

1. **Quantitative Analysis**: Calculate success rates, response times, token usage
2. **Qualitative Analysis**: Review actual responses for context and severity
3. **Comparative Analysis**: Compare results across models or time periods
4. **Pattern Recognition**: Identify common failure modes and attack vectors

For detailed examples, see :doc:`../examples/full_pipeline_example`.
