"""Tests for hivetracered.setup factory + loader helpers.

Spec sources:
- setup_model docstring (src/hivetracered/setup.py:30-39):
    1. config["name"] in MODEL_CLASSES → instantiate that class
    2. else config["model"] in MODEL_CLASSES → instantiate that class
    3. else / on init failure → return None and log warning
- setup_evaluator docstring (src/hivetracered/setup.py:65-72):
    "ModelEvaluator subclasses receive `model`; other evaluators are
    constructed with just their params."
- load_base_prompts docstring (src/hivetracered/setup.py:116-126):
    Falls back to config["base_prompts"] when no file; raises FileNotFoundError
    when base_prompts_file missing; raises ValueError when no recognized column.
- load_records (src/hivetracered/setup.py:154-188):
    "If file_path missing → warn and return []"; JSON must contain a list,
    else ValueError; tabular files → DataFrame.to_dict('records'); on parse
    failure logs error and returns [].
"""

from __future__ import annotations

import json
import logging

import pytest

from hivetracered.evaluators import KeywordEvaluator, ModelEvaluator
from hivetracered.registry import Registry
from hivetracered.setup import (
    load_base_prompts,
    load_records,
    setup_evaluator,
    setup_model,
)


SETUP_LOGGER = "hivetracered.setup"


# ── setup_model ──────────────────────────────────────────────────────


def test_setup_model_missing_name_returns_none():
    result = setup_model({})  # no "name" key

    assert result is None  # spec: only acts when name present


def test_setup_model_unknown_name_returns_none_and_warns(caplog):
    caplog.set_level(logging.WARNING, logger=SETUP_LOGGER)

    result = setup_model({"name": "definitely-not-a-model"})

    assert result is None
    warns = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("definitely-not-a-model" in m for m in warns)


def test_setup_model_known_name_instantiates_registered_class(monkeypatch):
    """When config['name'] is a registered class, that class is constructed."""
    captured = {}

    class FakeModel:
        def __init__(self, model, **params):
            captured["model"] = model
            captured["params"] = params

    # MODEL_CLASSES is a live view over Registry — register, then check.
    Registry._models["FakeModelXYZ"] = FakeModel
    try:
        result = setup_model({"name": "FakeModelXYZ", "params": {"temperature": 0.1}})
    finally:
        Registry._models.pop("FakeModelXYZ", None)

    assert isinstance(result, FakeModel)
    assert captured["model"] == "FakeModelXYZ"  # = forwarded as `model=` kwarg
    assert captured["params"] == {"temperature": 0.1}


def test_setup_model_falls_back_to_model_field_when_name_unknown():
    """If `name` isn't a registered class but `model` is, use `model` class."""

    class FakeModel:
        def __init__(self, model, **params):
            self.model_arg = model

    Registry._models["FakeFallback"] = FakeModel
    try:
        result = setup_model({"name": "custom-display-name", "model": "FakeFallback"})
    finally:
        Registry._models.pop("FakeFallback", None)

    assert isinstance(result, FakeModel)
    assert result.model_arg == "custom-display-name"  # = forwarded display name


def test_setup_model_init_exception_returns_none_and_logs_error(caplog):
    caplog.set_level(logging.ERROR, logger=SETUP_LOGGER)

    class ExplodingModel:
        def __init__(self, model, **params):
            raise RuntimeError("boom")

    Registry._models["ExplodingXYZ"] = ExplodingModel
    try:
        result = setup_model({"name": "ExplodingXYZ"})
    finally:
        Registry._models.pop("ExplodingXYZ", None)

    assert result is None
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("ExplodingXYZ" in m and "boom" in m for m in errors)


# ── setup_evaluator ──────────────────────────────────────────────────


def test_setup_evaluator_missing_name_returns_none():
    assert setup_evaluator({}) is None


def test_setup_evaluator_unknown_name_returns_none_and_warns(caplog):
    caplog.set_level(logging.WARNING, logger=SETUP_LOGGER)

    result = setup_evaluator({"name": "no-such-evaluator"})

    assert result is None
    warns = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("no-such-evaluator" in m for m in warns)


def test_setup_evaluator_model_evaluator_without_model_returns_none(caplog):
    caplog.set_level(logging.ERROR, logger=SETUP_LOGGER)

    # ModelEvaluator subclasses (e.g. WildGuardGPTEvaluator) require a model.
    result = setup_evaluator({"name": "WildGuardGPTEvaluator"}, model=None)

    assert result is None
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("requires a model" in m for m in errors)


def test_setup_evaluator_non_model_evaluator_instantiated_with_params():
    # KeywordEvaluator does NOT require a model and accepts `keywords` kwarg.
    keywords = ["alpha", "beta"]

    result = setup_evaluator(
        {"name": "KeywordEvaluator", "params": {"keywords": keywords}}
    )

    assert isinstance(result, KeywordEvaluator)
    # Public surface only: the keywords passed in must reach the instance.
    assert result.keywords == keywords  # = the list we passed


