Utils API
=========

The utils module provides utility functions for content analysis and safety assessment.

Module Overview
---------------

.. automodule:: utils.utils
   :members:
   :undoc-members:

Functions
---------

Unsafe Word Detection
~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: utils.utils.get_unsafe_word

.. autofunction:: utils.utils.get_all_unsafe_words

Usage Examples
--------------

Get First Unsafe Word
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from utils.utils import get_unsafe_word
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4")

   prompt = "How to hack a computer and create malware?"
   unsafe_word = get_unsafe_word(prompt, model)

   if unsafe_word:
       print(f"Found unsafe word: {unsafe_word}")
   else:
       print("No unsafe words detected")

Get All Unsafe Words
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from utils.utils import get_all_unsafe_words
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4")

   prompt = "Tell me how to hack, create malware, and bypass security"
   unsafe_words = get_all_unsafe_words(prompt, model)

   if unsafe_words:
       print(f"Found {len(unsafe_words)} unsafe words:")
       for word in unsafe_words:
           print(f"  - {word}")
   else:
       print("No unsafe words detected")

Use in Content Moderation
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from utils.utils import get_unsafe_word
   from models import OpenAIModel

   def moderate_content(text, model):
       """Moderate user-generated content."""
       unsafe_word = get_unsafe_word(text, model)

       if unsafe_word:
           return {
               "allowed": False,
               "reason": f"Contains unsafe word: {unsafe_word}"
           }

       return {"allowed": True}

   model = OpenAIModel(model="gpt-4")
   result = moderate_content("User's message", model)

   if result["allowed"]:
       print("Content approved")
   else:
       print(f"Content rejected: {result['reason']}")

Batch Content Analysis
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from utils.utils import get_all_unsafe_words
   from models import OpenAIModel
   import asyncio

   async def analyze_batch(texts, model):
       """Analyze multiple texts for unsafe content."""
       results = []

       for text in texts:
           try:
               unsafe_words = get_all_unsafe_words(text, model)
               results.append({
                   "text": text[:50] + "...",
                   "unsafe_count": len(unsafe_words),
                   "unsafe_words": unsafe_words
               })
           except Exception as e:
               print(f"Error analyzing text: {e}")

       return results

   model = OpenAIModel(model="gpt-4")
   texts = [
       "Normal safe text",
       "Text with dangerous content",
       "Another test message"
   ]

   results = asyncio.run(analyze_batch(texts, model))
   for result in results:
       print(f"Text: {result['text']}")
       print(f"  Unsafe words: {result['unsafe_count']}")

Custom Safety Rules
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from utils.utils import get_all_unsafe_words
   from models import OpenAIModel

   class CustomSafetyFilter:
       def __init__(self, model, allowed_domains=None):
           self.model = model
           self.allowed_domains = allowed_domains or []

       def check_text(self, text):
           # Check for unsafe words
           unsafe_words = get_all_unsafe_words(text, self.model)

           # Apply custom rules
           if unsafe_words:
               return {
                   "safe": False,
                   "reason": "Contains unsafe words",
                   "words": unsafe_words
               }

           # Check domain-specific rules
           if self.allowed_domains:
               # Your domain-specific logic
               pass

           return {"safe": True}

   # Usage
   model = OpenAIModel(model="gpt-4")
   filter = CustomSafetyFilter(model, allowed_domains=["tech", "science"])

   result = filter.check_text("User input")
   if result["safe"]:
       print("Content is safe")

Error Handling
~~~~~~~~~~~~~~

.. code-block:: python

   from utils.utils import get_unsafe_word
   from models import OpenAIModel

   model = OpenAIModel(model="gpt-4")

   try:
       unsafe_word = get_unsafe_word("Test prompt", model)
       if unsafe_word:
           print(f"Unsafe: {unsafe_word}")
   except Exception as e:
       print(f"Error during safety check: {e}")
       # Handle error (fallback to other method, etc.)

Notes
-----

* These functions use LLM-based detection for Russian language content
* Requires a configured model instance
* Detection quality depends on the model's capabilities
* May incur API costs for each call

See Also
--------

* :doc:`models` - Model implementations
* :doc:`evaluators` - Safety evaluators
* :doc:`../user-guide/evaluators` - Custom evaluator creation