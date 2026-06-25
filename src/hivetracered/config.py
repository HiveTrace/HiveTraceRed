"""
Configuration loading for HiveTraceRed.

The CLI requires an explicit YAML config file. There are no framework-level
defaults — each missing key is handled locally by whatever code consumes it
(e.g. ``config.get("output_dir", "results")`` in the runner), so the config
file is the single source of truth for a run.
"""

import logging
import os
import re
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Top-level keys the runner understands. Used to surface typos via a warning;
# not used as a source of defaults.
_KNOWN_TOP_LEVEL_KEYS = frozenset({
    "stages",
    "attacker_model",
    "response_model",
    "evaluation_model",
    "attacks",
    "attack_prompts_file",
    "model_responses_file",
    "evaluation_results_file",
    "system_prompt",
    "output_dir",
    "timestamp_format",
    "output_format",
    "report",
    "datasets",
    "error_handling",
})

_KNOWN_STAGE_KEYS = frozenset({
    "create_attack_prompts",
    "get_model_responses",
    "evaluate_responses",
    "generate_report",
})

_KNOWN_REPORT_KEYS = frozenset({
    "output_filename",
    "include_in_run_dir",
})

_KNOWN_DATASET_ENTRY_KEYS = frozenset({
    "name",
    "base_prompts",
    "base_prompts_file",
    "evaluator",
})


def load_config(config_path: str) -> dict[str, Any]:
    """Load and return the YAML configuration at ``config_path``.

    The file must exist and parse to a mapping. Unknown keys at the top
    level, under ``stages``, or under ``report`` are surfaced as warnings
    (catches typos like ``evaluat_responses``) but are otherwise preserved.

    Raises:
        FileNotFoundError: the path does not exist.
        ValueError: the file is empty, not a mapping, or fails dataset block validation.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config is None:
        raise ValueError(f"Config file '{config_path}' is empty.")
    if not isinstance(config, dict):
        raise ValueError(
            f"Config file '{config_path}' must be a mapping, "
            f"got {type(config).__name__}."
        )

    _validate_datasets_block(config)
    _warn_unknown_keys(config, _KNOWN_TOP_LEVEL_KEYS, "top level")
    _warn_unknown_keys(config.get("stages"), _KNOWN_STAGE_KEYS, "'stages'")
    _warn_unknown_keys(config.get("report"), _KNOWN_REPORT_KEYS, "'report'")

    return config


def _validate_datasets_block(config: dict) -> None:
    """Validate the datasets block in the config dict.

    Raises ValueError for legacy keys, missing/invalid datasets (when datasets:
    is present or a legacy key is present), duplicate names, invalid name
    characters, missing evaluator keys, or non-dict evaluator values.
    """
    legacy_present = [k for k in ("evaluator", "base_prompts", "base_prompts_file") if k in config]
    if legacy_present:
        raise ValueError(
            f"Config contains legacy top-level key(s): {', '.join(legacy_present)}. "
            "These keys have been removed. Migrate to the 'datasets:' schema: "
            "add a 'datasets:' list where each entry has 'name', a prompt source "
            "('base_prompts' or 'base_prompts_file'), and an 'evaluator' block."
        )

    # If no datasets key and no legacy keys, this is a bare config; skip further
    # validation so that existing configs without datasets: continue to load.
    if "datasets" not in config:
        return

    datasets = config.get("datasets")
    if not datasets or not isinstance(datasets, list):
        raise ValueError(
            "'datasets' key is missing or empty. "
            "Add a 'datasets:' list with at least one entry."
        )

    seen_names: set[str] = set()
    for entry in datasets:
        if not isinstance(entry, dict):
            raise ValueError(f"Each dataset entry must be a mapping, got: {type(entry).__name__}")

        name_val = entry.get("name")
        if name_val is None or not isinstance(name_val, str) or not name_val.strip():
            raise ValueError(
                f"Dataset entry has an invalid 'name': {name_val!r}. "
                "The name must be a non-empty string matching ^[A-Za-z0-9_-]+$."
            )
        name = name_val.strip()

        if "base_prompts_file" not in entry and "base_prompts" not in entry:
            raise ValueError(
                f"Dataset entry '{name}' must have either 'base_prompts' or 'base_prompts_file'."
            )

        if "evaluator" not in entry:
            raise ValueError(
                f"Dataset entry '{name}' is missing the 'evaluator' key. "
                "Each dataset entry must declare its own evaluator block with the shape: "
                "evaluator: {{name: ClassName, params: {{...}}}}."
            )

        if name in seen_names:
            raise ValueError(
                f"Duplicate dataset name '{name}'. Each dataset entry must have a unique name."
            )
        seen_names.add(name)

        if not re.fullmatch(r'^[A-Za-z0-9_-]+$', name):
            raise ValueError(
                f"Dataset name '{name}' contains invalid characters. "
                "Names must match ^[A-Za-z0-9_-]+$."
            )

        evaluator_val = entry.get("evaluator")
        if evaluator_val is not None and not isinstance(evaluator_val, dict):
            raise ValueError(
                f"Dataset entry '{name}': 'evaluator' must be a dict, "
                f"got {type(evaluator_val).__name__}."
            )

        # Warn on unknown keys in the dataset entry (AC-05).
        _warn_unknown_keys(entry, _KNOWN_DATASET_ENTRY_KEYS, f"dataset entry '{name}'")


def _warn_unknown_keys(section: Any, known: frozenset, where: str) -> None:
    """Log a warning if ``section`` contains keys not in ``known``."""
    if not isinstance(section, dict):
        return
    unknown = set(section) - known
    if unknown:
        logger.warning(
            "Unknown %s config keys (possible typos): %s",
            where, ", ".join(sorted(unknown)),
        )