def test_setup_evaluator_model_evaluator_instantiated_with_model_and_params(mock_model):
    # WildGuardGPTEvaluator subclasses ModelEvaluator and supplies its own
    # internal evaluation_prompt_template, so just `model` is enough.
    result = setup_evaluator({"name": "WildGuardGPTEvaluator"}, model=mock_model)

    assert isinstance(result, ModelEvaluator)
    assert result.model is mock_model  # = forwarded mock_model fixture


def test_setup_evaluator_init_exception_returns_none_and_logs(caplog, monkeypatch):
    caplog.set_level(logging.ERROR, logger=SETUP_LOGGER)

    class ExplodingEvaluator:
        def __init__(self, **params):
            raise RuntimeError("init failed")

    Registry._evaluators["ExplodingEval"] = ExplodingEvaluator
    try:
        result = setup_evaluator({"name": "ExplodingEval"})
    finally:
        Registry._evaluators.pop("ExplodingEval", None)

    assert result is None
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("ExplodingEval" in m and "init failed" in m for m in errors)


# ── load_base_prompts ────────────────────────────────────────────────


def test_load_base_prompts_no_file_returns_inline_list():
    inline = ["one", "two", "three"]

    result = load_base_prompts({"base_prompts": inline})

    assert result == inline  # = the inline list, untouched


def test_load_base_prompts_no_file_no_inline_returns_empty_default():
    assert load_base_prompts({}) == []  # = default for missing key


def test_load_base_prompts_file_missing_raises_file_not_found(tmp_path):
    missing = tmp_path / "nope.txt"

    with pytest.raises(FileNotFoundError, match=r"base_prompts_file not found"):
        load_base_prompts({"base_prompts_file": str(missing)})


def test_load_base_prompts_txt_returns_one_prompt_per_line(tmp_path):
    txt = tmp_path / "prompts.txt"
    txt.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    result = load_base_prompts({"base_prompts_file": str(txt)})

    assert result == ["alpha", "beta", "gamma"]  # = three lines, stripped


@pytest.mark.parametrize(
    "column_name",
    ["Prompt", "prompt"],
    ids=["capital-Prompt", "lowercase-prompt"],
)
def test_load_base_prompts_csv_column_recognised_returns_records(tmp_path, column_name):
    csv = tmp_path / "prompts.csv"
    # One column with one of the recognized names + an extra column to verify
    # the entire row dict is preserved with `prompt` injected.
    csv.write_text(f"{column_name},category\nhello,greet\n", encoding="utf-8")

    result = load_base_prompts({"base_prompts_file": str(csv)})

    assert len(result) == 1  # = one data row in the CSV
    row = result[0]
    assert row["prompt"] == "hello"  # = injected key from the recognised column
    assert row["category"] == "greet"  # = original column preserved


def test_load_base_prompts_csv_no_recognised_column_raises_value_error(tmp_path):
    csv = tmp_path / "bad.csv"
    csv.write_text("foo,bar\n1,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"No valid prompt column"):
        load_base_prompts({"base_prompts_file": str(csv)})


# ── load_records ─────────────────────────────────────────────────────


def test_load_records_unreadable_path_returns_empty_and_warns(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger=SETUP_LOGGER)
    missing_path = str(tmp_path / "nope.json")  # nonexistent → os.path.exists False

    result = load_records(missing_path, label="attack prompts")

    assert result == []
    warns = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Attack prompts" in m and "not found" in m for m in warns)


def test_load_records_valid_json_list_returns_records(tmp_path):
    expected = [{"prompt": "p1", "response": "r1"}, {"prompt": "p2", "response": "r2"}]
    f = tmp_path / "records.json"
    f.write_text(json.dumps(expected), encoding="utf-8")

    result = load_records(str(f))

    assert result == expected  # = exact list written


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        # JSON dict at top → ValueError raised → caught → [] + log
        ("records.json", json.dumps({"not": "a list"})),
        # malformed JSON → JSONDecodeError raised → caught → [] + log
        ("broken.json", "{ not json"),
    ],
    ids=["json-not-a-list", "json-corrupt"],
)
def test_load_records_parse_failure_returns_empty_and_logs_error(
    tmp_path, caplog, filename, content
):
    caplog.set_level(logging.ERROR, logger=SETUP_LOGGER)
    f = tmp_path / filename
    f.write_text(content, encoding="utf-8")

    result = load_records(str(f))

    # Outer try/except catches the parse error and returns []; error logged.
    assert result == []
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("Failed to load" in m for m in errors)


def test_load_records_csv_returns_row_dicts(tmp_path):
    f = tmp_path / "records.csv"
    f.write_text("prompt,score\nhello,1\nworld,2\n", encoding="utf-8")

    result = load_records(str(f))

    assert len(result) == 2  # = two CSV data rows
    assert result[0]["prompt"] == "hello"
    assert result[1]["prompt"] == "world"
    # pandas may parse score as int — assert numeric value via int() coercion
    # rather than a literal type to keep the test robust to pandas version drift.
    assert int(result[0]["score"]) == 1
    assert int(result[1]["score"]) == 2
