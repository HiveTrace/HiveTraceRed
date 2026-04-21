"""
Model, evaluator, and prompt setup utilities for HiveTraceRed.

Provides factory helpers that translate configuration dicts into
initialized model/evaluator instances, plus file loaders for base prompts
and intermediate pipeline records.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from hivetracered.evaluators import BaseEvaluator, ModelEvaluator
from hivetracered.models import Model
from hivetracered.pipeline.constants import EVALUATOR_CLASSES, MODEL_CLASSES

logger = logging.getLogger(__name__)

_PROMPT_COLUMN_NAMES = (
    "Prompt", "Text", "Question", "Query", "Input",
    "Input_text", "Input_query", "Input_question",
    "prompt", "text", "question", "query", "input",
    "input_text", "input_query", "input_question",
)


def setup_model(model_config: Dict[str, Any]) -> Optional[Model]:
    """Set up a model based on configuration dict.

    Resolution order:
      1. ``model_config["name"]`` matches a key in ``MODEL_CLASSES``.
      2. ``model_config["model"]`` (explicit class override) matches a key
         in ``MODEL_CLASSES``.

    Returns ``None`` and logs a warning on unknown names or init failures.
    """
    model_name = model_config.get("name")
    if not model_name:
        return None

    model_class_name = model_config.get("model", None)
    params = model_config.get("params", {})

    if model_name in MODEL_CLASSES:
        try:
            model_class = MODEL_CLASSES[model_name]
            return model_class(model=model_name, **params)
        except Exception as e:
            logger.error("Error initializing model '%s': %s", model_name, e)
    elif model_class_name in MODEL_CLASSES:
        try:
            model_class = MODEL_CLASSES[model_class_name]
            return model_class(model=model_name, **params)
        except Exception as e:
            logger.error("Error initializing model '%s': %s", model_class_name, e)
    else:
        logger.warning("Unknown model '%s'.", model_name)

    return None


def setup_evaluator(
    evaluator_config: Dict[str, Any], model: Optional[Model] = None
) -> Optional[BaseEvaluator]:
    """Set up an evaluator based on configuration dict.

    ModelEvaluator subclasses receive ``model``; other evaluators are
    constructed with just their params.
    """
    evaluator_name = evaluator_config.get("name")
    if not evaluator_name:
        return None

    params = evaluator_config.get("params", {})

    if evaluator_name not in EVALUATOR_CLASSES:
        logger.warning("Unknown evaluator '%s'.", evaluator_name)
        return None

    evaluator_class = EVALUATOR_CLASSES[evaluator_name]
    if issubclass(evaluator_class, ModelEvaluator) and model is None:
        logger.error(
            "Evaluator '%s' requires a model, but 'evaluation_model' is missing "
            "or failed to initialize. Check the 'evaluation_model' block in your "
            "config.",
            evaluator_name,
        )
        return None

    try:
        if issubclass(evaluator_class, ModelEvaluator):
            return evaluator_class(model=model, **params)
        return evaluator_class(**params)
    except Exception as e:
        logger.error("Error initializing evaluator '%s': %s", evaluator_name, e)
        return None


def _read_tabular(file_path: str) -> pd.DataFrame:
    """Read a .csv/.json/.parquet/.xlsx/.xls file into a DataFrame."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".json":
        return pd.read_json(file_path)
    if ext == ".csv":
        return pd.read_csv(file_path)
    if ext == ".parquet":
        return pd.read_parquet(file_path)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path)
    raise ValueError(f"Unsupported file extension: {ext}")


def load_base_prompts(config: Dict[str, Any]) -> List[Union[str, Dict[str, Any]]]:
    """Load base prompts from ``base_prompts_file`` or fall back to
    ``base_prompts`` in the config.

    Returns a list of strings (for ``.txt`` files) or a list of row-dicts
    with all original columns preserved plus a ``prompt`` field.

    Raises:
        FileNotFoundError: ``base_prompts_file`` is set but missing.
        ValueError: no recognized prompt column in a tabular file.
    """
    file_path = config.get("base_prompts_file")
    if not file_path:
        return config.get("base_prompts", [])

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"base_prompts_file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines()]

    df = _read_tabular(file_path)
    for col in _PROMPT_COLUMN_NAMES:
        if col in df.columns:
            records = df.to_dict("records")
            for record in records:
                if "prompt" not in record:
                    record["prompt"] = record[col]
            return records

    raise ValueError(
        f"No valid prompt column found in '{file_path}'. "
        f"Available columns: {df.columns.tolist()}"
    )


def load_records(file_path: str, label: str = "records") -> List[Dict[str, Any]]:
    """Load intermediate pipeline records from a file.

    Replaces the previous ``load_attack_prompts`` / ``load_model_responses``
    helpers, which differed only in their log strings.

    Args:
        file_path: Path to a ``.json``, ``.csv``, ``.parquet`` or
            ``.xlsx/.xls`` file.
        label: Human-readable label used in log messages (e.g.
            ``"attack prompts"``).
    """
    if not file_path or not os.path.exists(file_path):
        logger.warning("%s file '%s' not found.", label.capitalize(), file_path)
        return []

    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError(
                    f"JSON file must contain a list of records, "
                    f"got {type(data).__name__}."
                )
            records = data
        else:
            records = _read_tabular(file_path).to_dict("records")

        logger.info("Loaded %d %s from %s", len(records), label, file_path)
        return records
    except Exception as e:
        logger.error("Failed to load %s from %s: %s", label, file_path, e)
        return []
