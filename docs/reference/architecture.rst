Architecture & Design
=====================

This document provides a comprehensive overview of HiveTraceRed's system architecture, component interactions, design principles, and interaction patterns for LLM security testing.

System Overview
---------------

HiveTraceRed is designed as a modular, extensible framework for systematic LLM red teaming. The architecture follows a pipeline-based approach that separates concerns across distinct components:

.. code-block::

   ┌─────────────────────────────────────────────────────────────────┐
   │                    HiveTraceRed Framework                       │
   ├─────────────────────────────────────────────────────────────────┤
   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
   │  │   Attacks   │  │   Models    │  │ Evaluators  │              │
   │  │             │  │             │  │             │              │
   │  │ • Template  │  │ • OpenAI    │  │ • Keyword   │              │
   │  │ • Algorithm │  │ • GigaChat  │  │ • Model     │              │
   │  │ • Model     │  │ • YandexGPT │  │ • WildGuard │              │
   │  │   Based     │  │ • Gemini    │  │             │              │
   │  └─────────────┘  └─────────────┘  └─────────────┘              │
   │                           │                                     │
   │  ┌─────────────────────────┼─────────────────────────┐          │
   │  │                Pipeline Engine                    │          │
   │  │                                                   │          │
   │  │ Stage 1: Attack Prompt Generation                 │          │
   │  │ Stage 2: Model Response Collection                │          │
   │  │ Stage 3: Response Evaluation & Analysis           │          │
   │  └───────────────────────────────────────────────────┘          │
   │                           │                                     │
   │  ┌─────────────────────────┼─────────────────────────┐          │
   │  │              Results & Analysis                   │          │
   │  │                                                   │          │
   │  │ • Attack Success Metrics                          │          │
   │  │ • Vulnerability Reports                           │          │
   │  │ • Response Classifications                        │          │
   │  └───────────────────────────────────────────────────┘          │
   └─────────────────────────────────────────────────────────────────┘

Core Components
---------------

Attack System
~~~~~~~~~~~~~

The attack system implements a hierarchical architecture with three primary attack types:

**Template Attacks**
   Predefined text patterns that modify prompts using static templates. These attacks require no external models and operate deterministically.

   Examples: ``DANAttack``, ``JSONOutputAttack``, ``Base64Attack``

**Algorithmic Attacks**
   Programmatic transformations that apply mathematical or linguistic algorithms to modify prompt structure.

   Examples: ``DisemvowelAttack``, ``TypoAttack``, ``VerticalTextAttack``

**Model-Based Attacks**
   Dynamic attacks that use LLMs to generate contextually relevant adversarial prompts.

   Examples: ``AuthorityEndorsementAttack``, ``PersuasionAttack``, ``SocialProofAttack``

**Attack Categories**
   Attacks are organized into 10 tactical categories:

   - **Simple Instructions**: Direct prompt injection attempts
   - **Roleplay**: Character or persona-based manipulations
   - **Persuasion**: Social engineering and psychological manipulation
   - **Output Formatting**: Response structure and encoding manipulation
   - **Context Switching**: Instruction override and context redirection
   - **Token Smuggling**: Content encoding and obfuscation techniques
   - **Text Structure Modification**: Linguistic and formatting transformations
   - **Task Deflection**: Indirect approach and misdirection tactics
   - **Irrelevant Information**: Distraction and noise injection
   - **In-Context Learning**: Few-shot and example-based manipulation

Model Abstraction Layer
~~~~~~~~~~~~~~~~~~~~~~~

The framework provides a unified interface for multiple LLM providers through the ``BaseModel`` class:

.. code-block:: python

   class BaseModel(ABC):
       @abstractmethod
       def invoke(self, prompt: Union[str, List[Dict[str, str]]]) -> Dict[str, Any]:
           """Synchronous model invocation"""
           pass

       @abstractmethod
       async def ainvoke(self, prompt: Union[str, List[Dict[str, str]]]) -> Dict[str, Any]:
           """Asynchronous model invocation"""
           pass

**Supported Providers**:

- **OpenAI**: GPT-3.5, GPT-4 family models
- **Google**: Gemini and PaLM models
- **Yandex**: YandexGPT family
- **Sber**: GigaChat models

Each provider implementation handles authentication, rate limiting, and response formatting specific to that service.

Evaluation Framework
~~~~~~~~~~~~~~~~~~~~

The evaluation system uses a pluggable architecture supporting multiple assessment approaches:

**Keyword Evaluator**
   Pattern-based detection using predefined harmful content indicators and regular expressions.

**Model Evaluator**
   LLM-based assessment where models evaluate response harmfulness using structured prompts.

