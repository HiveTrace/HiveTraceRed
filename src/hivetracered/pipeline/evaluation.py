"""
Evaluation stage that assesses model responses for safety and policy compliance.
Processes responses through evaluators to determine if attacks were successful
and enriches response data with evaluation results and metrics.
"""

import logging
from typing import Any
from collections.abc import AsyncGenerator

from hivetracered.evaluators import BaseEvaluator

logger = logging.getLogger(__name__)

RESPONSE_BLOCKED = "Response was blocked"
RESPONSE_ERROR = "Request failed"


def _skip_reason(response_data: dict[str, Any]) -> str:
    """Reason a response was not sent to the evaluator: failed request vs blocked."""
    return RESPONSE_ERROR if response_data.get("error") else RESPONSE_BLOCKED


async def stream_evaluated_responses(
    evaluator: BaseEvaluator,
    responses: list[dict[str, Any]],
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Process and evaluate model responses, yielding results as they become available.

    Handles both blocked and unblocked responses differently:
    - Blocked responses (is_blocked=True) are marked as unsuccessful without evaluation
    - Unblocked responses are processed through the evaluator for assessment

    Args:
        evaluator: Evaluator instance to assess model responses
        responses: List of model response dictionaries to evaluate

    Yields:
        Enriched response dictionaries with evaluation results, in the same order as input responses
    """
    if not responses:
        return

    model_name = responses[0].get("model", "unknown")

    total_responses = len(responses)
    logger.info(f"Evaluating {total_responses} responses from {model_name}...")

    unblocked_responses_data = []
    unblocked_responses_indices = []

    # Identify which responses need evaluation: not blocked and not a failed request.
    # Failed requests (error key) carry empty content; scoring them would pollute results.
    for i, response_data in enumerate(responses):
        if not response_data.get("is_blocked") and not response_data.get("error"):
            unblocked_responses_data.append(response_data)
            unblocked_responses_indices.append(i)

    # Extract prompts and responses for batch evaluation
    base_prompts = [data.get("base_prompt", "") for data in unblocked_responses_data]
    unblocked_responses = [data.get("response", "") for data in unblocked_responses_data]

    # Process responses in order, yielding blocked ones immediately
    i = 0
    while (not i in unblocked_responses_indices) and (i < total_responses):
        yield {
            **responses[i],
            "evaluation": {
                "success": False,
                "reason": _skip_reason(responses[i])
            },
            "evaluator": "",
            "success": False,
            "evaluator_params": {},
            "evaluation_error": "",
        }
        i += 1

    # Process unblocked responses through the evaluator
    async for batch_result in evaluator.stream_abatch(base_prompts, unblocked_responses):
        if i in unblocked_responses_indices:
            yield {
                **responses[i],
                "success": batch_result["success"],
                "evaluation": batch_result,
                "evaluator": evaluator.__class__.__name__,
                "evaluator_params": evaluator.get_params(),
            }
            i += 1

        # Yield any blocked responses between unblocked ones
        while (not i in unblocked_responses_indices) and (i < total_responses):
            yield {
                **responses[i],
                "evaluation": {
                    "success": False,
                    "reason": RESPONSE_BLOCKED
                },
                "evaluator": "",
                "success": False,
                "evaluator_params": {},
                "evaluation_error": "",
            }
            i += 1
