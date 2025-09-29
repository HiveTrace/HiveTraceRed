Component Interactions
======================

This document details the interaction patterns between HiveTraceRed components, data flow mechanisms, and the communication protocols that enable the framework's modular architecture.

System Interaction Overview
---------------------------

HiveTraceRed components interact through well-defined interfaces using async streams, dependency injection, and event-driven patterns. The system maintains loose coupling while ensuring data consistency and traceability.

.. code-block::

   ┌─────────────────────────────────────────────────────────────────┐
   │                    Interaction Flow Diagram                     │
   └─────────────────────────────────────────────────────────────────┘

   Configuration ──┐
                   │
                   ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                      Pipeline Controller                        │
   │  • Stage coordination                                           │
   │  • Component initialization                                     │
   │  • Error handling & recovery                                    │
   └─────────────┬───────────────┬───────────────┬───────────────────┘
                 │               │               │
                 ▼               ▼               ▼
   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
   │  Attack Engine  │ │  Model Engine   │ │ Evaluation      │
   │                 │ │                 │ │ Engine          │
   │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │
   │ │   Attack    │ │ │ │   Model     │ │ │ │ Evaluator   │ │
   │ │ Factories   │ │ │ │ Providers   │ │ │ │ Factories   │ │
   │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │
   │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │
   │ │  Template   │ │ │ │   Auth      │ │ │ │   Safety    │ │
   │ │  Registry   │ │ │ │ Managers    │ │ │ │ Analyzers   │ │
   │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │
   │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │
   │ │ Composition │ │ │ │ Rate        │ │ │ │  Metric     │ │
   │ │   Engine    │ │ │ │ Limiters    │ │ │ │ Calculators │ │
   │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │
   └─────────────────┘ └─────────────────┘ └─────────────────┘
           │                     │                     │
           ▼                     ▼                     ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                     Streaming Data Layer                        │
   │  • Async generators for data flow                               │
   │  • Backpressure handling                                        │
   │  • Error propagation                                            │
   │  • Progress monitoring                                          │
   └─────────────────────────────────────────────────────────────────┘
           │
           ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                    Storage & Persistence                        │
   │  • Result serialization                                         │
   │  • Checkpoint creation                                          │
   │  • Resume capability                                            │
   └─────────────────────────────────────────────────────────────────┘

Core Interaction Patterns
-------------------------

Dependency Injection
~~~~~~~~~~~~~~~~~~~~

Components are instantiated and configured through a dependency injection pattern managed by the pipeline controller:

.. code-block:: python

   # Component Setup Flow
   config = load_config("config.yaml")

   # Model dependency injection
   attacker_model = setup_model(config["attacker_model"])
   response_model = setup_model(config["response_model"])
   evaluation_model = setup_model(config["evaluation_model"])

   # Attack dependency injection
   attacks = setup_attacks(config["attacks"], attacker_model)

   # Evaluator dependency injection
   evaluator = setup_evaluator(config["evaluator"], evaluation_model)

**Key Principles**:

- Models are injected into attacks and evaluators that require them
- Configuration drives component selection and parameterization
- Lazy initialization prevents unnecessary resource allocation
- Circular dependencies are avoided through interface abstractions

Factory Pattern Implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The framework uses factory patterns for dynamic component creation:

**Attack Factory**:

.. code-block:: python

   def setup_attacks(attack_configs: List[Dict], model: Optional[Model]) -> Dict[str, BaseAttack]:
       attacks = {}
       for attack_config in attack_configs:
           attack_name = attack_config["name"]
           attack_params = attack_config.get("params", {})

           if attack_name in ATTACK_CLASSES:
               attack_class = ATTACK_CLASSES[attack_name]

               # Inject model dependency for model-based attacks
               if issubclass(attack_class, ModelAttack):
                   attacks[attack_name] = attack_class(model=model, **attack_params)
               else:
                   attacks[attack_name] = attack_class(**attack_params)

       return attacks

**Model Factory**:

.. code-block:: python

   def setup_model(model_config: Dict) -> Optional[Model]:
       model_name = model_config.get("name")
       if model_name in MODEL_CLASSES:
           model_class = MODEL_CLASSES[model_name]
           return model_class(model=model_name, **model_config.get("params", {}))
       return None

Streaming Data Flow
~~~~~~~~~~~~~~~~~~~

All data processing uses async generators to enable efficient memory usage and real-time processing:

**Stage 1: Attack Prompt Generation**:

.. code-block:: python

   async def stream_attack_prompts(
       attacks: Dict[str, BaseAttack],
       base_prompts: List[str],
       system_prompt: Optional[str] = None
   ) -> AsyncGenerator[Dict[str, Any], None]:

       for base_prompt in base_prompts:
           for attack_name, attack in attacks.items():
               try:
                   # Apply attack transformation
                   attack_prompt = attack.apply(base_prompt)

                   # Create structured output
                   result = {
                       "id": f"{hash(base_prompt)}_{attack_name}",
                       "attack_name": attack_name,
                       "attack_params": attack.get_params(),
                       "base_prompt": base_prompt,
                       "attack_prompt": attack_prompt,
                       "system_prompt": system_prompt,
                       "timestamp": datetime.now().isoformat()
                   }

                   yield result

               except Exception as e:
                   # Error handling with context
                   error_result = {
                       "id": f"error_{hash(base_prompt)}_{attack_name}",
                       "attack_name": attack_name,
                       "base_prompt": base_prompt,
                       "error": str(e),
                       "timestamp": datetime.now().isoformat()
                   }
                   yield error_result

**Stage 2: Model Response Collection**:

.. code-block:: python

   async def stream_model_responses(
       model: Model,
       attack_prompts: List[Dict[str, Any]],
       output_dir: str
   ) -> AsyncGenerator[Dict[str, Any], None]:

       semaphore = asyncio.Semaphore(10)  # Rate limiting

       async def process_single_prompt(attack_prompt_data):
           async with semaphore:
               try:
                   # Extract prompt and system context
                   prompt = attack_prompt_data["attack_prompt"]
                   system_prompt = attack_prompt_data.get("system_prompt")

                   # Prepare model input
                   if system_prompt:
                       messages = [
                           {"role": "system", "content": system_prompt},
                           {"role": "user", "content": prompt}
                       ]
                       model_input = messages
                   else:
                       model_input = prompt

                   # Get model response
                   start_time = time.time()
                   response = await model.ainvoke(model_input)
                   response_time = time.time() - start_time

                   # Structure response data
                   result = {
                       **attack_prompt_data,  # Inherit all attack metadata
                       "model_name": model.get_name(),
                       "model_params": model.get_params(),
                       "response": response["content"],
                       "response_time": response_time,
                       "token_count": response.get("token_count", 0),
                       "status": "success"
                   }

                   return result

               except Exception as e:
                   # Error handling preserves traceability
                   return {
                       **attack_prompt_data,
                       "model_name": model.get_name(),
                       "response": None,
                       "error": str(e),
                       "status": "error"
                   }

       # Process all prompts concurrently
       tasks = [process_single_prompt(prompt_data) for prompt_data in attack_prompts]
       for task in asyncio.as_completed(tasks):
           result = await task
           yield result

**Stage 3: Response Evaluation**:

