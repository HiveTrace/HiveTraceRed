"""
Model responses stage that processes prompts through LLMs and collects their outputs.
Handles streaming API interactions, error recovery, and response standardization.
"""

import logging
from typing import Any
from collections.abc import AsyncGenerator

from hivetracered.models.base_model import Model

logger = logging.getLogger(__name__)


async def stream_model_responses(
    model: Model,
    attack_prompts: list[dict[str, Any]],
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Process attack prompts through a model and stream responses as they become available.

    Args:
        model: Language model instance to query
        attack_prompts: List of attack prompt dictionaries with at least a 'prompt' field

    Yields:
        Response dictionaries containing:
        - All original fields from the prompt dictionary
        - 'model': Name of the model class used
        - 'model_params': Configuration parameters of the model
        - 'response': Text response content from the model
        - 'raw_response': Complete response object from the model
        - 'is_blocked': Whether the response was blocked by safety mechanisms
        - 'error': Error message if request failed (only present on error)
    """
    total_prompts = len(attack_prompts)
    logger.info(f"Processing {total_prompts} prompts for model {model.__class__.__name__}...")

    prompts = [prompt_data.get("prompt", "") for prompt_data in attack_prompts]

    processed_count = 0

    async for response in model.stream_abatch(prompts):
        prompt_data = attack_prompts[processed_count]

        has_error = "error" in response

        response_data = {
            **prompt_data,
            "model": model.__class__.__name__,
            "model_params": model.get_params(),
            "response": response.get("content", ""),
            "raw_response": response,
            "is_blocked": model.is_answer_blocked(response),
        }

        if has_error:
            response_data["error"] = response["error"]

        yield response_data

        processed_count += 1

    logger.info(f"✓ Processed {processed_count} responses from model {model.__class__.__name__}")
