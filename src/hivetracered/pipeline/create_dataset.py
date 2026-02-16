"""
Dataset creation module that generates attack prompts by applying attacks to base prompts.
Supports regular and model-based attacks with efficient batch processing.
"""

import os
import asyncio
from typing import Dict, List, Any, Optional, Tuple, AsyncGenerator
from tqdm import tqdm

from hivetracered.attacks.base_attack import BaseAttack
from hivetracered.models.base_model import Model
from hivetracered.attacks import ModelAttack
from hivetracered.attacks.iterative_attack import IterativeAttack
from hivetracered.evaluators.base_evaluator import BaseEvaluator
from hivetracered.evaluators.scoring_judge_evaluator import ScoringJudgeEvaluator

from hivetracered.pipeline.constants import ATTACK_CLASSES

def build_attack_from_config(attack_config, attacker_model=None, target_model=None,
                             evaluator=None, evaluation_model=None, setup_evaluator_fn=None):
    """
    Construct an attack instance from configuration.

    Args:
        attack_config: String attack name or dict with attack configuration
        attacker_model: Model instance for model-based attacks
        target_model: Model instance for iterative attacks (target to jailbreak)
        evaluator: Evaluator instance for iterative attacks

    Returns:
        Configured attack instance

    Raises:
        ValueError: If attack name is unknown or required models/evaluator are missing
    """
    if isinstance(attack_config, str):
        attack_name, params = attack_config, {}
        inner_attack_cfg = None
    else:
        attack_name = attack_config.get("name", "")
        params = attack_config.get("params", {})
        inner_attack_cfg = attack_config.get("inner_attack", None)

    if attack_name not in ATTACK_CLASSES:
        raise ValueError(f"Unknown attack '{attack_name}'")
    attack_class = ATTACK_CLASSES[attack_name]["attack_class"]

    # Handle iterative attacks (TAP, PAIR)
    if issubclass(attack_class, IterativeAttack):
        attack_evaluator = None
        if not isinstance(attack_config, str) and attack_config.get("evaluator") and setup_evaluator_fn:
            attack_evaluator = setup_evaluator_fn(
                attack_config["evaluator"], evaluation_model
            )
            if not attack_evaluator:
                print(f"Warning: Per-attack evaluator config invalid for '{attack_name}'")

        if not attack_evaluator and evaluator and isinstance(evaluator, ScoringJudgeEvaluator):
            attack_evaluator = evaluator

        if not attack_evaluator and evaluation_model:
            print(f"Using default ScoringJudgeEvaluator for iterative attack '{attack_name}'")
            attack_evaluator = ScoringJudgeEvaluator(model=evaluation_model)

        if not attacker_model:
            raise ValueError(f"Attacker model is required for iterative attack '{attack_name}'")
        if not target_model:
            raise ValueError(f"Target model is required for iterative attack '{attack_name}'")
        if not attack_evaluator:
            raise ValueError(f"Evaluator is required for iterative attack '{attack_name}'")
        attack = attack_class(
            attacker_model=attacker_model,
            target_model=target_model,
            evaluator=attack_evaluator,
            **params
        )
    elif issubclass(attack_class, ModelAttack):
        if not attacker_model:
            raise ValueError(f"Attacker model is required for '{attack_name}'")
        attack = attack_class(model=attacker_model, **params)
    else:
        attack = attack_class(**params)
    if inner_attack_cfg:
        inner_attack = build_attack_from_config(inner_attack_cfg, attacker_model, target_model, evaluator,
                                                evaluation_model=evaluation_model, setup_evaluator_fn=setup_evaluator_fn)
        attack = inner_attack | attack
    return attack

def setup_attacks(
    attack_configs: List[dict],
    attacker_model: Optional[Model] = None,
    target_model: Optional[Model] = None,
    evaluator: Optional[BaseEvaluator] = None,
    evaluation_model: Optional[Model] = None,
    setup_evaluator_fn=None
) -> Dict[str, BaseAttack]:
    """
    Initialize attack instances from configuration list.

    Args:
        attack_configs: List of attack configurations
        attacker_model: Optional model for model-based and iterative attacks
        target_model: Optional target model for iterative attacks
        evaluator: Optional evaluator for iterative attacks

    Returns:
        Dictionary of attack name to attack instance mappings
    """
    attacks = {}
    for attack_config in attack_configs:
        try:
            attack = build_attack_from_config(attack_config, attacker_model, target_model, evaluator,
                                                evaluation_model=evaluation_model, setup_evaluator_fn=setup_evaluator_fn)
            attacks[attack.__class__.__name__] = attack
        except Exception as e:
            print(f"Warning: Failed to initialize attack from config {attack_config}: {str(e)}")
    return attacks

def extract_prompt_text(base_prompt: Any) -> str:
    """
    Extract prompt text from various input formats.

    Args:
        base_prompt: String or dict containing prompt

    Returns:
        Prompt text as string
    """
    if isinstance(base_prompt, str):
        return base_prompt
    elif isinstance(base_prompt, dict):
        # Try common prompt field names
        for key in ['prompt', 'Prompt', 'text', 'Text', 'question', 'Question']:
            if key in base_prompt:
                return base_prompt[key]
        raise ValueError(f"No prompt field found in dict. Available keys: {list(base_prompt.keys())}")
    else:
        raise ValueError(f"Unsupported base_prompt type: {type(base_prompt)}")

