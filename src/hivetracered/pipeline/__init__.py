"""
Pipeline module for orchestrating the red teaming evaluation process.
Provides components for creating attack datasets, generating model responses,
evaluating responses, and saving results in a streamlined workflow.
"""

# Constants
from hivetracered.pipeline.constants import (
    MODEL_CLASSES,
    ATTACK_TYPES,
    ATTACK_CLASSES,
    EVALUATOR_CLASSES
)

from hivetracered.pipeline.create_dataset import setup_attacks, stream_attack_prompts
from hivetracered.pipeline.model_responses import stream_model_responses
from hivetracered.pipeline.evaluation import stream_evaluated_responses
from hivetracered.pipeline.utils import save_pipeline_results

__all__ = [
    "MODEL_CLASSES",
    "ATTACK_TYPES",
    "ATTACK_CLASSES",
    "EVALUATOR_CLASSES",
    "setup_attacks",
    "stream_attack_prompts",
    "stream_model_responses",
    "stream_evaluated_responses",
    "save_pipeline_results"
] 