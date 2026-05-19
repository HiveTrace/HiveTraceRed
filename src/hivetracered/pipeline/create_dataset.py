"""
Dataset creation module that generates attack prompts by applying attacks to base prompts.
Supports regular and model-based attacks with efficient batch processing.
"""

import logging
from typing import Any
from collections.abc import AsyncGenerator
from tqdm import tqdm

from hivetracered.attacks.base_attack import BaseAttack
from hivetracered.models.base_model import Model
from hivetracered.attacks import ModelAttack
from hivetracered.attacks.iterative_attack import IterativeAttack
from hivetracered.evaluators.base_evaluator import BaseEvaluator
from hivetracered.evaluators.scoring_judge_evaluator import ScoringJudgeEvaluator

from hivetracered.pipeline.constants import ATTACK_CLASSES

logger = logging.getLogger(__name__)


def _parse_attack_config(attack_config):
    if isinstance(attack_config, str):
        return attack_config, {}, None
    attack_name = attack_config.get("name", "")
    params = attack_config.get("params", {})
    inner_attack_cfg = attack_config.get("inner_attack", None)
    return attack_name, params, inner_attack_cfg


def _resolve_iterative_evaluator(attack_config, attack_name, evaluator,
                                 evaluation_model, setup_evaluator_fn):
    attack_evaluator = None
    if not isinstance(attack_config, str) and attack_config.get("evaluator") and setup_evaluator_fn:
        attack_evaluator = setup_evaluator_fn(
            attack_config["evaluator"], evaluation_model
        )
        if not attack_evaluator:
            logger.warning(f"Per-attack evaluator config invalid for '{attack_name}'")

    if not attack_evaluator and evaluator and isinstance(evaluator, ScoringJudgeEvaluator):
        attack_evaluator = evaluator

    if not attack_evaluator and evaluation_model:
        logger.info(f"Using default ScoringJudgeEvaluator for iterative attack '{attack_name}'")
        attack_evaluator = ScoringJudgeEvaluator(model=evaluation_model)

    return attack_evaluator


def _build_iterative_attack(attack_class, attack_config, attack_name, params,
                            attacker_model, target_model, evaluator,
                            evaluation_model, setup_evaluator_fn):
    attack_evaluator = _resolve_iterative_evaluator(
        attack_config, attack_name, evaluator, evaluation_model, setup_evaluator_fn
    )

    if not attacker_model:
        raise ValueError(f"Attacker model is required for iterative attack '{attack_name}'")
    if not target_model:
        raise ValueError(f"Target model is required for iterative attack '{attack_name}'")
    if not attack_evaluator:
        raise ValueError(f"Evaluator is required for iterative attack '{attack_name}'")

    return attack_class(
        attacker_model=attacker_model,
        target_model=target_model,
        evaluator=attack_evaluator,
        **params
    )


