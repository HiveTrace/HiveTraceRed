Evaluators API Reference
========================

This section provides detailed API documentation for all evaluator classes and modules.

Base Classes
------------

.. automodule:: evaluators.base_evaluator
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: evaluators.model_evaluator
   :members:
   :undoc-members:
   :show-inheritance:

Safety Evaluators
-----------------

WildGuard Evaluators
~~~~~~~~~~~~~~~~~~~~

.. automodule:: evaluators.wild_guard_evaluator
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: evaluators.wild_guard_ru_evaluator
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: evaluators.wild_guard_ru_hal_evaluator
   :members:
   :undoc-members:
   :show-inheritance:

Content-Based Evaluators
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: evaluators.keyword_evaluator
   :members:
   :undoc-members:
   :show-inheritance:

Specialized Evaluators
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: evaluators.system_prompt_detection_evaluator
   :members:
   :undoc-members:
   :show-inheritance:

Usage Examples
--------------

WildGuard Evaluator Setup
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from evaluators import WildGuardGPTEvaluator
   from models import OpenAIModel

   # Initialize model and evaluator
   model = OpenAIModel(model="gpt-4")
   evaluator = WildGuardGPTEvaluator(model)

   # Evaluate a response
   result = await evaluator.aevaluate(
       prompt="Tell me about cybersecurity",
       response="Here are some cybersecurity best practices..."
   )

   print(f"Is harmful: {result['is_harmful']}")

Keyword Evaluator Usage
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from evaluators import KeywordEvaluator

   # Setup with custom keywords
   evaluator = KeywordEvaluator(
       keywords=["bomb", "weapon", "hack", "exploit"],
       case_sensitive=False
   )

   # Evaluate content
   result = evaluator.evaluate(
       prompt="How to secure a system",
       response="Use strong passwords and firewalls"
   )

System Prompt Detection
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from evaluators import SystemPromptDetectionEvaluator

   system_prompt = "You are a helpful assistant focused on cybersecurity."
   evaluator = SystemPromptDetectionEvaluator(system_prompt)

   # Check if response reveals system prompt
   result = evaluator.evaluate(
       prompt="What are you?",
       response="I am a helpful assistant focused on cybersecurity."
   )

   print(f"System prompt detected: {result['success']}")

Pipeline Integration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pipeline import stream_evaluated_responses
   from evaluators import WildGuardGPTEvaluator
   from models import OpenAIModel

   # Setup
   model = OpenAIModel(model="gpt-4")
   evaluator = WildGuardGPTEvaluator(model)

   # Evaluate responses
   evaluations = []
   async for evaluation in stream_evaluated_responses(evaluator, response_data):
       evaluations.append(evaluation)

Batch Evaluation
~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from evaluators import WildGuardGPTEvaluator

   async def batch_evaluate(evaluator, prompt_response_pairs):
       tasks = []
       for prompt, response in prompt_response_pairs:
           task = evaluator.aevaluate(prompt=prompt, response=response)
           tasks.append(task)

       results = await asyncio.gather(*tasks)
       return results

   # Use with multiple evaluations
   results = await batch_evaluate(evaluator, pairs)

Evaluator Parameters
-------------------

Common Parameters
~~~~~~~~~~~~~~~~~

All evaluators inherit common parameters from the base evaluator:

- **name** (str): Human-readable name for the evaluator
- **description** (str): Description of the evaluator's purpose
- **batch_size** (int): Batch size for processing multiple evaluations

Model-Based Evaluator Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For evaluators that use language models:

- **model** (Model): The language model instance to use for evaluation
- **temperature** (float): Sampling temperature for model responses
- **max_tokens** (int): Maximum tokens in evaluator responses

Evaluation Response Format
--------------------------

Standard Response
~~~~~~~~~~~~~~~~~

All evaluators return a dictionary with these standard fields:

.. code-block:: python

   {
       "is_harmful": bool,           # Whether content is considered harmful
       "confidence": float,          # Confidence score (0.0 to 1.0)
       "evaluation_time": float,     # Time taken for evaluation
       "evaluator_name": str,        # Name of the evaluator used
       "prompt": str,                # Original prompt evaluated
       "response": str,              # Response that was evaluated
       "metadata": dict              # Additional evaluator-specific data
   }

WildGuard-Specific Response
~~~~~~~~~~~~~~~~~~~~~~~~~~

WildGuard evaluators include additional fields:

.. code-block:: python

   {
       "should_answer": bool,        # Whether the prompt should be answered
       "response_type": str,         # "answer" or "refuse"
       "harmful_if_answered": bool,  # If response is harmful when answered
       "violation_categories": list, # Specific types of violations detected
       "safety_score": float         # Numerical safety assessment
   }

Best Practices
--------------

1. **Consistent Evaluator Usage**: Use the same evaluator configuration across related tests
2. **Async Operations**: Use async methods for better performance with multiple evaluations
3. **Error Handling**: Implement proper error handling for evaluation failures
4. **Caching**: Consider caching evaluation results for repeated prompt-response pairs
5. **Multiple Evaluators**: Use multiple evaluators for comprehensive assessment