def create_prompt(base_prompt: Any, system_prompt: Optional[str] = None) -> Any:
    """
    Format a prompt with optional system instructions.

    Args:
        base_prompt: The user prompt content (string or dict)
        system_prompt: Optional system instructions

    Returns:
        String prompt or list of message dictionaries
    """
    prompt_text = extract_prompt_text(base_prompt)
    if system_prompt:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "human", "content": prompt_text}
        ]
    return prompt_text

async def generate_attack_prompt(attack: BaseAttack, base_prompt: Any,
                                system_prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Apply an attack to a single prompt.

    Args:
        attack: Attack instance to apply
        base_prompt: Original prompt content (string or dict with columns)
        system_prompt: Optional system instructions

    Returns:
        Dictionary with attack result and metadata (preserves all base_prompt columns)
    """
    prompt = create_prompt(base_prompt, system_prompt)
    attack_name = attack.__class__.__name__

    # Extract base fields if base_prompt is a dict
    base_fields = {}
    if isinstance(base_prompt, dict):
        base_fields = {k: v for k, v in base_prompt.items()}

    try:
        attack_prompt = attack.apply(prompt)
        return {
            **base_fields,  # Preserve all original columns
            "base_prompt": extract_prompt_text(base_prompt),
            "prompt": attack_prompt,
            "attack_name": attack_name,
            "attack_type": ATTACK_CLASSES[attack_name]["attack_type"],
            "attack_params": attack.get_params(),
            # "attack_timestamp": get_timestamp(),
            "error": ""
        }
    except Exception as e:
        print(f"Error generating prompt for attack {attack_name}: {str(e)}")
        return {
            **base_fields,  # Preserve all original columns
            "base_prompt": extract_prompt_text(base_prompt) if not isinstance(base_prompt, str) else base_prompt,
            "prompt": "",
            "attack_name": attack_name,
            "attack_type": ATTACK_CLASSES[attack_name]["attack_type"],
            "attack_params": attack.get_params(),
            # "attack_timestamp": get_timestamp(),
            "error": str(e)
        }

async def stream_attack(attack: BaseAttack,
                        base_prompts: List[Any], system_prompt: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Apply an attack to multiple prompts in streaming mode.

    Args:
        attack: Attack instance to apply
        base_prompts: List of original prompts (strings or dicts with columns)
        system_prompt: Optional system instructions

    Yields:
        Attack result dictionaries with metadata (preserves all base_prompt columns)
    """
    # Format all prompts
    formatted_prompts = [create_prompt(prompt, system_prompt) for prompt in base_prompts]
    attack_name = attack.__class__.__name__
    try:
        # Apply the attack to all prompts at once
        i = 0
        async for attack_prompt in attack.stream_abatch(formatted_prompts):
            # Extract base fields if base_prompt is a dict
            base_fields = {}
            if isinstance(base_prompts[i], dict):
                base_fields = {k: v for k, v in base_prompts[i].items()}

            yield {
                    **base_fields,  # Preserve all original columns
                    "base_prompt": extract_prompt_text(base_prompts[i]),
                    "prompt": attack_prompt,
                    "attack_name": attack_name,
                    "attack_type": ATTACK_CLASSES[attack_name]["attack_type"],
                    "attack_params": attack.get_params(),
                    # "attack_timestamp": get_timestamp(),
                    "error": ""
                }
            i += 1
    except Exception as e:
        print(f"Error generating prompts for model attack {attack_name}: {str(e)}")
        for base_prompt in base_prompts:
            # Extract base fields if base_prompt is a dict
            base_fields = {}
            if isinstance(base_prompt, dict):
                base_fields = {k: v for k, v in base_prompt.items()}

            yield {
                **base_fields,  # Preserve all original columns
                "base_prompt": extract_prompt_text(base_prompt),
                "prompt": "",
                "attack_name": attack_name,
                "attack_type": ATTACK_CLASSES[attack_name]["attack_type"],
                "attack_params": attack.get_params(),
                # "attack_timestamp": get_timestamp(),
                "error": str(e)
            }


async def stream_attack_prompts(attacks: Dict[str, BaseAttack],
                                base_prompts: List[Any], system_prompt: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Process all attacks on all base prompts and stream results.

    Args:
        attacks: Dictionary of attack instances
        base_prompts: List of original prompts (strings or dicts with columns)
        system_prompt: Optional system instructions

    Yields:
        Attack result dictionaries with metadata (preserves all base_prompt columns)
    """
    
    # Initialize result list
    attack_prompts = []
    
    if attacks:
        # Process regular attacks with tqdm for progress tracking
        for i, (name, attack) in tqdm(enumerate(attacks.items()), total=len(attacks), desc="Processing Attacks"):
            async for attack_prompt_data in stream_attack(attack, base_prompts, system_prompt):
                attack_prompts.append(attack_prompt_data)
                yield attack_prompt_data
    