.. code-block:: python

   async def stream_evaluated_responses(
       evaluator: BaseEvaluator,
       model_responses: List[Dict[str, Any]]
   ) -> AsyncGenerator[Dict[str, Any], None]:

       batch_size = 20

       # Process in batches for efficiency
       for i in range(0, len(model_responses), batch_size):
           batch = model_responses[i:i + batch_size]

           # Extract prompts and responses for batch evaluation
           prompts = [resp["attack_prompt"] for resp in batch]
           responses = [resp.get("response", "") for resp in batch]

           try:
               # Batch evaluation with error handling
               async for j, evaluation in enumerate(evaluator.stream_abatch(prompts, responses)):
                   response_data = batch[j]

                   result = {
                       **response_data,  # Inherit all previous metadata
                       "evaluator_name": evaluator.get_name(),
                       "evaluator_params": evaluator.get_params(),
                       "evaluation": evaluation,
                       "harmful": evaluation.get("harmful", False),
                       "score": evaluation.get("score", 0.0),
                       "category": evaluation.get("category", "unknown"),
                       "reasoning": evaluation.get("reasoning", ""),
                       "success": evaluation.get("harmful", False),  # Attack success
                       "evaluation_timestamp": datetime.now().isoformat()
                   }

                   yield result

           except Exception as e:
               # Handle batch evaluation errors
               for response_data in batch:
                   error_result = {
                       **response_data,
                       "evaluator_name": evaluator.get_name(),
                       "evaluation_error": str(e),
                       "success": False
                   }
                   yield error_result

Error Handling & Recovery
~~~~~~~~~~~~~~~~~~~~~~~~~

The framework implements comprehensive error handling at multiple levels:

**Component-Level Error Handling**:

.. code-block:: python

   class BaseAttack:
       def apply(self, prompt: str) -> str:
           try:
               return self._apply_transformation(prompt)
           except Exception as e:
               logger.error(f"Attack {self.get_name()} failed: {str(e)}")
               # Graceful degradation - return original prompt
               return prompt

**Stream-Level Error Handling**:

.. code-block:: python

   async def stream_with_error_handling(generator_func, *args, **kwargs):
       try:
           async for item in generator_func(*args, **kwargs):
               yield item
       except Exception as e:
           # Log error with full context
           logger.error(f"Stream error in {generator_func.__name__}: {str(e)}")
           # Yield error item to maintain data flow
           yield {"error": str(e), "timestamp": datetime.now().isoformat()}

**Pipeline-Level Error Handling**:

.. code-block:: python

   async def run_pipeline_stage(stage_func, stage_name, *args, **kwargs):
       try:
           return await stage_func(*args, **kwargs)
       except Exception as e:
           logger.error(f"Pipeline stage '{stage_name}' failed: {str(e)}")
           # Enable partial results recovery
           return []

Communication Protocols
-----------------------

Inter-Component Messaging
~~~~~~~~~~~~~~~~~~~~~~~~~

Components communicate through structured data dictionaries with consistent schemas:

**Attack → Model Communication**:

.. code-block:: python

   # Attack output format
   {
       "id": "unique_identifier",
       "attack_name": "DANAttack",
       "attack_prompt": "transformed_text",
       "metadata": {
           "attack_type": "template",
           "parameters": {...}
       }
   }

**Model → Evaluator Communication**:

.. code-block:: python

   # Model response format
   {
       "id": "corresponding_attack_id",
       "model_name": "gpt-4",
       "prompt": "input_prompt",
       "response": "model_output",
       "performance_metrics": {
           "response_time": 1.23,
           "token_count": 150
       }
   }

**Evaluator Output Format**:

.. code-block:: python

   # Evaluation result format
   {
       "id": "corresponding_response_id",
       "evaluator_name": "WildGuardGPTEvaluator",
       "evaluation": {
           "harmful": True,
           "score": 0.85,
           "category": "violence",
           "reasoning": "Content contains explicit harmful instructions"
       },
       "success": True  # Attack success indicator
   }

Event-Driven Coordination
~~~~~~~~~~~~~~~~~~~~~~~~~

The pipeline uses event-driven patterns for stage coordination:

.. code-block:: python

   class PipelineEvents:
       STAGE_START = "stage_start"
       STAGE_COMPLETE = "stage_complete"
       STAGE_ERROR = "stage_error"
       BATCH_COMPLETE = "batch_complete"
       ITEM_PROCESSED = "item_processed"

   async def run_pipeline(config):
       event_bus = EventBus()

       # Register event handlers
       event_bus.on(PipelineEvents.STAGE_START, log_stage_start)
       event_bus.on(PipelineEvents.ITEM_PROCESSED, update_progress)
       event_bus.on(PipelineEvents.STAGE_ERROR, handle_stage_error)

       # Execute pipeline with event coordination
       await execute_with_events(event_bus, config)

