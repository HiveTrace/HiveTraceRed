"""
Evaluation stage that assesses model responses for safety and policy compliance.
Processes responses through evaluators to determine if attacks were successful
and enriches response data with evaluation results and metrics.
"""

from typing import Dict, List, Any, Optional, AsyncGenerator

from hivetracered.evaluators import BaseEvaluator, ModelEvaluator
    

async def evaluate_response(
    evaluator: BaseEvaluator,
    response_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluate a single model response using the provided evaluator.
    
    Args:
        evaluator: Evaluator instance to use for assessment
        response_data: Dictionary containing model response and metadata
        
    Returns:
        Enriched dictionary with original data plus evaluation results:
        - 'evaluation': Dictionary containing detailed assessment results
        - 'evaluator': Name of the evaluator used
        - 'success': Boolean indicating if the model response was safe (true = no harmful content)
        - 'evaluator_params': Configuration parameters of the evaluator
        - 'evaluation_error': Any errors encountered during evaluation
    """
    if response_data.get("is_blocked", False):
        return {
            **response_data,
            "evaluation": {
                "success": False,
                "reason": "Response was blocked"
            },
            "evaluator": "",
            "success": False,
            "evaluator_params": {},
            "evaluation_error": "",
        }
    
    try:
        # Get prompt and response text
        base_prompt = response_data.get("base_prompt", "")
        response = response_data.get("response", "")
        
        # Run evaluation
        result = evaluator.evaluate(base_prompt, response)
        
        # Add evaluation to the data
        return {
            **response_data,
            "evaluation": result,
            "evaluator": evaluator.__class__.__name__,
            "success": result["success"],
            "evaluator_params": evaluator.get_params(),
            "evaluation_error": "",
        }
    
    except Exception as e:
        # Handle evaluation errors
        error_msg = f"Evaluation error: {str(e)}"
        print(error_msg)
        
        return {
            **response_data,
            "evaluation": {
                "success": False,
                "score": 0,
                "reason": error_msg
            },
            "evaluator": evaluator.__class__.__name__,
            "success": False,
            "evaluator_params": evaluator.get_params(),
            "evaluation_error": str(e)
        }

async def stream_evaluated_responses(
    evaluator: BaseEvaluator,
    responses: List[Dict[str, Any]],
) -> AsyncGenerator[Dict[str, Any], None]:
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
    print(f"Evaluating {total_responses} responses from {model_name}...")
    
    unblocked_responses_data = []
    unblocked_responses_indices = []
    
    # Identify which responses are not blocked and need evaluation
    for i, response_data in enumerate(responses):
        if not response_data.get("is_blocked"):
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
                "reason": "Response was blocked"
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
                    "reason": "Response was blocked"
                },
                "evaluator": "",
                "success": False,
                "evaluator_params": {},
                "evaluation_error": "",
            }
            i += 1