def _build_conversational_attack(attack_class, attack_name, params,
                                 attacker_model, target_model, evaluator,
                                 evaluation_model, setup_evaluator_fn=None):
    """Build a multi-turn conversational attack (CrescendoAttack).

    Judge resolution, in priority order:
      1. ``params["refusal_judge"]`` / ``params["success_judge"]`` — if either
         is a dict, it is treated as an evaluator config and resolved via
         ``setup_evaluator_fn`` (``evaluation_model`` is injected for
         ``ModelEvaluator`` subclasses). Already-instantiated evaluators are
         passed through unchanged. This lets YAML configure each judge with
         its own threshold/model.
      2. ``success_judge`` only — falls back to the supplied ``evaluator``
         (any subclass; Crescendo reads only ``success`` from its verdict),
         else to ``ScoringJudgeEvaluator(evaluation_model)`` with default
         threshold. In the multi-dataset runner, ``evaluator`` is the per-
         dataset evaluator (e.g. ``WildGuardGPTEvaluator``), so each dataset
         drives Crescendo's success criterion with its own grader.
      3. ``refusal_judge`` — left at ``None`` so ``CrescendoAttack.__init__``
         applies its own ``KeywordEvaluator()`` default (offline, no per-turn
         LLM call). The top-level ``evaluator`` is never auto-promoted into
         the refusal slot; configure it explicitly via ``params.refusal_judge``
         if you want LLM-graded refusal detection.
    """
    if not attacker_model:
        raise ValueError(f"Attacker model is required for conversational attack '{attack_name}'")
    if not target_model:
        raise ValueError(f"Target model is required for conversational attack '{attack_name}'")

    # Resolve dict-shaped judge configs in params into evaluator instances.
    params = dict(params)
    for key in ("refusal_judge", "success_judge"):
        value = params.get(key)
        if isinstance(value, dict):
            if not setup_evaluator_fn:
                raise ValueError(
                    f"Per-judge config for '{key}' in attack '{attack_name}' requires "
                    f"setup_evaluator_fn; pass it through build_attack_from_config."
                )
            resolved = setup_evaluator_fn(value, evaluation_model)
            if resolved is None:
                raise ValueError(
                    f"Failed to build '{key}' for conversational attack '{attack_name}' "
                    f"from config {value!r}"
                )
            params[key] = resolved

    refusal_judge = params.pop("refusal_judge", None)
    success_judge = params.pop("success_judge", None)

    if success_judge is None:
        if evaluator is not None:
            success_judge = evaluator
        elif evaluation_model:
            success_judge = ScoringJudgeEvaluator(model=evaluation_model)
        else:
            raise ValueError(
                f"Evaluator or evaluation_model is required for conversational attack '{attack_name}' "
                f"(success judge cannot be defaulted)"
            )

    kwargs = {"success_judge": success_judge, **params}
    if refusal_judge is not None:
        kwargs["refusal_judge"] = refusal_judge

    return attack_class(
        attacker_model=attacker_model,
        target_model=target_model,
        **kwargs,
    )


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
    attack_name, params, inner_attack_cfg = _parse_attack_config(attack_config)

    if attack_name not in ATTACK_CLASSES:
        raise ValueError(f"Unknown attack '{attack_name}'")
    attack_class = ATTACK_CLASSES[attack_name]["attack_class"]

    if ATTACK_CLASSES[attack_name]["attack_type"] == "conversational":
        attack = _build_conversational_attack(
            attack_class, attack_name, params,
            attacker_model, target_model, evaluator, evaluation_model,
            setup_evaluator_fn=setup_evaluator_fn,
        )
    elif issubclass(attack_class, IterativeAttack):
        attack = _build_iterative_attack(
            attack_class, attack_config, attack_name, params,
            attacker_model, target_model, evaluator,
            evaluation_model, setup_evaluator_fn,
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
    attack_configs: list[dict],
    attacker_model: Model | None = None,
    target_model: Model | None = None,
    evaluator: BaseEvaluator | None = None,
    evaluation_model: Model | None = None,
    setup_evaluator_fn=None
) -> dict[str, BaseAttack]:
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
            logger.warning(f"Failed to initialize attack from config {attack_config}: {str(e)}")
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


def create_prompt(base_prompt: Any, system_prompt: str | None = None) -> Any:
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


async def stream_attack(attack: BaseAttack,
                        base_prompts: list[Any], system_prompt: str | None = None) -> AsyncGenerator[dict[str, Any], None]:
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
            # Multi-turn attacks (e.g. CrescendoAttack) yield (prompt_str, metadata_dict);
            # single-turn attacks yield just the prompt. Split here so the row schema is uniform.
            if isinstance(attack_prompt, tuple) and len(attack_prompt) == 2:
                prompt_value, prompt_metadata = attack_prompt
            else:
                prompt_value, prompt_metadata = attack_prompt, {}

            # Extract base fields if base_prompt is a dict
            base_fields = {}
            if isinstance(base_prompts[i], dict):
                base_fields = {k: v for k, v in base_prompts[i].items()}

            yield {
                    **base_fields,  # Preserve all original columns
                    "base_prompt": extract_prompt_text(base_prompts[i]),
                    "prompt": prompt_value,
                    "metadata": prompt_metadata,
                    "attack_name": attack_name,
                    "attack_type": ATTACK_CLASSES[attack_name]["attack_type"],
                    "attack_params": attack.get_params(),
                    "error": ""
                }
            i += 1
    except Exception as e:
        logger.error(f"Error generating prompts for model attack {attack_name}: {str(e)}")
        for base_prompt in base_prompts:
            # Extract base fields if base_prompt is a dict
            base_fields = {}
            if isinstance(base_prompt, dict):
                base_fields = {k: v for k, v in base_prompt.items()}

            yield {
                **base_fields,  # Preserve all original columns
                "base_prompt": extract_prompt_text(base_prompt),
                "prompt": "",
                "metadata": {},
                "attack_name": attack_name,
                "attack_type": ATTACK_CLASSES[attack_name]["attack_type"],
                "attack_params": attack.get_params(),
                "error": str(e)
            }


async def stream_attack_prompts(attacks: dict[str, BaseAttack],
                                base_prompts: list[Any], system_prompt: str | None = None) -> AsyncGenerator[dict[str, Any], None]:
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