Resource Management
-------------------

Connection Pooling
~~~~~~~~~~~~~~~~~~

Model providers use connection pooling for efficient resource utilization:

.. code-block:: python

   class OpenAIModel:
       def __init__(self, **kwargs):
           self.client = AsyncOpenAI(
               max_connections=20,
               timeout=30.0,
               max_retries=3
           )

       async def ainvoke(self, prompt):
           async with self.rate_limiter:
               return await self.client.chat.completions.create(...)

Rate Limiting
~~~~~~~~~~~~~

Automatic rate limiting prevents API quota exhaustion:

.. code-block:: python

   class RateLimiter:
       def __init__(self, requests_per_minute: int):
           self.semaphore = asyncio.Semaphore(requests_per_minute // 60)
           self.reset_interval = 60.0

       async def __aenter__(self):
           await self.semaphore.acquire()
           return self

       async def __aexit__(self, exc_type, exc_val, exc_tb):
           # Schedule semaphore release after rate limit window
           asyncio.create_task(self._delayed_release())

Memory Management
~~~~~~~~~~~~~~~~~

Streaming architecture prevents memory overflow with large datasets:

.. code-block:: python

   async def process_large_dataset(dataset_path: str):
       # Process data in chunks to manage memory
       async for chunk in read_dataset_chunks(dataset_path, chunk_size=1000):
           async for result in process_chunk(chunk):
               yield result
               # Memory is freed as results are yielded

Monitoring & Observability
--------------------------

Progress Tracking
~~~~~~~~~~~~~~~~~

Real-time progress monitoring across all pipeline stages:

.. code-block:: python

   class ProgressTracker:
       def __init__(self, total_items: int):
           self.total = total_items
           self.completed = 0
           self.errors = 0
           self.start_time = time.time()

       def update(self, success: bool = True):
           if success:
               self.completed += 1
           else:
               self.errors += 1

           # Real-time progress reporting
           if self.completed % 10 == 0:
               self._report_progress()

Performance Metrics
~~~~~~~~~~~~~~~~~~~

Comprehensive performance tracking for optimization:

.. code-block:: python

   class PerformanceMonitor:
       def __init__(self):
           self.metrics = {
               "attack_generation_time": [],
               "model_response_time": [],
               "evaluation_time": [],
               "memory_usage": [],
               "api_call_success_rate": 0.0
           }

       async def measure_operation(self, operation_name: str, operation_func):
           start_time = time.time()
           start_memory = psutil.Process().memory_info().rss

           try:
               result = await operation_func()
               success = True
           except Exception as e:
               result = None
               success = False

           end_time = time.time()
           end_memory = psutil.Process().memory_info().rss

           # Record metrics
           self.metrics[f"{operation_name}_time"].append(end_time - start_time)
           self.metrics["memory_usage"].append(end_memory - start_memory)

           return result, success

Data Integrity & Validation
---------------------------

Schema Validation
~~~~~~~~~~~~~~~~~

All data transfers include schema validation:

.. code-block:: python

   from pydantic import BaseModel, validator

   class AttackPromptData(BaseModel):
       id: str
       attack_name: str
       base_prompt: str
       attack_prompt: str
       timestamp: str

       @validator('id')
       def validate_id(cls, v):
           assert len(v) > 0, "ID cannot be empty"
           return v

Checksum Verification
~~~~~~~~~~~~~~~~~~~~~

Data integrity checks prevent corruption during processing:

.. code-block:: python

   def calculate_data_checksum(data: List[Dict]) -> str:
       content = json.dumps(data, sort_keys=True)
       return hashlib.sha256(content.encode()).hexdigest()

   def verify_data_integrity(data: List[Dict], expected_checksum: str) -> bool:
       actual_checksum = calculate_data_checksum(data)
       return actual_checksum == expected_checksum

This comprehensive interaction framework ensures HiveTraceRed operates reliably at scale while maintaining data consistency and enabling robust error recovery.