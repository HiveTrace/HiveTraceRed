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
from typing import Any

import yaml

from hivetracered.attacks.iterative_attack import IterativeAttack
from hivetracered.pipeline import (
    ATTACK_CLASSES,
    save_pipeline_results,
    setup_attacks,
    stream_attack_prompts,
    stream_evaluated_responses,
    stream_model_responses,
)
from hivetracered.pipeline.create_dataset import _parse_attack_config
from hivetracered.pipeline.model_responses import CONSECUTIVE_FAILURES_DEFAULT
from hivetracered.pipeline.evaluation import RESPONSE_ERROR
from hivetracered.report import (
    build_html_report,
    calculate_metrics,
    create_charts,
    generate_data_tables,
    load_data,
)
from hivetracered.setup import (
    DatasetSpec,
    load_base_prompts,
    load_datasets,
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
    async for response in stream_model_responses(
        response_model, attack_prompts, _consecutive_failures(config)
    ):
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

    When the loaded DataFrame has more than one distinct ``dataset`` value,
    per-dataset metric blocks are rendered and the cross-dataset aggregate is
    suppressed (FR-15).

    Exceptions propagate to the top-level CLI handler. No local try/except.
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

    report_config = config.get("report", {})
    output_filename = report_config.get("output_filename")
    if not output_filename:
        timestamp = datetime.now().strftime(config.get("timestamp_format", "%Y%m%d_%H%M%S"))
        output_filename = f"report_{timestamp}.html"

    if report_config.get("include_in_run_dir", True):
        report_path = os.path.join(run_dir, output_filename)
    else:
        report_path = os.path.join(config.get("output_dir", "results"), output_filename)

    if "dataset" in df.columns and df["dataset"].nunique() > 1:
        for ds_name in df["dataset"].unique():
            logger.info("Dataset '%s': %d records", ds_name, len(df[df["dataset"] == ds_name]))
        html = build_html_report(df, metrics=None, charts=None, data_tables=None)
    else:
        metrics = calculate_metrics(df)
        charts = create_charts(df)
        data_tables = generate_data_tables(df)
        html = build_html_report(df, metrics, charts, data_tables)
        logger.info(
            "  Total: %d | Success rate: %.1f%% | Best attack: %s (%.1f%%)",
            metrics["total_tests"],
            metrics["success_rate"],
            metrics["best_attack_name"],
            metrics["best_attack_rate"],
        )

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Report generated: %s", report_path)
    return report_path


def _preflight_config(
    config: dict[str, Any],
    enable_attacks: bool,
    enable_responses: bool,
    enable_eval: bool,
) -> list[DatasetSpec]:
    """Validate each enabled stage's required models up-front and raise if
    any cannot be constructed. Returns the materialised DatasetSpec list for
    direct reuse by the caller (ADR-0008).
    """
    evaluation_model = setup_model(config.get("evaluation_model", {}))

    specs = load_datasets(config, evaluation_model)

    for spec in specs:
        if len(spec.prompts) == 0:
            entry = next(e for e in config["datasets"] if e["name"] == spec.name)
            source = "base_prompts_file" if "base_prompts_file" in entry else "base_prompts"
            raise ValueError(
                f"Dataset '{spec.name}' has no prompts in '{source}'. "
                "Each dataset must have at least one prompt."
            )

    for attack_cfg in config.get("attacks", []):
        _check_no_iterative_attack(attack_cfg)

    if not enable_attacks and config.get("attack_prompts_file"):
        rows = load_records(config["attack_prompts_file"], "attack prompts")
        file_datasets: set[str] = {str(row["dataset"]) for row in rows if row.get("dataset")}
        spec_names = {spec.name for spec in specs}
        orphans = file_datasets - spec_names
        if orphans:
            raise ValueError(
                f"attack_prompts_file contains records with dataset name(s) not "
                f"found in the config: {', '.join(sorted(orphans))}. "
                "Remove orphan records or add matching dataset entries."
            )

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
        if specs:
            for spec in specs:
                if spec.evaluator is None:
                    raise ValueError(
                        f"Stage 3 (evaluate_responses) is enabled but the evaluator "
                        f"for dataset '{spec.name}' could not be initialized. "
                        "Check the 'evaluator' block for that dataset entry."
                    )
        else:
            evaluator = setup_evaluator(config.get("evaluator", {}), evaluation_model)
            if evaluator is None:
                raise ValueError(
                    "Stage 3 (evaluate_responses) is enabled but the evaluator "
                    "could not be initialized. See previous log messages; "
                    "typically a missing or misnamed 'evaluator' / "
                    "'evaluation_model' config block."
                )

    return specs


def _check_no_iterative_attack(attack_cfg: Any) -> None:
    """Raise ValueError if attack_cfg (or any nested inner_attack) is iterative."""
    attack_name, _params, inner_attack_cfg = _parse_attack_config(attack_cfg)
    if attack_name and attack_name in ATTACK_CLASSES:
        attack_class = ATTACK_CLASSES[attack_name]["attack_class"]
        if issubclass(attack_class, IterativeAttack):
            raise ValueError(
                f"Iterative attack '{attack_name}' is not supported with the "
                "'datasets:' schema (FR-13). Use non-iterative attacks instead."
            )
    if inner_attack_cfg is not None:
        _check_no_iterative_attack(inner_attack_cfg)


async def _evaluate_dataset(
    spec: DatasetSpec, responses: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Run Stage 3 for one dataset.

    Evaluator exceptions are caught and converted to per-record failure dicts
    so one dataset's evaluator failure does not abort the others (AC-10).
    """
    if spec.evaluator is None:
        return []

    evaluation_results: list[dict[str, Any]] = []
    try:
        # Skip failed requests (error field): scoring their empty content would
        # pollute results. Evaluate only the rest, then weave back in order.
        eval_indices = [i for i, r in enumerate(responses) if not r.get("error")]
        eval_inputs = [responses[i] for i in eval_indices]
        prompts = [r.get("base_prompt", "") for r in eval_inputs]

        scored_by_index: dict[int, dict[str, Any]] = {}
        async for batch_result in spec.evaluator.stream_abatch(prompts, eval_inputs):
            orig_idx = eval_indices[len(scored_by_index)]
            scored_by_index[orig_idx] = batch_result

        for i, source in enumerate(responses):
            if i in scored_by_index:
                batch_result = scored_by_index[i]
                evaluation_results.append({
                    **source,
                    "success": batch_result.get("success", False),
                    "evaluation": batch_result,
                    "evaluator": spec.evaluator.__class__.__name__,
                })
            else:
                evaluation_results.append({
                    **source,
                    "success": False,
                    "evaluation": {"success": False, "reason": RESPONSE_ERROR},
                    "evaluator": "",
                })
    except Exception as e:
        logger.error("Stage 3 failed for dataset '%s': %s", spec.name, e, exc_info=True)
        if len(responses) == 0:
            evaluation_results.append({
                "dataset": spec.name,
                "success": False,
                "error": str(e),
                "evaluator": "",
                "evaluation": {"success": False, "reason": "evaluator failure — empty response slice"},
            })
        else:
            for resp in responses:
                evaluation_results.append({
                    **resp,
                    "dataset": spec.name,
                    "success": False,
                    "evaluator": "",
                    "evaluation": {"success": False, "reason": "evaluator failure"},
                    "error": str(e),
                })

    return evaluation_results


async def _run_pipeline_for_datasets(
    config: dict[str, Any],
    dataset_specs: list[DatasetSpec],
    run_dir: str,
    output_format: str,
    enable_attacks: bool,
    enable_responses: bool,
    enable_eval: bool,
) -> tuple[list[dict[str, Any]], str | None]:
    """Run Stages 1-3 across all datasets, one stage at a time.

    Each stage processes the datasets sequentially; the only concurrency is
    each model's own internal request batching. Stage 1 and Stage 2 write one
    file per dataset; Stage 3 results are combined into a single
    ``evaluations`` file. Returns ``(all_evaluation_results,
    evaluation_file_path)``. Stage-1/2 exceptions abort the run; Stage-3
    exceptions are isolated per-dataset and converted to failure records.
    """
    system_prompt = config.get("system_prompt")

    # Stage 1: attack prompts — one file per dataset.
    attacks_by_dataset: dict[str, list[dict[str, Any]]] = {}
    if enable_attacks:
        attacker_model = setup_model(config.get("attacker_model", {}))
        response_model_for_attacks = setup_model(config.get("response_model", {}))
        evaluation_model = setup_model(config.get("evaluation_model", {}))
        for spec in dataset_specs:
            # Attacks are re-built per dataset so that each dataset's own
            # evaluator (spec.evaluator) flows into attack-internal judge
            # slots — e.g. CrescendoAttack.success_judge uses the per-dataset
            # WildGuardGPTEvaluator instead of a generic ScoringJudgeEvaluator.
            attacks = setup_attacks(
                config.get("attacks", []),
                attacker_model,
                target_model=response_model_for_attacks,
                evaluator=spec.evaluator,
                evaluation_model=evaluation_model,
                setup_evaluator_fn=setup_evaluator,
            )
            records: list[dict[str, Any]] = []
            async for record in stream_attack_prompts(attacks, spec.prompts, system_prompt):
                record["dataset"] = spec.name
                records.append(record)
            save_pipeline_results(
                records, run_dir, f"attack_prompts_{spec.name}", format=output_format
            )
            attacks_by_dataset[spec.name] = records
    elif enable_responses:
        all_attacks = load_records(config.get("attack_prompts_file"), "attack prompts")
        for spec in dataset_specs:
            attacks_by_dataset[spec.name] = [
                r for r in all_attacks if r.get("dataset") == spec.name
            ]

    # Stage 2: model responses — one file per dataset, shared response model.
    responses_by_dataset: dict[str, list[dict[str, Any]]] = {}
    if enable_responses:
        response_model = setup_model(config.get("response_model", {}))
        for spec in dataset_specs:
            records = []
            if response_model is not None:
                async for record in stream_model_responses(
                    response_model, attacks_by_dataset.get(spec.name, []),
                    _consecutive_failures(config),
                ):
                    records.append(record)
            save_pipeline_results(
                records, run_dir, f"model_responses_{spec.name}", format=output_format
            )
            responses_by_dataset[spec.name] = records
    elif enable_eval:
        all_responses = load_records(config.get("model_responses_file"), "model responses")
        for spec in dataset_specs:
            responses_by_dataset[spec.name] = [
                r for r in all_responses if r.get("dataset") == spec.name
            ]

    # Stage 3: evaluation — combined into a single file.
    all_eval_results: list[dict[str, Any]] = []
    if enable_eval:
        for spec in dataset_specs:
            all_eval_results.extend(
                await _evaluate_dataset(spec, responses_by_dataset.get(spec.name, []))
            )

    evaluation_file: str | None = None
    if enable_eval and all_eval_results:
        output = save_pipeline_results(
            all_eval_results, run_dir, "evaluations", format=output_format
        )
        evaluation_file = output.get("path")

    return all_eval_results, evaluation_file


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


def _consecutive_failures(config: dict[str, Any]) -> int:
    """Circuit-breaker threshold from config (error_handling.consecutive_failures)."""
    return config.get("error_handling", {}).get(
        "consecutive_failures", CONSECUTIVE_FAILURES_DEFAULT
    )


def _max_failure_rate(config: dict[str, Any]) -> float:
    """Failure fraction above which a run is reported as degraded (nonzero exit)."""
    return config.get("error_handling", {}).get("max_failure_rate", 0.5)


def _error_rate(records: list[dict[str, Any]]) -> float:
    """Fraction of records whose request failed (non-empty 'error' field)."""
    if not records:
        return 0.0
    failed = sum(1 for r in records if r.get("error"))
    return failed / len(records)


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


async def run_pipeline(config: dict[str, Any]) -> bool:
    """Run the complete testing pipeline, controlling stages via config.

    Returns True if the run is degraded (request failure rate above
    error_handling.max_failure_rate), so the CLI can exit non-zero.
    """
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
    dataset_specs = _preflight_config(config, enable_attacks, enable_responses, enable_eval)

    if "datasets" in config:
        evaluation_results, evaluation_file = await _run_pipeline_for_datasets(
            config, dataset_specs, run_dir, output_format,
            enable_attacks, enable_responses, enable_eval,
        )
        attack_prompts: list[dict[str, Any]] = []
        model_responses: list[dict[str, Any]] = []
    else:
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

    # Evaluation records carry the request 'error' field through; fall back to raw
    # responses when evaluation was disabled.
    rate = _error_rate(evaluation_results or model_responses)
    degraded = rate > _max_failure_rate(config)
    if degraded:
        logger.warning("Degraded run: %.0f%% of requests failed", rate * 100)
    return degraded
