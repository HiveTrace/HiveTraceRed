"""
Model responses stage that processes prompts through LLMs and collects their outputs.
Handles streaming API interactions, error recovery, and response standardization.
"""

import os
from typing import List, Dict, Any, AsyncGenerator

import asyncio
from hivetracered.pipeline.utils.data_io import save_pipeline_results

from hivetracered.models.base_model import Model

async def stream_model_responses(
    model: Model,
    attack_prompts: List[Dict[str, Any]],
    output_dir: str = "pipeline/data",
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Process attack prompts through a model and stream responses as they become available.
    
    Args:
        model: Language model instance to query
        attack_prompts: List of attack prompt dictionaries with at least a 'prompt' field
        output_dir: Directory for saving results (if enabled)
        
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
    print(f"Processing {total_prompts} prompts for model {model.__class__.__name__}...")
    
    # Create a mapping from prompt index to attack prompt data
    prompt_index_to_data = [prompt_data for prompt_data in attack_prompts]
    prompts = [prompt_data.get("prompt", "") for prompt_data in attack_prompts]

    # Keep track of processed prompts
    processed_count = 0

    # Process prompts and handle responses as they complete
    # Individual errors are now handled at the model level
    async for response in model.stream_abatch(prompts):
        # Get corresponding prompt data
        prompt_data = prompt_index_to_data[processed_count]

        # Check if this response has an error
        has_error = "error" in response

        # Create response data
        response_data = {
            **prompt_data,
            "model": model.__class__.__name__,
            "model_params": model.get_params(),
            "response": response.get("content", ""),
            "raw_response": response,
            # "response_timestamp": get_timestamp(),
            "is_blocked": model.is_answer_blocked(response),
        }

        # Add error field if present
        if has_error:
            response_data["error"] = response["error"]

        # Yield the response data
        yield response_data

        # Increment processed count
        processed_count += 1

    print(f"✓ Processed {processed_count} responses from model {model.__class__.__name__}")


