"""
Model responses stage that processes prompts through LLMs and collects their outputs.
Handles streaming API interactions, error recovery, and response standardization.
"""

import logging
from typing import Any
from collections.abc import AsyncGenerator

from hivetracered.models.base_model import Model

logger = logging.getLogger(__name__)

# Stop sending requests after this many consecutive failures (dead key, no balance,
# wrong endpoint — every following request would fail too). 0 disables the breaker.
CONSECUTIVE_FAILURES_DEFAULT = 3


async def stream_model_responses(
    model: Model,
    attack_prompts: list[dict[str, Any]],
    consecutive_failures: int = CONSECUTIVE_FAILURES_DEFAULT,
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

    # Records that already failed in Stage 1 (e.g. an attack model error) carry a
    # non-empty 'error'. Don't send their (empty) prompt to the target — pass the
    # error straight through. Only the rest are queried, in order.
    send_prompts = [pd.get("prompt", "") for pd in attack_prompts if not pd.get("error")]

    def _response_data(prompt_data: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        data = {
            **prompt_data,
            "model": model.__class__.__name__,
            "model_params": model.get_params(),
            "response": response.get("content", ""),
            "raw_response": response,
            "is_blocked": model.is_answer_blocked(response),
        }
        if response.get("error"):
            data["error"] = response["error"]
        return data

    # Single pass over attack_prompts: pull a target response on demand for each
    # prompt actually sent, so output stays in input order without an index map.
    gen = model.stream_abatch(send_prompts)
    consecutive = 0
    broken_error: str | None = None
    try:
        for prompt_data in attack_prompts:
            if prompt_data.get("error"):
                # Stage-1 failure: not sent, carry the error through unchanged.
                yield {
                    **prompt_data,
                    "model": model.__class__.__name__,
                    "model_params": model.get_params(),
                    "response": "",
                    "raw_response": {},
                    "is_blocked": False,
                }
                continue
            if broken_error is not None:
                # Circuit breaker already tripped: mark without sending.
                yield _response_data(prompt_data, {
                    "content": "", "error": f"skipped_after_failures: {broken_error}",
                })
                continue

            response = await gen.__anext__()
            yield _response_data(prompt_data, response)
            consecutive = consecutive + 1 if "error" in response else 0

            # Circuit breaker: too many failures in a row means a global fault (dead
            # key, no balance) — stop sending and mark the rest as errors.
            if consecutive_failures and consecutive >= consecutive_failures:
                broken_error = response.get("error", "too many consecutive failures")
                logger.warning(
                    "Circuit breaker tripped after %d consecutive errors for model %s; "
                    "marking remaining prompts as skipped",
                    consecutive, model.__class__.__name__,
                )
    finally:
        # aclose() cancels tasks still blocked on the concurrency semaphore; up to
        # max_concurrency in-flight requests may still finish.
        await gen.aclose()

    logger.info(f"✓ Processed {total_prompts} responses from model {model.__class__.__name__}")
