"""Unit tests for the runner module orchestration helpers.

Covers _preflight_config validation, _dump_config_to_yaml round-trip,
_log_summary log output, _prepare_run_dir filesystem layout, and
generate_report's missing-file and happy paths.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, List, Tuple
from unittest.mock import MagicMock

import pandas as pd
import pytest
import yaml

from hivetracered import runner
from hivetracered.runner import (
    _dump_config_to_yaml,
    _log_summary,
    _prepare_run_dir,
    _preflight_config,
    _run_stage_attacks,
    _run_stage_eval,
    _run_stage_responses,
    create_attack_prompts,
    evaluate_responses,
    generate_report,
    get_model_responses,
    run_pipeline,
)


def _run(coro):
    """Run an async coroutine to completion in a fresh event loop.

    Uses ``asyncio.new_event_loop`` rather than ``asyncio.run`` because the
    latter closes the policy default loop, which interferes with the
    project-wide ``async_collect`` helper in ``tests/conftest.py``.
    """
    return asyncio.new_event_loop().run_until_complete(coro)


async def _aiter(items):
    """Convert an iterable into an async generator."""
    for item in items:
        yield item


# ── _preflight_config ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("enable_attacks", "enable_responses", "enable_eval", "match"),
    [
        (True, False, False, r"Stage 1"),
        (False, True, False, r"Stage 2"),
    ],
    ids=["stage1-missing-attacker", "stage2-missing-response"],
)
def test_preflight_config_missing_model_raises(enable_attacks, enable_responses, enable_eval, match):
    with pytest.raises(ValueError, match=match):
        _preflight_config({}, enable_attacks, enable_responses, enable_eval)


def test_preflight_config_passes_when_all_required_models_present(monkeypatch):
    fake_model = MagicMock()
    fake_evaluator = MagicMock()
    monkeypatch.setattr(runner, "setup_model", lambda cfg: fake_model)
    monkeypatch.setattr(runner, "setup_evaluator", lambda cfg, m: fake_evaluator)
    config = {
        "attacker_model": {"name": "X"},
        "response_model": {"name": "Y"},
        "evaluator": {"name": "Z"},
    }

    # Should not raise
    _preflight_config(config, True, True, True)


def test_preflight_config_stage3_evaluator_init_failure_raises(monkeypatch):
    monkeypatch.setattr(runner, "setup_model", lambda cfg: MagicMock())
    monkeypatch.setattr(runner, "setup_evaluator", lambda cfg, m: None)

    with pytest.raises(ValueError, match=r"Stage 3"):
        _preflight_config({}, False, False, True)


def test_preflight_config_eval_disabled_skips_evaluator_check(monkeypatch):
    """When enable_eval=False the evaluator block at line 247 is skipped
    entirely; even setup_evaluator returning None must not raise.
    """
    monkeypatch.setattr(runner, "setup_model", lambda cfg: MagicMock())
    setup_evaluator_calls: list = []
    monkeypatch.setattr(
        runner, "setup_evaluator",
        lambda cfg, m: setup_evaluator_calls.append((cfg, m)) or None,
    )

    # Should NOT raise (eval disabled), and setup_evaluator must not be called
    _preflight_config({}, True, True, False)

    assert setup_evaluator_calls == []


# ── _dump_config_to_yaml ────────────────────────────────────────────


def test_dump_config_to_yaml_round_trips_dict(tmp_path):
    cfg = {
        "output_dir": "results",
        "attacker_model": {"name": "X", "params": {"temperature": 0.5}},
        "attacks": ["A1", "A2"],
        "stages": {"create_attack_prompts": True, "generate_report": False},
    }
    path = tmp_path / "config.yaml"

    _dump_config_to_yaml(cfg, str(path))

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert loaded == cfg


# ── _log_summary ────────────────────────────────────────────────────


def test_log_summary_logs_pipeline_complete_with_counts(caplog):
    caplog.set_level(logging.INFO, logger="hivetracered.runner")
    attack_prompts = [{}, {}, {}]  # 3
    model_responses = [{}, {}]      # 2
    evaluation_results = [{"success": True}, {"success": False}]  # 2

    _log_summary("/tmp/run", attack_prompts, model_responses, evaluation_results, None)

    messages = [rec.getMessage() for rec in caplog.records]
    assert any("3 attack prompts" in m and "2 responses" in m and "2 evaluations" in m for m in messages)


@pytest.mark.parametrize(
    ("eval_results", "report_path", "expected_fragment"),
    [
        ([{"success": True}, {"success": True}, {"success": False}, {"success": False}], None, "50.00%"),
        ([], "/tmp/run/report.html", "/tmp/run/report.html"),
    ],
    ids=["success-rate", "report-path"],
)
def test_log_summary_logs_conditional_fields(caplog, eval_results, report_path, expected_fragment):
    caplog.set_level(logging.INFO, logger="hivetracered.runner")

    _log_summary("/tmp/run", [], [], eval_results, report_path)

    messages = [rec.getMessage() for rec in caplog.records]
    assert any(expected_fragment in m for m in messages)


# ── _prepare_run_dir ────────────────────────────────────────────────


def test_prepare_run_dir_creates_run_dir_and_writes_config_yaml(tmp_path):
    config = {"output_dir": str(tmp_path), "attacker_model": {"name": "X"}}

    run_dir = asyncio.get_event_loop().run_until_complete(_prepare_run_dir(config))

    assert os.path.isdir(run_dir)
    assert run_dir.startswith(str(tmp_path) + os.sep + "run_")
    config_yaml = Path(run_dir) / "config.yaml"
    assert config_yaml.exists()
    loaded = yaml.safe_load(config_yaml.read_text(encoding="utf-8"))
    assert loaded == config


def test_prepare_run_dir_uses_default_output_dir_when_missing(tmp_path, monkeypatch):
    # Default is "results"; cd into tmp_path so we don't pollute the cwd.
    monkeypatch.chdir(tmp_path)

    run_dir = asyncio.get_event_loop().run_until_complete(_prepare_run_dir({}))

    assert run_dir.startswith("results" + os.sep + "run_")
    assert os.path.isdir(run_dir)


# ── generate_report ─────────────────────────────────────────────────


def test_generate_report_missing_file_returns_none_and_warns(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="hivetracered.runner")
    missing = str(tmp_path / "does_not_exist.csv")

    result = generate_report({}, str(tmp_path), missing)

    assert result is None
    assert any("not found" in r.getMessage() for r in caplog.records)


def test_generate_report_empty_dataframe_returns_none(tmp_path, monkeypatch):
    eval_file = tmp_path / "eval.csv"
    eval_file.write_text("", encoding="utf-8")  # exists, but load_data returns empty df
    monkeypatch.setattr(runner, "load_data", lambda p: pd.DataFrame())

    result = generate_report({}, str(tmp_path), str(eval_file))

    assert result is None


def test_generate_report_writes_html_and_returns_path(tmp_path, monkeypatch):
    eval_file = tmp_path / "eval.csv"
    eval_file.write_text("col\nval\n", encoding="utf-8")
    fake_df = pd.DataFrame({"a": [1]})
    fake_metrics = {
        "total_tests": 1,
        "success_rate": 100.0,
        "best_attack_name": "BA",
        "best_attack_rate": 100.0,
    }
    monkeypatch.setattr(runner, "load_data", lambda p: fake_df)
    monkeypatch.setattr(runner, "calculate_metrics", lambda df: fake_metrics)
    monkeypatch.setattr(runner, "create_charts", lambda df: {"chart": "<div/>"})
    monkeypatch.setattr(runner, "generate_data_tables", lambda df: {"table": "<table/>"})
    monkeypatch.setattr(runner, "build_html_report", lambda df, m, c, t: "<html>x</html>")

    config = {"output_dir": str(tmp_path), "report": {"output_filename": "out.html"}}
    result = generate_report(config, str(tmp_path), str(eval_file))

    assert result == str(tmp_path / "out.html")
    assert (tmp_path / "out.html").read_text(encoding="utf-8") == "<html>x</html>"


def test_generate_report_uses_output_dir_when_include_in_run_dir_false(tmp_path, monkeypatch):
    eval_file = tmp_path / "eval.csv"
    eval_file.write_text("x", encoding="utf-8")
    out_dir = tmp_path / "outdir"
    out_dir.mkdir()
    run_dir = tmp_path / "rundir"
    run_dir.mkdir()
    monkeypatch.setattr(runner, "load_data", lambda p: pd.DataFrame({"a": [1]}))
    monkeypatch.setattr(runner, "calculate_metrics", lambda df: {
        "total_tests": 1, "success_rate": 0.0, "best_attack_name": "B", "best_attack_rate": 0.0,
    })
    monkeypatch.setattr(runner, "create_charts", lambda df: {})
    monkeypatch.setattr(runner, "generate_data_tables", lambda df: {})
    monkeypatch.setattr(runner, "build_html_report", lambda *a, **k: "<html/>")

    cfg = {
        "output_dir": str(out_dir),
        "report": {"output_filename": "r.html", "include_in_run_dir": False},
    }
    result = generate_report(cfg, str(run_dir), str(eval_file))

    assert result == str(out_dir / "r.html")
    assert (out_dir / "r.html").exists()


def test_generate_report_uses_timestamp_default_filename_when_missing(tmp_path, monkeypatch):
    eval_file = tmp_path / "eval.csv"
    eval_file.write_text("x", encoding="utf-8")
    monkeypatch.setattr(runner, "load_data", lambda p: pd.DataFrame({"a": [1]}))
    monkeypatch.setattr(runner, "calculate_metrics", lambda df: {
        "total_tests": 1, "success_rate": 0.0, "best_attack_name": "B", "best_attack_rate": 0.0,
    })
    monkeypatch.setattr(runner, "create_charts", lambda df: {})
    monkeypatch.setattr(runner, "generate_data_tables", lambda df: {})
    monkeypatch.setattr(runner, "build_html_report", lambda *a, **k: "<html/>")

    # No "report.output_filename" in config triggers the timestamp branch.
    result = generate_report({}, str(tmp_path), str(eval_file))

    assert result is not None
    assert os.path.basename(result).startswith("report_")
    assert result.endswith(".html")
    assert os.path.exists(result)


# ── create_attack_prompts ───────────────────────────────────────────


def test_create_attack_prompts_no_attacker_model_returns_empty(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="hivetracered.runner")
    monkeypatch.setattr(runner, "setup_model", lambda cfg: None)

    result = _run(create_attack_prompts({}, str(tmp_path)))

    assert result == []
    assert any("attacker model" in r.getMessage().lower() for r in caplog.records)


def test_create_attack_prompts_no_base_prompts_returns_empty(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="hivetracered.runner")
    monkeypatch.setattr(runner, "setup_model", lambda cfg: MagicMock())
    monkeypatch.setattr(runner, "load_base_prompts", lambda cfg: [])

    result = _run(create_attack_prompts({}, str(tmp_path)))

    assert result == []
    assert any("base prompts" in r.getMessage().lower() for r in caplog.records)


def test_create_attack_prompts_no_valid_attacks_returns_empty(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="hivetracered.runner")
    monkeypatch.setattr(runner, "setup_model", lambda cfg: MagicMock())
    monkeypatch.setattr(runner, "load_base_prompts", lambda cfg: ["p1"])
    monkeypatch.setattr(runner, "setup_evaluator", lambda cfg, m: MagicMock())
    monkeypatch.setattr(runner, "setup_attacks", lambda *a, **k: {})

    result = _run(create_attack_prompts({"attacks": []}, str(tmp_path)))

    assert result == []
    assert any("attacks" in r.getMessage().lower() for r in caplog.records)


def test_create_attack_prompts_no_prompts_streamed_returns_empty(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="hivetracered.runner")
    monkeypatch.setattr(runner, "setup_model", lambda cfg: MagicMock())
    monkeypatch.setattr(runner, "load_base_prompts", lambda cfg: ["p1"])
    monkeypatch.setattr(runner, "setup_evaluator", lambda cfg, m: MagicMock())
    monkeypatch.setattr(runner, "setup_attacks", lambda *a, **k: {"A": MagicMock()})
    monkeypatch.setattr(runner, "stream_attack_prompts", lambda attacks, prompts, sysp: _aiter([]))

    saved = []
    monkeypatch.setattr(
        runner, "save_pipeline_results",
        lambda data, run_dir, stage, format="csv": saved.append((stage, list(data))) or {"path": "x"},
    )

    result = _run(create_attack_prompts({"attacks": [{"name": "A"}]}, str(tmp_path)))

    assert result == []
    assert saved == []  # no save when no prompts generated
    assert any("no attack prompts generated" in r.getMessage().lower() for r in caplog.records)


def test_create_attack_prompts_happy_path_returns_prompts_and_saves(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "setup_model", lambda cfg: MagicMock())
    monkeypatch.setattr(runner, "load_base_prompts", lambda cfg: ["p1", "p2"])
    monkeypatch.setattr(runner, "setup_evaluator", lambda cfg, m: MagicMock())
    monkeypatch.setattr(runner, "setup_attacks", lambda *a, **k: {"A": MagicMock()})
    items = [{"prompt": "x", "attack": "A"}, {"prompt": "y", "attack": "A"}]
    monkeypatch.setattr(runner, "stream_attack_prompts", lambda *a, **k: _aiter(items))
    saved: List[Tuple[str, list, str]] = []
    monkeypatch.setattr(
        runner, "save_pipeline_results",
        lambda data, run_dir, stage, format="csv": saved.append((stage, list(data), format)) or {"path": "p"},
    )

    result = _run(create_attack_prompts(
        {"attacks": [{"name": "A"}], "system_prompt": "sys"},
        str(tmp_path),
        output_format="parquet",
    ))

    assert result == items
    assert saved[0][0] == "attack_prompts"
    assert saved[0][1] == items
    assert saved[0][2] == "parquet"


# ── get_model_responses ─────────────────────────────────────────────


def test_get_model_responses_no_response_model_returns_empty(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="hivetracered.runner")
    monkeypatch.setattr(runner, "setup_model", lambda cfg: None)

    result = _run(get_model_responses({}, [{"prompt": "x"}], str(tmp_path)))

    assert result == []
    assert any("response model" in r.getMessage().lower() for r in caplog.records)


def test_get_model_responses_no_responses_returns_empty(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="hivetracered.runner")
    monkeypatch.setattr(runner, "setup_model", lambda cfg: MagicMock())
    monkeypatch.setattr(runner, "stream_model_responses", lambda model, prompts: _aiter([]))
    saved: List[str] = []
    monkeypatch.setattr(
        runner, "save_pipeline_results",
        lambda data, run_dir, stage, format="csv": saved.append(stage) or {"path": "x"},
    )

    result = _run(get_model_responses({}, [{"prompt": "x"}], str(tmp_path)))

    assert result == []
    assert saved == []  # no save on empty
    assert any("no model responses" in r.getMessage().lower() for r in caplog.records)


def test_get_model_responses_happy_path_returns_and_saves(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "setup_model", lambda cfg: MagicMock())
    items = [{"prompt": "x", "response": "r1"}, {"prompt": "y", "response": "r2"}]
    monkeypatch.setattr(runner, "stream_model_responses", lambda *a, **k: _aiter(items))
    saved: List[Tuple[str, list, str]] = []
    monkeypatch.setattr(
        runner, "save_pipeline_results",
        lambda data, run_dir, stage, format="csv": saved.append((stage, list(data), format)) or {"path": "p"},
    )

    result = _run(get_model_responses({}, [{"prompt": "x"}], str(tmp_path), output_format="xlsx"))

    assert result == items
    assert saved[0][0] == "model_responses"
    assert saved[0][1] == items
    assert saved[0][2] == "xlsx"


# ── evaluate_responses ──────────────────────────────────────────────


def test_evaluate_responses_no_evaluator_returns_empty_and_none(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="hivetracered.runner")
    monkeypatch.setattr(runner, "setup_model", lambda cfg: MagicMock())
    monkeypatch.setattr(runner, "setup_evaluator", lambda cfg, m: None)

    results, eval_file = _run(evaluate_responses({}, [{"x": 1}], str(tmp_path)))

    assert results == []
    assert eval_file is None
    assert any("no valid evaluator" in r.getMessage().lower() for r in caplog.records)


def test_evaluate_responses_no_results_returns_empty_and_none(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="hivetracered.runner")
    monkeypatch.setattr(runner, "setup_model", lambda cfg: MagicMock())
    monkeypatch.setattr(runner, "setup_evaluator", lambda cfg, m: MagicMock())
    monkeypatch.setattr(runner, "stream_evaluated_responses", lambda ev, resps: _aiter([]))

    results, eval_file = _run(evaluate_responses({}, [{"x": 1}], str(tmp_path)))

    assert results == []
    assert eval_file is None
    assert any("no evaluation results" in r.getMessage().lower() for r in caplog.records)


def test_evaluate_responses_happy_path_logs_success_rate_and_returns_path(
    monkeypatch, tmp_path, caplog,
):
    caplog.set_level(logging.INFO, logger="hivetracered.runner")
    monkeypatch.setattr(runner, "setup_model", lambda cfg: MagicMock())
    monkeypatch.setattr(runner, "setup_evaluator", lambda cfg, m: MagicMock())
    items = [{"success": True}, {"success": False}, {"success": True}, {"success": True}]
    # = 75.00% success rate (3 out of 4)
    monkeypatch.setattr(runner, "stream_evaluated_responses", lambda *a, **k: _aiter(items))
    monkeypatch.setattr(
        runner, "save_pipeline_results",
        lambda data, run_dir, stage, format="csv": {"path": str(tmp_path / "evals.csv")},
    )

    results, eval_file = _run(evaluate_responses({}, [{"x": 1}], str(tmp_path)))

    assert results == items
    assert eval_file == str(tmp_path / "evals.csv")
    assert any("75.00" in r.getMessage() for r in caplog.records)


# ── _run_stage_attacks ──────────────────────────────────────────────


def test_run_stage_attacks_attacks_enabled_returns_prompts(monkeypatch, tmp_path):
    items = [{"prompt": "p"}]

    async def fake(config, run_dir, output_format):
        return items

    monkeypatch.setattr(runner, "create_attack_prompts", fake)

    prompts, enable_responses = _run(
        _run_stage_attacks({}, str(tmp_path), "csv", True, True),
    )

    assert prompts == items
    assert enable_responses is True


def test_run_stage_attacks_no_prompts_disables_responses(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="hivetracered.runner")

    async def fake(config, run_dir, output_format):
        return []

    monkeypatch.setattr(runner, "create_attack_prompts", fake)

    prompts, enable_responses = _run(
        _run_stage_attacks({}, str(tmp_path), "csv", True, True),
    )

    assert prompts == []
    assert enable_responses is False
    assert any("skipping model responses" in r.getMessage().lower() for r in caplog.records)


def test_run_stage_attacks_disabled_loads_from_file(monkeypatch, tmp_path):
    items = [{"prompt": "p"}]
    monkeypatch.setattr(runner, "load_records", lambda path, label: items)

    prompts, enable_responses = _run(
        _run_stage_attacks(
            {"attack_prompts_file": "/some/path"},
            str(tmp_path), "csv", False, True,
        ),
    )

    assert prompts == items
    assert enable_responses is True


def test_run_stage_attacks_disabled_empty_file_disables_responses(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "load_records", lambda path, label: [])

    prompts, enable_responses = _run(
        _run_stage_attacks(
            {"attack_prompts_file": "/some/path"},
            str(tmp_path), "csv", False, True,
        ),
    )

    assert prompts == []
    assert enable_responses is False


def test_run_stage_attacks_both_disabled_returns_empty(tmp_path):
    prompts, enable_responses = _run(
        _run_stage_attacks({}, str(tmp_path), "csv", False, False),
    )

    assert prompts == []
    assert enable_responses is False


# ── _run_stage_responses ────────────────────────────────────────────


def test_run_stage_responses_enabled_returns_responses(monkeypatch, tmp_path):
    items = [{"response": "r"}]

    async def fake(config, prompts, run_dir, output_format):
        return items

    monkeypatch.setattr(runner, "get_model_responses", fake)

    responses, enable_eval = _run(
        _run_stage_responses({}, [{"p": 1}], str(tmp_path), "csv", True, True),
    )

    assert responses == items
    assert enable_eval is True


def test_run_stage_responses_empty_disables_eval(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="hivetracered.runner")

    async def fake(config, prompts, run_dir, output_format):
        return []

    monkeypatch.setattr(runner, "get_model_responses", fake)

    responses, enable_eval = _run(
        _run_stage_responses({}, [{"p": 1}], str(tmp_path), "csv", True, True),
    )

    assert responses == []
    assert enable_eval is False
    assert any("skipping evaluation" in r.getMessage().lower() for r in caplog.records)


def test_run_stage_responses_disabled_loads_from_file(monkeypatch, tmp_path):
    items = [{"response": "r"}]
    monkeypatch.setattr(runner, "load_records", lambda path, label: items)

    responses, enable_eval = _run(
        _run_stage_responses(
            {"model_responses_file": "/some/path"},
            [], str(tmp_path), "csv", False, True,
        ),
    )

    assert responses == items
    assert enable_eval is True


def test_run_stage_responses_disabled_empty_file_disables_eval(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "load_records", lambda path, label: [])

    responses, enable_eval = _run(
        _run_stage_responses(
            {"model_responses_file": "/some/path"},
            [], str(tmp_path), "csv", False, True,
        ),
    )

    assert responses == []
    assert enable_eval is False


def test_run_stage_responses_both_disabled_returns_empty(tmp_path):
    responses, enable_eval = _run(
        _run_stage_responses({}, [], str(tmp_path), "csv", False, False),
    )

    assert responses == []
    assert enable_eval is False


# ── _run_stage_eval ─────────────────────────────────────────────────


def test_run_stage_eval_enabled_calls_evaluate_responses(monkeypatch, tmp_path):
    expected = ([{"success": True}], "/path/to/evals.csv")

    async def fake(config, responses, run_dir, output_format):
        return expected

    monkeypatch.setattr(runner, "evaluate_responses", fake)

    results, eval_file = _run(
        _run_stage_eval({}, [{"r": 1}], str(tmp_path), "csv", True, True),
    )

    assert results == expected[0]
    assert eval_file == expected[1]


def test_run_stage_eval_disabled_uses_provided_file_when_exists(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="hivetracered.runner")
    eval_file = tmp_path / "evals.csv"
    eval_file.write_text("x", encoding="utf-8")

    results, returned = _run(
        _run_stage_eval(
            {"evaluation_results_file": str(eval_file)},
            [], str(tmp_path), "csv", False, True,
        ),
    )

    assert results == []
    assert returned == str(eval_file)
    assert any("provided evaluation file" in r.getMessage().lower() for r in caplog.records)


def test_run_stage_eval_disabled_missing_file_returns_none(tmp_path):
    results, returned = _run(
        _run_stage_eval(
            {"evaluation_results_file": str(tmp_path / "nope.csv")},
            [], str(tmp_path), "csv", False, True,
        ),
    )

    assert results == []
    assert returned is None


def test_run_stage_eval_all_disabled_returns_none(tmp_path):
    results, returned = _run(
        _run_stage_eval({}, [], str(tmp_path), "csv", False, False),
    )

    assert results == []
    assert returned is None


# ── run_pipeline ────────────────────────────────────────────────────


def test_run_pipeline_happy_path_invokes_all_stages(monkeypatch, tmp_path):
    """All four stages enabled: each stage helper is invoked once and the
    final report is generated.
    """
    cfg = {"output_dir": str(tmp_path), "stages": {}}
    calls: List[str] = []

    async def fake_prepare(config):
        run_dir = str(tmp_path / "run_X")
        os.makedirs(run_dir, exist_ok=True)
        calls.append("prepare")
        return run_dir

    monkeypatch.setattr(runner, "_prepare_run_dir", fake_prepare)
    monkeypatch.setattr(runner, "_preflight_config", lambda *a, **k: calls.append("preflight"))

    async def fake_attacks(config, run_dir, output_format, ea, er):
        calls.append("attacks")
        return [{"p": 1}], er

    async def fake_responses(config, prompts, run_dir, output_format, er, ev):
        calls.append("responses")
        return [{"r": 1}], ev

    async def fake_eval(config, responses, run_dir, output_format, ev, ep):
        calls.append("eval")
        return [{"success": True}], str(tmp_path / "evals.csv")

    monkeypatch.setattr(runner, "_run_stage_attacks", fake_attacks)
    monkeypatch.setattr(runner, "_run_stage_responses", fake_responses)
    monkeypatch.setattr(runner, "_run_stage_eval", fake_eval)
    monkeypatch.setattr(
        runner, "generate_report",
        lambda config, run_dir, eval_file: calls.append("report") or "/some/report.html",
    )

    _run(run_pipeline(cfg))

    assert calls == ["prepare", "preflight", "attacks", "responses", "eval", "report"]


def test_run_pipeline_skips_report_when_no_evaluation_file(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="hivetracered.runner")
    cfg = {"output_dir": str(tmp_path)}

    async def fake_prepare(config):
        run_dir = str(tmp_path / "run_X")
        os.makedirs(run_dir, exist_ok=True)
        return run_dir

    monkeypatch.setattr(runner, "_prepare_run_dir", fake_prepare)
    monkeypatch.setattr(runner, "_preflight_config", lambda *a, **k: None)

    async def fake_attacks(config, run_dir, output_format, ea, er):
        return [], False

    async def fake_responses(config, prompts, run_dir, output_format, er, ev):
        return [], False

    async def fake_eval(config, responses, run_dir, output_format, ev, ep):
        return [], None

    monkeypatch.setattr(runner, "_run_stage_attacks", fake_attacks)
    monkeypatch.setattr(runner, "_run_stage_responses", fake_responses)
    monkeypatch.setattr(runner, "_run_stage_eval", fake_eval)
    report_calls: List[Any] = []
    monkeypatch.setattr(
        runner, "generate_report",
        lambda config, run_dir, eval_file: report_calls.append(eval_file) or "ignored",
    )

    _run(run_pipeline(cfg))

    assert report_calls == []  # generate_report not called when no eval file
    assert any("skipping report" in r.getMessage().lower() for r in caplog.records)


def test_run_pipeline_report_disabled_skips_report_call(monkeypatch, tmp_path):
    cfg = {
        "output_dir": str(tmp_path),
        "stages": {"generate_report": False},
    }

    async def fake_prepare(config):
        run_dir = str(tmp_path / "run_X")
        os.makedirs(run_dir, exist_ok=True)
        return run_dir

    monkeypatch.setattr(runner, "_prepare_run_dir", fake_prepare)
    monkeypatch.setattr(runner, "_preflight_config", lambda *a, **k: None)

    async def fake_attacks(config, run_dir, output_format, ea, er):
        return [{"p": 1}], er

    async def fake_responses(config, prompts, run_dir, output_format, er, ev):
        return [{"r": 1}], ev

    async def fake_eval(config, responses, run_dir, output_format, ev, ep):
        # Returns a path, but report stage is disabled, so generate_report
        # must not be called regardless.
        return [{"success": True}], "/some/file.csv"

    monkeypatch.setattr(runner, "_run_stage_attacks", fake_attacks)
    monkeypatch.setattr(runner, "_run_stage_responses", fake_responses)
    monkeypatch.setattr(runner, "_run_stage_eval", fake_eval)
    report_calls: List[Any] = []
    monkeypatch.setattr(
        runner, "generate_report",
        lambda config, run_dir, eval_file: report_calls.append(eval_file) or "x",
    )

    _run(run_pipeline(cfg))

    assert report_calls == []


def test_run_pipeline_preflight_failure_propagates(monkeypatch, tmp_path):
    """A ValueError from _preflight_config must bubble up to the caller."""
    cfg = {"output_dir": str(tmp_path)}

    async def fake_prepare(config):
        run_dir = str(tmp_path / "run_X")
        os.makedirs(run_dir, exist_ok=True)
        return run_dir

    monkeypatch.setattr(runner, "_prepare_run_dir", fake_prepare)

    def bad_preflight(*a, **k):
        raise ValueError("Stage 1 broken")

    monkeypatch.setattr(runner, "_preflight_config", bad_preflight)

    with pytest.raises(ValueError, match=r"Stage 1 broken"):
        _run(run_pipeline(cfg))