**WildGuard Evaluators**
   Specialized evaluators optimized for specific content types and languages:

   - ``WildGuardGPTEvaluator``: General English content evaluation
   - ``WildGuardGPTRuEvaluator``: Russian language content evaluation
   - ``WildGuardGPTRuHalEvaluator``: Russian hallucination detection

Pipeline Architecture
---------------------

The framework operates through a three-stage asynchronous pipeline that processes data in streams for memory efficiency and scalability.

Stage 1: Attack Prompt Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block::

   Base Prompts → [Attack Selection] → [Attack Application] → Attack Prompts
        │              │                       │                    │
        │              │                       │                    │
   ┌────▼────┐    ┌────▼────┐           ┌────▼────┐         ┌────▼────┐
   │ Input   │    │ Attack  │           │ Prompt  │         │ Output  │
   │ Dataset │    │ Config  │           │ Transform│         │ Dataset │
   │         │    │         │           │         │         │         │
   │ • Text  │    │ • Type  │           │ • Apply │         │ • ID    │
   │ • JSON  │    │ • Params│           │ • Validate        │ • Attack│
   │ • CSV   │    │ • Model │           │ • Metadata        │ • Prompt│
   │ • Parquet     │         │           │         │         │ • Metadata
   └─────────┘    └─────────┘           └─────────┘         └─────────┘

**Process Flow**:

1. **Input Processing**: Load base prompts from various formats (text, JSON, CSV, Parquet)
2. **Attack Initialization**: Configure and instantiate attack classes with parameters
3. **Batch Processing**: Apply attacks to prompts using async streaming for efficiency
4. **Metadata Generation**: Track attack types, parameters, and transformation details
5. **Output Serialization**: Save structured attack prompts with full traceability

Stage 2: Model Response Collection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block::

   Attack Prompts → [Model Selection] → [Response Generation] → Model Responses
         │              │                        │                     │
         │              │                        │                     │
   ┌─────▼─────┐   ┌─────▼─────┐          ┌─────▼─────┐         ┌─────▼─────┐
   │ Attack    │   │ Target    │          │ Response  │         │ Response  │
   │ Dataset   │   │ Model     │          │ Collection│         │ Dataset   │
   │           │   │           │          │           │         │           │
   │ • Prompt  │   │ • Provider│          │ • Invoke  │         │ • Request │
   │ • Attack  │   │ • Config  │          │ • Retry   │         │ • Response│
   │ • Metadata│   │ • Auth    │          │ • Rate    │         │ • Timing  │
   │           │   │           │          │   Limit   │         │ • Status  │
   └───────────┘   └───────────┘          └───────────┘         └───────────┘

**Process Flow**:

1. **Model Setup**: Initialize target model with authentication and configuration
2. **Request Management**: Handle rate limiting, retries, and error recovery
3. **Response Collection**: Capture model outputs with timing and metadata
4. **Status Tracking**: Monitor success/failure rates and response quality
5. **Data Persistence**: Store responses with full request context

Stage 3: Response Evaluation & Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block::

   Model Responses → [Evaluator Selection] → [Safety Assessment] → Evaluation Results
          │               │                         │                      │
          │               │                         │                      │
   ┌──────▼──────┐  ┌─────▼─────┐           ┌──────▼──────┐       ┌──────▼──────┐
   │ Response    │  │ Evaluator │           │ Content     │       │ Results     │
   │ Dataset     │  │ Config    │           │ Analysis    │       │ Dataset     │
   │             │  │           │           │             │       │             │
   │ • Text      │  │ • Type    │           │ • Harmful   │       │ • Score     │
   │ • Context   │  │ • Model   │           │ • Safe      │       │ • Category  │
   │ • Metadata  │  │ • Params  │           │ • Uncertain │       │ • Reasoning │
   │             │  │           │           │ • Reasoning │       │ • Success   │
   └─────────────┘  └───────────┘           └─────────────┘       └─────────────┘

**Process Flow**:

1. **Evaluator Setup**: Configure assessment models and evaluation criteria
2. **Content Analysis**: Analyze responses for harmful content and policy violations
3. **Classification**: Categorize responses as harmful, safe, or uncertain
4. **Scoring**: Generate quantitative safety and quality metrics
5. **Report Generation**: Compile detailed evaluation results with reasoning

Data Flow & Storage
-------------------

The framework uses a structured data flow approach with intermediate result caching:

**File Formats**:

- **JSON**: Human-readable intermediate results and configuration
- **Parquet**: Efficient columnar storage for large datasets
- **CSV**: Compatibility with external analysis tools
- **YAML**: Configuration files and pipeline definitions

**Data Schema**:

