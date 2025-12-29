"""
HiveTraceRed - LLM Red Teaming Framework

A defensive security framework for systematically testing Large Language Model vulnerabilities
through attack methodologies and evaluation pipelines.

Main Components:
- attacks: 80+ adversarial attack implementations across 10 categories
- models: Unified interface for various LLM providers
- evaluators: Safety assessment tools for detecting harmful outputs
- pipeline: Orchestration tools for attack generation, testing, and evaluation
"""

__version__ = "1.0.6"

# Import core attack classes
from hivetracered.attacks import (
    BaseAttack,
    TemplateAttack,
    ModelAttack,
    AlgoAttack,
    ComposedAttack
)

# Import core model classes
from hivetracered.models import Model

# Import core evaluator classes
from hivetracered.evaluators import BaseEvaluator

# Import pipeline components
from hivetracered.pipeline import (
    MODEL_CLASSES,
    ATTACK_TYPES,
    ATTACK_CLASSES,
    EVALUATOR_CLASSES,
    setup_attacks,
    stream_attack_prompts,
    stream_model_responses,
    stream_evaluated_responses,
    save_pipeline_results
)

__all__ = [
    # Version
    "__version__",
    # Base classes
    "BaseAttack",
    "TemplateAttack",
    "ModelAttack",
    "AlgoAttack",
    "ComposedAttack",
    "Model",
    "BaseEvaluator",
    # Pipeline
    "MODEL_CLASSES",
    "ATTACK_TYPES",
    "ATTACK_CLASSES",
    "EVALUATOR_CLASSES",
    "setup_attacks",
    "stream_attack_prompts",
    "stream_model_responses",
    "stream_evaluated_responses",
    "save_pipeline_results",
]
