"""
Pipeline runner for HiveTraceRed.

Orchestrates the four-stage pipeline: attack-prompt generation, model
response collection, response evaluation, and HTML report generation.
Each stage is individually toggleable via ``config["stages"]``; when a
stage is disabled, the runner falls back to loading that stage's input
from a file path specified in the config.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import yaml

from hivetracered.pipeline import (
    save_pipeline_results,
    setup_attacks,
    stream_attack_prompts,
    stream_evaluated_responses,
    stream_model_responses,
)
from hivetracered.report import (
    build_html_report,
    calculate_metrics,
    create_charts,
    generate_data_tables,
    load_data,
)
from hivetracered.setup import (
    load_base_prompts,
    load_records,
    setup_evaluator,
    setup_model,
)

logger = logging.getLogger(__name__)


async def create_attack_prompts(
    config: dict[str, Any], run_dir: str, output_format: str = "csv"
) -> list[dict[str, Any]]:
    """Stage 1: Create attack prompts using configured attacks."""
    logger.info("STAGE 1: Creating attack prompts...")

    attacker_model = setup_model(config.get("attacker_model", {}))
    if not attacker_model:
        logger.warning("No valid attacker model configured.")
        return []

    base_prompts = load_base_prompts(config)
    if not base_prompts:
        logger.warning("No base prompts found.")
        return []

    logger.info("Loaded %d base prompts", len(base_prompts))

    # Iterative attacks (PAIR/TAP) consume target_model + evaluator during
    # prompt generation, so they must be instantiated here as well as in
    # stage 3. Deduplicating would require threading state across stages.
    response_model = setup_model(config.get("response_model", {}))
    evaluation_model = setup_model(config.get("evaluation_model", {}))
    evaluator = setup_evaluator(config.get("evaluator", {}), evaluation_model)

    attack_configs = config.get("attacks", [])
    attacks = setup_attacks(
        attack_configs,
        attacker_model,
        target_model=response_model,
        evaluator=evaluator,
        evaluation_model=evaluation_model,
        setup_evaluator_fn=setup_evaluator,
    )
    if not attacks:
        logger.warning("No valid attacks configured.")
        return []

    logger.info("Initialized %d attacks: %s", len(attacks), ", ".join(attacks.keys()))

    system_prompt = config.get("system_prompt", None)

    attack_prompts: list[dict[str, Any]] = []
    async for ap in stream_attack_prompts(attacks, base_prompts, system_prompt):
        attack_prompts.append(ap)

    if not attack_prompts:
        logger.warning("No attack prompts generated.")
        return []

    logger.info("Generated %d attack prompts", len(attack_prompts))
    save_pipeline_results(attack_prompts, run_dir, "attack_prompts", format=output_format)
    return attack_prompts


async def get_model_responses(
    config: dict[str, Any],
    attack_prompts: list[dict[str, Any]],
    run_dir: str,
    output_format: str = "csv",
) -> list[dict[str, Any]]:
    """Stage 2: Get model responses for the attack prompts."""
    logger.info("STAGE 2: Getting model responses...")

    response_model = setup_model(config.get("response_model", {}))
    if not response_model:
        logger.warning("No valid response model configured.")
        return []

    model_responses: list[dict[str, Any]] = []
    async for response in stream_model_responses(response_model, attack_prompts, run_dir):
        model_responses.append(response)

    if not model_responses:
        logger.warning("No model responses generated.")
        return []

    save_pipeline_results(model_responses, run_dir, "model_responses", format=output_format)
    return model_responses


async def evaluate_responses(
    config: dict[str, Any],
    model_responses: list[dict[str, Any]],
    run_dir: str,
    output_format: str = "csv",
) -> tuple[list[dict[str, Any]], str | None]:
    """Stage 3: Evaluate model responses."""
    logger.info("STAGE 3: Evaluating responses...")

    evaluation_model = setup_model(config.get("evaluation_model", {}))
    evaluator = setup_evaluator(config.get("evaluator", {}), evaluation_model)

    if not evaluator:
        logger.warning("No valid evaluator configured.")
        return [], None

    evaluation_results: list[dict[str, Any]] = []
    async for result in stream_evaluated_responses(evaluator, model_responses):
        evaluation_results.append(result)

    if not evaluation_results:
        logger.warning("No evaluation results generated.")
        return [], None

    output = save_pipeline_results(
        evaluation_results, run_dir, "evaluations", format=output_format
    )
    evaluation_file = output.get("path")

    success_count = sum(1 for r in evaluation_results if r.get("success", False))
    success_rate = (success_count / len(evaluation_results)) * 100
    logger.info(
        "Evaluation: %d total, %d successful (%.2f%%)",
        len(evaluation_results), success_count, success_rate,
    )

    return evaluation_results, evaluation_file


def generate_report(
    config: dict[str, Any], run_dir: str, evaluation_file: str
) -> str | None:
    """Stage 4: Generate HTML report from evaluation results.

    Exceptions propagate to the top-level CLI handler, which logs them
    uniformly. No local try/except wrapper.
    """
    logger.info("STAGE 4: Generating report...")

    if not os.path.exists(evaluation_file):
        logger.warning("Evaluation file not found: %s", evaluation_file)
        return None

    df = load_data(evaluation_file)
    if df.empty:
        logger.warning("No data loaded from evaluation file.")
        return None

    logger.info("Loaded %d evaluation results for report", len(df))

    metrics = calculate_metrics(df)
    charts = create_charts(df)
    data_tables = generate_data_tables(df)

    report_config = config.get("report", {})
    output_filename = report_config.get("output_filename")
    if not output_filename:
        timestamp = datetime.now().strftime(config.get("timestamp_format", "%Y%m%d_%H%M%S"))
        output_filename = f"report_{timestamp}.html"

    if report_config.get("include_in_run_dir", True):
        report_path = os.path.join(run_dir, output_filename)
    else:
        report_path = os.path.join(config.get("output_dir", "results"), output_filename)

    html = build_html_report(df, metrics, charts, data_tables)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Report generated: %s", report_path)
    logger.info(
        "  Total: %d | Success rate: %.1f%% | Best attack: %s (%.1f%%)",
        metrics["total_tests"],
        metrics["success_rate"],
        metrics["best_attack_name"],
        metrics["best_attack_rate"],
    )
    return report_path


def _preflight_config(
    config: dict[str, Any],
    enable_attacks: bool,
    enable_responses: bool,
    enable_eval: bool,
) -> None:
    """Validate each enabled stage's required models up-front and raise if
    any cannot be constructed. Prevents earlier stages from burning API
    calls before a later stage is guaranteed to fail — typically caused by
    a typo'd top-level key such as ``respons_model`` or ``evaluaton_model``.

    Required resources per stage:
      - Stage 1 (attacks):   ``attacker_model``
      - Stage 2 (responses): ``response_model``
      - Stage 3 (eval):      ``evaluator`` (plus ``evaluation_model`` if the
                             evaluator is a ``ModelEvaluator`` subclass)

    Instances built here are discarded; each stage constructs its own.
    """
    if enable_attacks and setup_model(config.get("attacker_model", {})) is None:
        raise ValueError(
            "Stage 1 (create_attack_prompts) is enabled but 'attacker_model' "
            "could not be initialized. Check the 'attacker_model' block in "
            "your config."
        )

    if enable_responses and setup_model(config.get("response_model", {})) is None:
        raise ValueError(
            "Stage 2 (get_model_responses) is enabled but 'response_model' "
            "could not be initialized. Check the 'response_model' block in "
            "your config."
        )

    if enable_eval:
        evaluation_model = setup_model(config.get("evaluation_model", {}))
        evaluator = setup_evaluator(config.get("evaluator", {}), evaluation_model)
        if evaluator is None:
            raise ValueError(
                "Stage 3 (evaluate_responses) is enabled but the evaluator "
                "could not be initialized. See previous log messages; "
                "typically a missing or misnamed 'evaluator' / "
                "'evaluation_model' config block."
            )


def _dump_config_to_yaml(config: dict[str, Any], config_path: str) -> None:
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False)


async def _prepare_run_dir(config: dict[str, Any]) -> str:
    output_dir = config.get("output_dir", "results")
    timestamp = datetime.now().strftime(config.get("timestamp_format", "%Y%m%d_%H%M%S"))
    run_dir = os.path.join(output_dir, f"run_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    config_path = os.path.join(run_dir, "config.yaml")
    await asyncio.to_thread(_dump_config_to_yaml, config, config_path)
    logger.info("Configuration saved to %s", config_path)
    return run_dir


async def _run_stage_attacks(
    config: dict[str, Any], run_dir: str, output_format: str,
    enable_attacks: bool, enable_responses: bool,
) -> tuple[list[dict[str, Any]], bool]:
    if enable_attacks:
        attack_prompts = await create_attack_prompts(config, run_dir, output_format)
        if not attack_prompts and enable_responses:
            logger.warning("No attack prompts. Skipping model responses.")
            enable_responses = False
        return attack_prompts, enable_responses

    if enable_responses:
        attack_prompts = load_records(config.get("attack_prompts_file"), "attack prompts")
        if not attack_prompts:
            enable_responses = False
        return attack_prompts, enable_responses

    return [], enable_responses


async def _run_stage_responses(
    config: dict[str, Any], attack_prompts: list[dict[str, Any]],
    run_dir: str, output_format: str,
    enable_responses: bool, enable_eval: bool,
) -> tuple[list[dict[str, Any]], bool]:
    if enable_responses:
        model_responses = await get_model_responses(config, attack_prompts, run_dir, output_format)
        if not model_responses and enable_eval:
            logger.warning("No model responses. Skipping evaluation.")
            enable_eval = False
        return model_responses, enable_eval

    if enable_eval:
        model_responses = load_records(config.get("model_responses_file"), "model responses")
        if not model_responses:
            enable_eval = False
        return model_responses, enable_eval

    return [], enable_eval


async def _run_stage_eval(
    config: dict[str, Any], model_responses: list[dict[str, Any]],
    run_dir: str, output_format: str,
    enable_eval: bool, enable_report: bool,
) -> tuple[list[dict[str, Any]], str | None]:
    if enable_eval:
        return await evaluate_responses(config, model_responses, run_dir, output_format)

    if enable_report:
        provided = config.get("evaluation_results_file")
        if provided and os.path.exists(provided):
            logger.info("Using provided evaluation file for report: %s", provided)
            return [], provided

    return [], None


def _log_summary(
    run_dir: str,
    attack_prompts: list[dict[str, Any]],
    model_responses: list[dict[str, Any]],
    evaluation_results: list[dict[str, Any]],
    report_path: str | None,
) -> None:
    logger.info(
        "Pipeline complete: %d attack prompts, %d responses, %d evaluations",
        len(attack_prompts), len(model_responses), len(evaluation_results),
    )
    if evaluation_results:
        success_count = sum(1 for r in evaluation_results if r.get("success", False))
        logger.info("Attack success rate: %.2f%%", (success_count / len(evaluation_results)) * 100)
    logger.info("Results saved to: %s", run_dir)
    if report_path:
        logger.info("Report: %s", report_path)


async def run_pipeline(config: dict[str, Any]) -> None:
    """Run the complete testing pipeline, controlling stages via config."""
    run_dir = await _prepare_run_dir(config)
    output_format = config.get("output_format", "csv")

    stages = config.get("stages", {})
    enable_attacks = stages.get("create_attack_prompts", True)
    enable_responses = stages.get("get_model_responses", True)
    enable_eval = stages.get("evaluate_responses", True)
    enable_report = stages.get("generate_report", True)

    logger.info(
        "Enabled stages: attacks=%s responses=%s eval=%s report=%s",
        enable_attacks, enable_responses, enable_eval, enable_report,
    )

    # Fail fast on config errors (e.g. typo'd model keys) before any stage
    # burns time and API credits.
    _preflight_config(config, enable_attacks, enable_responses, enable_eval)

    attack_prompts, enable_responses = await _run_stage_attacks(
        config, run_dir, output_format, enable_attacks, enable_responses,
    )

    model_responses, enable_eval = await _run_stage_responses(
        config, attack_prompts, run_dir, output_format,
        enable_responses, enable_eval,
    )

    evaluation_results, evaluation_file = await _run_stage_eval(
        config, model_responses, run_dir, output_format,
        enable_eval, enable_report,
    )

    report_path = None
    if enable_report and evaluation_file:
        report_path = generate_report(config, run_dir, evaluation_file)
    elif enable_report:
        logger.info("Skipping report: no evaluation file available.")

    _log_summary(run_dir, attack_prompts, model_responses, evaluation_results, report_path)
