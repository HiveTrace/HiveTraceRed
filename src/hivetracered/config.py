"""
Configuration loading for HiveTraceRed.

The CLI requires an explicit YAML config file. There are no framework-level
defaults — each missing key is handled locally by whatever code consumes it
(e.g. ``config.get("output_dir", "results")`` in the runner), so the config
file is the single source of truth for a run.
"""

import logging
import os
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)

# Top-level keys the runner understands. Used to surface typos via a warning;
# not used as a source of defaults.
_KNOWN_TOP_LEVEL_KEYS = frozenset({
    "stages",
    "attacker_model",
    "response_model",
    "evaluation_model",
    "evaluator",
    "attacks",
    "base_prompts",
    "base_prompts_file",
    "attack_prompts_file",
    "model_responses_file",
    "evaluation_results_file",
    "system_prompt",
    "output_dir",
    "timestamp_format",
    "output_format",
    "report",
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


def load_config(config_path: str) -> dict[str, Any]:
    """Load and return the YAML configuration at ``config_path``.

    The file must exist and parse to a mapping. Unknown keys at the top
    level, under ``stages``, or under ``report`` are surfaced as warnings
    (catches typos like ``evaluat_responses``) but are otherwise preserved.

    Raises:
        FileNotFoundError: the path does not exist.
        ValueError: the file is empty or does not parse to a mapping.
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

    _warn_unknown_keys(config, _KNOWN_TOP_LEVEL_KEYS, "top level")
    _warn_unknown_keys(config.get("stages"), _KNOWN_STAGE_KEYS, "'stages'")
    _warn_unknown_keys(config.get("report"), _KNOWN_REPORT_KEYS, "'report'")

    return config


def _warn_unknown_keys(section: Any, known: frozenset, where: str) -> None:
    if not isinstance(section, dict):
        return
    unknown = set(section) - known
    if unknown:
        logger.warning(
            "Unknown %s config keys (possible typos): %s",
            where, ", ".join(sorted(unknown)),
        )