.. code-block:: python

   # Attack Prompt Schema
   {
       "id": "unique_identifier",
       "attack_name": "attack_class_name",
       "base_prompt": "original_input_text",
       "attack_prompt": "transformed_prompt",
       "attack_params": {...},
       "timestamp": "2024-01-01T00:00:00Z"
   }

   # Model Response Schema
   {
       "id": "corresponding_attack_id",
       "model_name": "provider_model_name",
       "prompt": "input_prompt",
       "response": "model_output",
       "response_time": 1.23,
       "token_count": 150,
       "status": "success|error|timeout"
   }

   # Evaluation Result Schema
   {
       "id": "corresponding_response_id",
       "evaluator_name": "evaluator_class_name",
       "harmful": true|false,
       "score": 0.95,
       "category": "violence|hate|sexual|etc",
       "reasoning": "explanation_text",
       "success": true|false
   }

Configuration & Extensibility
-----------------------------

The framework supports extensive configuration through YAML files:

.. code-block:: yaml

   # Pipeline Control
   stages:
     create_attack_prompts: true
     get_model_responses: true
     evaluate_responses: true

   # Model Configuration
   response_model:
     name: "gpt-4"
     params:
       temperature: 0.0
       max_tokens: 500

   # Attack Selection
   attacks:
     - name: "DANAttack"
       params: {}
     - name: "AuthorityEndorsementAttack"
       params:
         authority_type: "expert"

   # Evaluation Setup
   evaluator:
     name: "WildGuardGPTRuEvaluator"
     params:
       threshold: 0.8

**Extension Points**:

1. **Custom Attacks**: Inherit from ``BaseAttack`` and implement required methods
2. **Model Providers**: Implement ``BaseModel`` interface for new LLM services
3. **Evaluators**: Extend ``BaseEvaluator`` for specialized assessment criteria
4. **Pipeline Stages**: Add new processing stages through the streaming architecture

Security & Safety Considerations
--------------------------------

**Defensive Design**:

- All attacks are designed for defensive security research only
- No support for credential harvesting or malicious data collection
- Rate limiting and request throttling prevent service abuse
- Comprehensive logging for audit and compliance requirements

**Ethical Guidelines**:

- Framework restricted to authorized security testing
- Results should be used to improve model safety
- Responsible disclosure of discovered vulnerabilities
- Compliance with platform terms of service

Performance & Scalability
-------------------------

**Async Architecture**:
   Stream-based processing enables handling large datasets without memory constraints

**Batch Processing**:
   Configurable batch sizes optimize throughput while respecting API limits

**Caching Strategy**:
   Intermediate results stored to enable pipeline resumption and partial re-runs

**Resource Management**:
   Automatic retry logic and error recovery for robust long-running evaluations

**Monitoring**:
   Built-in progress tracking and performance metrics collection

Component Interactions
----------------------

System Interaction Overview
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

HiveTraceRed components interact through well-defined interfaces using async streams, dependency injection, and event-driven patterns. The system maintains loose coupling while ensuring data consistency and traceability.

Core Interaction Patterns
~~~~~~~~~~~~~~~~~~~~~~~~~~

Dependency Injection
^^^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^

All data processing uses async generators to enable efficient memory usage and real-time processing. Each pipeline stage streams data through async generators, allowing for concurrent processing and minimal memory footprint.

Error Handling & Recovery
^^^^^^^^^^^^^^^^^^^^^^^^^^

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

Communication Protocols
~~~~~~~~~~~~~~~~~~~~~~~

Inter-Component Messaging
^^^^^^^^^^^^^^^^^^^^^^^^^

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

Resource Management
~~~~~~~~~~~~~~~~~~~

Connection Pooling
^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^

Automatic rate limiting prevents API quota exhaustion through semaphores and adaptive rate adjustment based on error patterns.

Memory Management
^^^^^^^^^^^^^^^^^

Streaming architecture prevents memory overflow with large datasets by processing data in chunks and yielding results incrementally.

Monitoring & Observability
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Progress Tracking
^^^^^^^^^^^^^^^^^

Real-time progress monitoring tracks completion rates, errors, and performance across all pipeline stages.

Performance Metrics
^^^^^^^^^^^^^^^^^^^

Comprehensive performance tracking includes timing metrics, memory usage, API call success rates, and bottleneck identification for optimization.

Data Integrity & Validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Schema Validation
^^^^^^^^^^^^^^^^^

All data transfers include schema validation using Pydantic models to ensure data consistency and type safety.

Checksum Verification
^^^^^^^^^^^^^^^^^^^^^

Data integrity checks prevent corruption during processing through SHA-256 checksums of serialized data.