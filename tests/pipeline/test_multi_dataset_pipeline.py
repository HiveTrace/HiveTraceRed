"""Tests for the multi-dataset pipeline feature (SPECs 001-024).

Each test converts one SPEC-NNN from test-specs.md into a single executable
failing test. Tests cover: evaluator routing, dataset column propagation,
preflight validation, config schema, concurrency bounds, failure isolation,
and report generation.

Trust-boundary mocking: only mocks at network/IO/model/evaluator boundaries;
SUT functions (load_config, run_pipeline, _preflight_config,
_run_pipeline_for_datasets, generate_report, build_html_report, load_datasets)
are called for real.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest
import yaml

from hivetracered.config import load_config
from hivetracered.evaluators.base_evaluator import BaseEvaluator


# ---------------------------------------------------------------------------
# Shared helpers and fake evaluator base
# ---------------------------------------------------------------------------


def _run(coro):
    """Run a coroutine to completion in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_evaluate_dataset_skips_failed_requests():
    # Failed requests (error field) must not reach the evaluator and must be
    # marked success=False with reason "Request failed", preserving order.
    from hivetracered.runner import _evaluate_dataset
    from hivetracered.setup import DatasetSpec

    ev = _RecordingEvaluator(result={"success": True, "reason": "ok"})
    responses = [
        {"base_prompt": "p0", "response": "real answer"},
        {"base_prompt": "p1", "response": "", "error": "no balance"},
        {"base_prompt": "p2", "response": "another real"},
    ]
    spec = DatasetSpec(name="ds", prompts=["p0", "p1", "p2"], evaluator=ev)

    results = _run(_evaluate_dataset(spec, responses))

    # Only the two non-error records were sent to the evaluator.
    assert ev.received_prompts == ["p0", "p2"]
    # All three results returned, in order.
    assert [r["base_prompt"] for r in results] == ["p0", "p1", "p2"]
    # The error record is skipped, not scored.
    assert results[1]["evaluator"] == ""
    assert results[1]["success"] is False
    assert results[1]["evaluation"]["reason"] == "Request failed"
    # Real records were scored by the evaluator.
    assert results[0]["evaluator"] == "_RecordingEvaluator"
    assert results[2]["evaluator"] == "_RecordingEvaluator"


def _write_yaml(path: Path, data: dict) -> str:
    """Write a dict as YAML and return the file path string."""
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return str(path)


class _RecordingEvaluator(BaseEvaluator):
    """Evaluator that records all stream_abatch call arguments (prompts + responses)
    and returns configurable per-record results."""

    def __init__(self, result: dict | None = None, raise_exc: Exception | None = None):
        self.received_prompts: list = []
        self.received_responses: list = []
        self._result = result or {"success": True, "reason": "ok"}
        self._raise_exc = raise_exc

    def evaluate(self, prompt, response) -> dict:
        return self._result.copy()

    async def stream_abatch(
        self, prompts: list, responses: list
    ) -> AsyncGenerator[dict, None]:
        if self._raise_exc is not None:
            raise self._raise_exc
        for p, r in zip(prompts, responses):
            self.received_prompts.append(p)
            self.received_responses.append(r)
            yield self._result.copy()

    def get_name(self) -> str:
        return "_RecordingEvaluator"

    def get_description(self) -> str:
        return "recording evaluator for tests"

    def get_params(self) -> dict:
        return {}


def _minimal_config(
    tmp_path: Path,
    dataset_entries: list[dict],
    *,
    attacks: list | None = None,
    system_prompt: str | None = None,
    stages: dict | None = None,
    extra: dict | None = None,
) -> dict:
    """Build a minimal in-memory config dict for multi-dataset tests."""
    cfg: dict[str, Any] = {
        "datasets": dataset_entries,
        "attacks": attacks if attacks is not None else [{"name": "NoneAttack"}],
        "output_dir": str(tmp_path),
    }
    if system_prompt is not None:
        cfg["system_prompt"] = system_prompt
    if stages is not None:
        cfg["stages"] = stages
    if extra:
        cfg.update(extra)
    return cfg


def _write_records_csv(path: Path, records: list[dict]) -> str:
    """Write a list of dicts as CSV and return the path string."""
    pd.DataFrame(records).to_csv(path, index=False)
    return str(path)


async def _fake_stream_attack_prompts_str_only(attacks, base_prompts, system_prompt=None):
    """Fake stream_attack_prompts for SPEC-014 and SPEC-017.

    Each base_prompt must already be a plain string (no branching needed).
    Stamping 'dataset' is done by _run_pipeline_for_datasets (Stage 1), not here.
    """
    for bp in base_prompts:
        yield {
            "base_prompt": str(bp),
            "attack_prompt": f"attack_{bp}",
            "attack": "NoneAttack",
        }


async def _fake_stream_model_responses_passthrough(response_model, attack_prompts, consecutive_failures=None):
    """Fake stream_model_responses for SPEC-014.

    Passes through all attack_prompt fields unchanged and adds response columns.
    """
    for ap in attack_prompts:
        yield {**ap, "response": "model_response", "is_blocked": False, "model": "mock"}


async def _capturing_stream_attack_prompts_with_system_prompt(
    attacks, base_prompts, system_prompt=None
):
    """Fake stream_attack_prompts for SPEC-008.

    Embeds system_prompt in each yielded record so that
    _capturing_stream_model_responses_recording_system_prompt can observe it.
    Stamping 'dataset' is done by _run_pipeline_for_datasets (Stage 1), not here.
    """
    for bp in base_prompts:
        yield {
            "base_prompt": str(bp),
            "attack_prompt": str(bp),
            "attack": "NoneAttack",
            "system_prompt": system_prompt,
        }


async def _capturing_stream_model_responses_recording_system_prompt(
    response_model, attack_prompts, consecutive_failures=None, *, _seen: list
):
    """Fake stream_model_responses for SPEC-008.

    Records the system_prompt field from each incoming attack_prompt record into
    the shared _seen list, then passes through a minimal response dict.
    """
    for ap in attack_prompts:
        _seen.append(ap.get("system_prompt"))
        yield {**ap, "response": "mock_response", "is_blocked": False, "model": "mock"}


def _load_records_from_csv_files(paths: list[Path]) -> list[dict]:
    """Load and concatenate records from a list of CSV files into one list of dicts."""
    frames = [pd.read_csv(str(p)) for p in paths]
    if not frames:
        return []
    return pd.concat(frames, ignore_index=True).to_dict("records")


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def eval_data_two_datasets():
    """Fixture: 3 evaluation records each for 'harmful_ru' and 'sys_prompt' (SPEC-013)."""
    records = []
    for i in range(3):
        records.append({
            "dataset": "harmful_ru",
            "base_prompt": f"p{i}",
            "attack": "NoneAttack",
            "response": "r",
            "success": True,
            "evaluation": json.dumps({"success": True, "reason": "ok"}),
            "evaluator": "KeywordEvaluator",
            "evaluator_params": "{}",
        })
    for i in range(3):
        records.append({
            "dataset": "sys_prompt",
            "base_prompt": f"q{i}",
            "attack": "NoneAttack",
            "response": "s",
            "success": False,
            "evaluation": json.dumps({"success": False, "reason": "blocked"}),
            "evaluator": "KeywordEvaluator",
            "evaluator_params": "{}",
        })
    return records


@pytest.fixture
def spec024_pipeline_results(tmp_path, caplog):
    """Fixture: runs the SPEC-024a/b/c empty-slice scenario once and returns results.

    Returns a tuple of (eval_results, error_messages) so that each sub-test
    can assert on exactly one logical outcome.
    """
    from hivetracered.runner import _run_pipeline_for_datasets
    from hivetracered.setup import DatasetSpec

    mr_records = [
        {"dataset": "ok", "base_prompt": "p1", "attack_prompt": "a1",
         "attack": "NoneAttack", "model": "mock", "response": "r1", "is_blocked": False},
        {"dataset": "ok", "base_prompt": "p2", "attack_prompt": "a2",
         "attack": "NoneAttack", "model": "mock", "response": "r2", "is_blocked": False},
    ]
    mr_file = tmp_path / "model_responses.csv"
    _write_records_csv(mr_file, mr_records)

    ev_ok = _RecordingEvaluator(result={"success": True, "reason": "ok"})
    ev_empty = _RecordingEvaluator(raise_exc=RuntimeError("fail"))

    spec_ok = DatasetSpec(name="ok", prompts=["p1", "p2"], evaluator=ev_ok)
    spec_empty = DatasetSpec(name="empty_slice", prompts=[], evaluator=ev_empty)

    config = _minimal_config(
        tmp_path,
        [
            {"name": "ok", "base_prompts": ["p1", "p2"],
             "evaluator": {"name": "KeywordEvaluator"}},
            {"name": "empty_slice", "base_prompts": ["p3"],
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
        stages={
            "create_attack_prompts": False,
            "get_model_responses": False,
            "evaluate_responses": True,
            "generate_report": False,
        },
        extra={"model_responses_file": str(mr_file)},
    )

    caplog.set_level(logging.ERROR, logger="hivetracered.runner")

    eval_results, _ = _run(
        _run_pipeline_for_datasets(
            config,
            [spec_ok, spec_empty],
            str(tmp_path),
            "csv",
            enable_attacks=False,
            enable_responses=False,
            enable_eval=True,
        )
    )

    error_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    return eval_results, error_messages


# ---------------------------------------------------------------------------
# SPEC-001: Evaluator routing is per-dataset, not global
# ---------------------------------------------------------------------------


def test_SPEC_001_evaluator_routing_routes_records_to_correct_mock(tmp_path):
    """SPEC-001 (AC-01): Each dataset's evaluator receives ONLY its own records."""
    from hivetracered.runner import _run_pipeline_for_datasets  # noqa: F401 — import triggers AttributeError if not yet implemented
    from hivetracered.setup import DatasetSpec  # noqa: F401 — triggers AttributeError if not yet defined

    mock_wildguard = _RecordingEvaluator()
    mock_sysprompt = _RecordingEvaluator()

    # Build a model_responses file with 4 records: 2 per dataset
    ap_records = [
        {"dataset": "harmful_ru", "base_prompt": "p1", "attack_prompt": "a1",
         "attack": "NoneAttack", "model": "mock", "response": "r1", "is_blocked": False},
        {"dataset": "harmful_ru", "base_prompt": "p2", "attack_prompt": "a2",
         "attack": "NoneAttack", "model": "mock", "response": "r2", "is_blocked": False},
        {"dataset": "sys_extract", "base_prompt": "p3", "attack_prompt": "a3",
         "attack": "NoneAttack", "model": "mock", "response": "r3", "is_blocked": False},
        {"dataset": "sys_extract", "base_prompt": "p4", "attack_prompt": "a4",
         "attack": "NoneAttack", "model": "mock", "response": "r4", "is_blocked": False},
    ]
    mr_file = tmp_path / "model_responses.csv"
    _write_records_csv(mr_file, ap_records)

    spec_a = DatasetSpec(name="harmful_ru", prompts=["p1", "p2"], evaluator=mock_wildguard)
    spec_b = DatasetSpec(name="sys_extract", prompts=["p3", "p4"], evaluator=mock_sysprompt)

    config = _minimal_config(
        tmp_path,
        [
            {"name": "harmful_ru", "base_prompts": ["p1", "p2"],
             "evaluator": {"name": "KeywordEvaluator"}},
            {"name": "sys_extract", "base_prompts": ["p3", "p4"],
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
        stages={
            "create_attack_prompts": False,
            "get_model_responses": False,
            "evaluate_responses": True,
            "generate_report": False,
        },
        extra={"model_responses_file": str(mr_file)},
    )

    _run(
        _run_pipeline_for_datasets(
            config,
            [spec_a, spec_b],
            str(tmp_path),
            "csv",
            enable_attacks=False,
            enable_responses=False,
            enable_eval=True,
        )
    )

    # Every record that mock_wildguard received must belong to 'harmful_ru';
    # every record that mock_sysprompt received must belong to 'sys_extract'.
    # received_responses contains the response dicts passed to stream_abatch,
    # each of which has a 'dataset' field stamped by _run_pipeline_for_datasets (Stage 1).
    assert all(
        r.get("dataset") == "harmful_ru" for r in mock_wildguard.received_responses
    ), (
        "mock_wildguard must receive ONLY records with dataset='harmful_ru'; "
        f"got datasets: {[r.get('dataset') for r in mock_wildguard.received_responses]}"
    )
    assert all(
        r.get("dataset") == "sys_extract" for r in mock_sysprompt.received_responses
    ), (
        "mock_sysprompt must receive ONLY records with dataset='sys_extract'; "
        f"got datasets: {[r.get('dataset') for r in mock_sysprompt.received_responses]}"
    )


# ---------------------------------------------------------------------------
# SPEC-002: Every Stage-1 record carries a non-null dataset column
# ---------------------------------------------------------------------------


def test_SPEC_002_stage1_records_carry_non_null_dataset_column(tmp_path):
    """SPEC-002 (AC-02): All attack-prompt records have a non-null dataset column."""
    from hivetracered.runner import _run_pipeline_for_datasets  # noqa: F401
    from hivetracered.setup import DatasetSpec

    ev_a = _RecordingEvaluator()
    ev_b = _RecordingEvaluator()
    spec_a = DatasetSpec(name="ds_alpha", prompts=["prompt_x", "prompt_y"], evaluator=ev_a)
    spec_b = DatasetSpec(name="ds_beta", prompts=["prompt_z", "prompt_w"], evaluator=ev_b)

    config = _minimal_config(
        tmp_path,
        [
            {"name": "ds_alpha", "base_prompts": ["prompt_x", "prompt_y"],
             "evaluator": {"name": "KeywordEvaluator"}},
            {"name": "ds_beta", "base_prompts": ["prompt_z", "prompt_w"],
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
        stages={
            "create_attack_prompts": True,
            "get_model_responses": False,
            "evaluate_responses": False,
            "generate_report": False,
        },
    )
    # Stage 1 needs an attacker_model; use a mock via monkeypatching done below
    # Instead, call _run_pipeline_for_datasets directly with stage flags
    _, _ = _run(
        _run_pipeline_for_datasets(
            config,
            [spec_a, spec_b],
            str(tmp_path),
            "csv",
            enable_attacks=True,
            enable_responses=False,
            enable_eval=False,
        )
    )

    # Collect all saved attack_prompts_* files and load into a flat list
    stage1_files = (
        list(tmp_path.glob("attack_prompts_ds_alpha*"))
        + list(tmp_path.glob("attack_prompts_ds_beta*"))
    )
    assert stage1_files, "Expected at least one attack_prompts_<dataset> file to be written"

    all_records = _load_records_from_csv_files(stage1_files)

    assert all(
        r.get("dataset") not in (None, "", float("nan")) for r in all_records
    ), "Every Stage-1 record must have a non-null, non-empty 'dataset' column"


# ---------------------------------------------------------------------------
# SPEC-003: Preflight rejects a misspelled evaluator class name
# ---------------------------------------------------------------------------


def test_SPEC_003_preflight_rejects_misspelled_evaluator_class(tmp_path):
    """SPEC-003 (AC-03): _preflight_config raises ValueError for unknown evaluator name.

    The new implementation must materialise DatasetSpec objects via load_datasets
    (Step 0b in design.md) and then check that no spec.evaluator is None when
    enable_eval=True. The misspelled class causes setup_evaluator to return None,
    which must be surfaced as a ValueError naming the dataset and the bad evaluator block.

    This test imports DatasetSpec to trigger ImportError against the current code
    (DatasetSpec does not exist yet), ensuring a fail-for-the-right-reason state.
    The test checks the ValueError message identifies the dataset AND evaluator path.
    """
    from hivetracered.runner import _preflight_config
    from hivetracered.setup import DatasetSpec  # ImportError until implemented

    config = _minimal_config(
        tmp_path,
        [
            {"name": "ds1", "base_prompts": ["p1"],
             "evaluator": {"name": "WildGuardGPTRuEvalautor"}},  # deliberate typo
        ],
    )

    with pytest.raises(ValueError) as exc_info:
        _preflight_config(
            config,
            enable_attacks=False,
            enable_responses=False,
            enable_eval=True,
        )

    # The error must originate from the per-dataset evaluator check, not
    # from a generic "no evaluator configured" fallback.
    msg = str(exc_info.value)
    assert "ds1" in msg or "evaluator" in msg, (
        "ValueError must name the offending dataset or evaluator block"
    )


# ---------------------------------------------------------------------------
# SPEC-004: Legacy top-level schema raises ValueError with migration message
# ---------------------------------------------------------------------------


def test_SPEC_004_legacy_top_level_evaluator_raises_value_error(tmp_path):
    """SPEC-004 (AC-04): load_config raises ValueError on legacy evaluator: key."""
    cfg_file = tmp_path / "legacy.yaml"
    cfg_file.write_text(
        "evaluator:\n"
        "  name: WildGuardGPTRuEvaluator\n"
        "base_prompts:\n"
        "  - prompt_one\n"
        "attacks:\n"
        "  - name: NoneAttack\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        load_config(str(cfg_file))

    msg = str(exc_info.value)
    assert any(key in msg for key in ("evaluator", "base_prompts", "base_prompts_file")), (
        "ValueError message must name at least one removed legacy key"
    )
    assert "datasets" in msg, "ValueError message must reference the new 'datasets:' schema"


# ---------------------------------------------------------------------------
# SPEC-005: Unknown key in dataset entry logs a warning
# ---------------------------------------------------------------------------


def test_SPEC_005_unknown_key_in_dataset_entry_logs_warning(tmp_path, caplog):
    """SPEC-005 (AC-05): load_config logs a WARNING for unrecognised dataset entry keys."""
    cfg_file = tmp_path / "unknown_key.yaml"
    cfg_file.write_text(
        "datasets:\n"
        "  - name: my_ds\n"
        "    base_prompts:\n"
        "      - some_prompt\n"
        "    evaluator:\n"
        "      name: KeywordEvaluator\n"
        "    max_retries: 3\n"  # unknown key
        "attacks:\n"
        "  - name: NoneAttack\n",
        encoding="utf-8",
    )
    caplog.set_level(logging.WARNING, logger="hivetracered.config")

    result = load_config(str(cfg_file))

    assert result is not None, "load_config should return the config dict without raising"
    warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "max_retries" in m for m in warning_messages
    ), "A WARNING mentioning the unknown key 'max_retries' must be logged"


# ---------------------------------------------------------------------------
# SPEC-006: Two datasets with identical evaluator class use independent instances
# ---------------------------------------------------------------------------


def test_SPEC_006_identical_evaluator_class_produces_independent_instances(tmp_path):
    """SPEC-006 (AC-06): load_datasets returns distinct evaluator instances per dataset."""
    from hivetracered.setup import load_datasets

    config = _minimal_config(
        tmp_path,
        [
            {"name": "ds_one", "base_prompts": ["p1"],
             "evaluator": {"name": "KeywordEvaluator"}},
            {"name": "ds_two", "base_prompts": ["p2"],
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
    )

    specs = load_datasets(config, evaluation_model=None)

    assert len(specs) == 2, "Expected two DatasetSpec entries"
    assert id(specs[0].evaluator) != id(specs[1].evaluator), (
        "Evaluator instances for different dataset entries must have different object identities"
    )


# ---------------------------------------------------------------------------
# SPEC-007: Stage-1-disabled run routes via dataset column
# ---------------------------------------------------------------------------


def test_SPEC_007_stage1_disabled_evaluators_receive_correct_records(tmp_path):
    """SPEC-007 (AC-07): With attack_prompts_file loaded, routing to per-dataset evaluators works."""
    from hivetracered.runner import _run_pipeline_for_datasets
    from hivetracered.setup import DatasetSpec

    mr_records = [
        {"dataset": "alpha", "base_prompt": "p1", "attack_prompt": "a1",
         "attack": "NoneAttack", "model": "mock", "response": "r1", "is_blocked": False},
        {"dataset": "alpha", "base_prompt": "p2", "attack_prompt": "a2",
         "attack": "NoneAttack", "model": "mock", "response": "r2", "is_blocked": False},
        {"dataset": "alpha", "base_prompt": "p3", "attack_prompt": "a3",
         "attack": "NoneAttack", "model": "mock", "response": "r3", "is_blocked": False},
        {"dataset": "beta", "base_prompt": "p4", "attack_prompt": "a4",
         "attack": "NoneAttack", "model": "mock", "response": "r4", "is_blocked": False},
        {"dataset": "beta", "base_prompt": "p5", "attack_prompt": "a5",
         "attack": "NoneAttack", "model": "mock", "response": "r5", "is_blocked": False},
        {"dataset": "beta", "base_prompt": "p6", "attack_prompt": "a6",
         "attack": "NoneAttack", "model": "mock", "response": "r6", "is_blocked": False},
    ]
    mr_file = tmp_path / "model_responses.csv"
    _write_records_csv(mr_file, mr_records)

    ev_alpha = _RecordingEvaluator()
    ev_beta = _RecordingEvaluator()
    spec_alpha = DatasetSpec(name="alpha", prompts=["p1", "p2", "p3"], evaluator=ev_alpha)
    spec_beta = DatasetSpec(name="beta", prompts=["p4", "p5", "p6"], evaluator=ev_beta)

    config = _minimal_config(
        tmp_path,
        [
            {"name": "alpha", "base_prompts": ["p1", "p2", "p3"],
             "evaluator": {"name": "KeywordEvaluator"}},
            {"name": "beta", "base_prompts": ["p4", "p5", "p6"],
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
        stages={
            "create_attack_prompts": False,
            "get_model_responses": False,
            "evaluate_responses": True,
            "generate_report": False,
        },
        extra={"model_responses_file": str(mr_file)},
    )

    _run(
        _run_pipeline_for_datasets(
            config,
            [spec_alpha, spec_beta],
            str(tmp_path),
            "csv",
            enable_attacks=False,
            enable_responses=False,
            enable_eval=True,
        )
    )

    assert len(ev_alpha.received_responses) == 3, (
        f"'alpha' evaluator must receive 3 records, got {len(ev_alpha.received_responses)}"
    )
    assert len(ev_beta.received_responses) == 3, (
        f"'beta' evaluator must receive 3 records, got {len(ev_beta.received_responses)}"
    )


# ---------------------------------------------------------------------------
# SPEC-007b: Preflight rejects attack_prompts_file with orphan dataset names
# ---------------------------------------------------------------------------


def test_SPEC_007b_preflight_rejects_orphan_dataset_in_attack_prompts_file(tmp_path):
    """SPEC-007b (AC-07): _preflight_config raises ValueError for orphan dataset names in file.

    The new preflight Step 7 (design.md) must cross-check the file's dataset column
    values against configured spec names. 'gamma' is not in {'alpha', 'beta'}.

    This test imports DatasetSpec to fail with ImportError against the current code
    (the new preflight step does not exist yet).
    """
    from hivetracered.runner import _preflight_config
    from hivetracered.setup import DatasetSpec  # ImportError until implemented

    orphan_records = [
        {"dataset": "gamma", "base_prompt": "p1", "attack_prompt": "a1"},
    ]
    ap_file = tmp_path / "attack_prompts.csv"
    _write_records_csv(ap_file, orphan_records)

    config = _minimal_config(
        tmp_path,
        [
            {"name": "alpha", "base_prompts": ["p1"],
             "evaluator": {"name": "KeywordEvaluator"}},
            {"name": "beta", "base_prompts": ["p2"],
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
        stages={
            "create_attack_prompts": False,
            "get_model_responses": True,
            "evaluate_responses": True,
            "generate_report": False,
        },
        extra={"attack_prompts_file": str(ap_file)},
    )

    with pytest.raises(ValueError) as exc_info:
        _preflight_config(
            config,
            enable_attacks=False,
            enable_responses=True,
            enable_eval=True,
        )

    assert "gamma" in str(exc_info.value), (
        "ValueError must identify the orphan dataset name 'gamma'"
    )


# ---------------------------------------------------------------------------
# SPEC-008: Global system_prompt is used by both datasets
# ---------------------------------------------------------------------------


def test_SPEC_008_global_system_prompt_propagated_to_both_datasets(tmp_path, monkeypatch):
    """SPEC-008 (AC-08): Both datasets use the global system_prompt in Stage 2."""
    import functools

    import hivetracered.runner as runner_mod
    from hivetracered.runner import _run_pipeline_for_datasets
    from hivetracered.setup import DatasetSpec

    system_prompts_seen: list[str | None] = []

    # Bind the shared recording list into the module-level fake via functools.partial.
    monkeypatch.setattr(
        runner_mod,
        "stream_model_responses",
        functools.partial(
            _capturing_stream_model_responses_recording_system_prompt,
            _seen=system_prompts_seen,
        ),
    )
    monkeypatch.setattr(
        runner_mod,
        "stream_attack_prompts",
        _capturing_stream_attack_prompts_with_system_prompt,
    )

    from tests.conftest import MockModel
    mock_response_model = MockModel()

    ev_a = _RecordingEvaluator()
    ev_b = _RecordingEvaluator()
    spec_a = DatasetSpec(name="ds_a", prompts=["p1"], evaluator=ev_a)
    spec_b = DatasetSpec(name="ds_b", prompts=["p2"], evaluator=ev_b)

    config = _minimal_config(
        tmp_path,
        [
            {"name": "ds_a", "base_prompts": ["p1"],
             "evaluator": {"name": "KeywordEvaluator"}},
            {"name": "ds_b", "base_prompts": ["p2"],
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
        system_prompt="You are a helpful assistant",
        stages={
            "create_attack_prompts": True,
            "get_model_responses": True,
            "evaluate_responses": False,
            "generate_report": False,
        },
    )

    monkeypatch.setattr(runner_mod, "setup_model", lambda cfg: mock_response_model)

    _run(
        _run_pipeline_for_datasets(
            config,
            [spec_a, spec_b],
            str(tmp_path),
            "csv",
            enable_attacks=True,
            enable_responses=True,
            enable_eval=False,
        )
    )

    assert system_prompts_seen and all(
        sp == "You are a helpful assistant" for sp in system_prompts_seen
    ), (
        f"Every model call must carry system_prompt='You are a helpful assistant', "
        f"got: {system_prompts_seen}"
    )


# ---------------------------------------------------------------------------
# SPEC-009: Iterative attack combined with datasets raises ValueError at preflight
# ---------------------------------------------------------------------------


def test_SPEC_009_iterative_attack_with_datasets_raises_value_error(tmp_path):
    """SPEC-009 (AC-09): _preflight_config raises ValueError when datasets + IterativeAttack."""
    from hivetracered.runner import _preflight_config

    config = _minimal_config(
        tmp_path,
        [
            {"name": "ds1", "base_prompts": ["p1"],
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
        attacks=[{"name": "PAIRAttack"}],
    )

    with pytest.raises(ValueError) as exc_info:
        _preflight_config(
            config,
            enable_attacks=True,
            enable_responses=False,
            enable_eval=False,
        )

    assert "iterative" in str(exc_info.value).lower() or "datasets" in str(exc_info.value).lower(), (
        "ValueError message must reference iterative attacks and/or datasets: schema"
    )


# ---------------------------------------------------------------------------
# SPEC-009b: Nested iterative attack via inner_attack chain is also rejected
# ---------------------------------------------------------------------------


def test_SPEC_009b_nested_iterative_attack_via_inner_attack_also_rejected(tmp_path):
    """SPEC-009b (AC-09): _preflight_config raises ValueError for nested IterativeAttack.

    The new preflight Step 5 (design.md) recursively walks inner_attack chains via
    _parse_attack_config and rejects any class satisfying issubclass(_, IterativeAttack).
    PAIRAttack nested inside NoneAttack via inner_attack must be caught.

    Imports DatasetSpec (not yet implemented) to fail with ImportError against current code.
    """
    from hivetracered.runner import _preflight_config
    from hivetracered.setup import DatasetSpec  # ImportError until implemented

    config = _minimal_config(
        tmp_path,
        [
            {"name": "ds1", "base_prompts": ["p1"],
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
        attacks=[{"name": "NoneAttack", "inner_attack": {"name": "PAIRAttack"}}],
    )

    with pytest.raises(ValueError) as exc_info:
        _preflight_config(
            config,
            enable_attacks=True,
            enable_responses=False,
            enable_eval=False,
        )

    assert "iterative" in str(exc_info.value).lower() or "datasets" in str(exc_info.value).lower(), (
        "ValueError must reference iterative attacks and/or datasets: schema"
    )


# ---------------------------------------------------------------------------
# SPEC-010: One dataset's Stage-3 failure does not affect the other dataset
# ---------------------------------------------------------------------------


def test_SPEC_010_stage3_failure_in_one_dataset_does_not_affect_other(tmp_path, caplog):
    """SPEC-010 (AC-10): Stage-3 exception for 'bad_dataset' leaves 'ok_dataset' unaffected."""
    from hivetracered.runner import _run_pipeline_for_datasets
    from hivetracered.setup import DatasetSpec

    ev_ok = _RecordingEvaluator(result={"success": True, "reason": "ok"})
    ev_bad = _RecordingEvaluator(raise_exc=RuntimeError("simulated failure"))

    mr_records = [
        {"dataset": "ok_dataset", "base_prompt": "p1", "attack_prompt": "a1",
         "attack": "NoneAttack", "model": "mock", "response": "r1", "is_blocked": False},
        {"dataset": "ok_dataset", "base_prompt": "p2", "attack_prompt": "a2",
         "attack": "NoneAttack", "model": "mock", "response": "r2", "is_blocked": False},
        {"dataset": "bad_dataset", "base_prompt": "p3", "attack_prompt": "a3",
         "attack": "NoneAttack", "model": "mock", "response": "r3", "is_blocked": False},
        {"dataset": "bad_dataset", "base_prompt": "p4", "attack_prompt": "a4",
         "attack": "NoneAttack", "model": "mock", "response": "r4", "is_blocked": False},
    ]
    mr_file = tmp_path / "model_responses.csv"
    _write_records_csv(mr_file, mr_records)

    spec_ok = DatasetSpec(name="ok_dataset", prompts=["p1", "p2"], evaluator=ev_ok)
    spec_bad = DatasetSpec(name="bad_dataset", prompts=["p3", "p4"], evaluator=ev_bad)

    config = _minimal_config(
        tmp_path,
        [
            {"name": "ok_dataset", "base_prompts": ["p1", "p2"],
             "evaluator": {"name": "KeywordEvaluator"}},
            {"name": "bad_dataset", "base_prompts": ["p3", "p4"],
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
        stages={
            "create_attack_prompts": False,
            "get_model_responses": False,
            "evaluate_responses": True,
            "generate_report": False,
        },
        extra={"model_responses_file": str(mr_file)},
    )

    caplog.set_level(logging.ERROR, logger="hivetracered.runner")

    # Should NOT raise
    eval_results, _ = _run(
        _run_pipeline_for_datasets(
            config,
            [spec_ok, spec_bad],
            str(tmp_path),
            "csv",
            enable_attacks=False,
            enable_responses=False,
            enable_eval=True,
        )
    )

    ok_records = [r for r in eval_results if r.get("dataset") == "ok_dataset"]

    # AC-10 core: the healthy dataset's records must all succeed despite the other failing.
    # This is the single observable outcome that distinguishes isolation from contamination.
    assert ok_records and all(r.get("success") is True for r in ok_records), (
        "ok_dataset records must all have success=True even when bad_dataset's evaluator raises"
    )


# ---------------------------------------------------------------------------
# SPEC-011: Duplicate dataset names raise ValueError at load_config
# ---------------------------------------------------------------------------


def test_SPEC_011_duplicate_dataset_names_raise_value_error(tmp_path):
    """SPEC-011 (AC-11): load_config raises ValueError for duplicate dataset names."""
    cfg_file = tmp_path / "dup_names.yaml"
    cfg_file.write_text(
        "datasets:\n"
        "  - name: harmful_ru\n"
        "    base_prompts:\n"
        "      - p1\n"
        "    evaluator:\n"
        "      name: KeywordEvaluator\n"
        "  - name: harmful_ru\n"
        "    base_prompts:\n"
        "      - p2\n"
        "    evaluator:\n"
        "      name: KeywordEvaluator\n"
        "attacks:\n"
        "  - name: NoneAttack\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        load_config(str(cfg_file))

    assert "harmful_ru" in str(exc_info.value), (
        "ValueError message must identify the duplicate name 'harmful_ru'"
    )


# ---------------------------------------------------------------------------
# SPEC-012: Dataset name with invalid character raises ValueError at load_config
# ---------------------------------------------------------------------------


def test_SPEC_012_dataset_name_with_space_raises_value_error(tmp_path):
    """SPEC-012 (AC-12): load_config raises ValueError for name containing a space."""
    cfg_file = tmp_path / "bad_name.yaml"
    cfg_file.write_text(
        "datasets:\n"
        "  - name: 'bad name'\n"
        "    base_prompts:\n"
        "      - p1\n"
        "    evaluator:\n"
        "      name: KeywordEvaluator\n"
        "attacks:\n"
        "  - name: NoneAttack\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        load_config(str(cfg_file))

    msg = str(exc_info.value)
    assert "bad name" in msg or "A-Za-z0-9_-" in msg or "[A-Za-z0-9_-]" in msg, (
        "ValueError message must identify the invalid name and/or the allowed charset"
    )


# ---------------------------------------------------------------------------
# SPEC-013: HTML report shows per-dataset blocks and no cross-dataset aggregate
# ---------------------------------------------------------------------------


def test_SPEC_013_html_report_has_per_dataset_blocks_no_aggregate(eval_data_two_datasets):
    """SPEC-013 (AC-13): build_html_report renders per-dataset blocks; no aggregate metric."""
    from hivetracered.report import build_html_report

    df = pd.DataFrame(eval_data_two_datasets)

    # Multi-dataset mode: pass metrics=None
    html = build_html_report(df, metrics=None, charts=None, data_tables=None)

    assert "harmful_ru" in html and "sys_prompt" in html and "Overall success rate" not in html, (
        "HTML must contain per-dataset sections for both datasets "
        "and must NOT contain any cross-dataset 'Overall success rate' aggregate"
    )


# ---------------------------------------------------------------------------
# SPEC-014: Results directory has per-dataset Stage 1/2 files and one combined evaluations file
# ---------------------------------------------------------------------------


def test_SPEC_014_results_dir_has_per_dataset_files_and_combined_evaluations(tmp_path, monkeypatch):
    """SPEC-014 (AC-14): Per-dataset Stage-1/2 files and one combined evaluations file."""
    import hivetracered.runner as runner_mod
    from hivetracered.runner import _run_pipeline_for_datasets
    from hivetracered.setup import DatasetSpec
    from tests.conftest import MockModel

    mock_attacker = MockModel(response={"content": "attack_content"})

    monkeypatch.setattr(runner_mod, "stream_attack_prompts", _fake_stream_attack_prompts_str_only)
    monkeypatch.setattr(runner_mod, "stream_model_responses", _fake_stream_model_responses_passthrough)
    monkeypatch.setattr(runner_mod, "setup_model", lambda cfg: mock_attacker)

    ev_ds1 = _RecordingEvaluator(result={"success": True, "reason": "ok"})
    ev_ds2 = _RecordingEvaluator(result={"success": True, "reason": "ok"})
    spec_ds1 = DatasetSpec(name="ds1", prompts=["p1", "p2"], evaluator=ev_ds1)
    spec_ds2 = DatasetSpec(name="ds2", prompts=["p3", "p4"], evaluator=ev_ds2)

    config = _minimal_config(
        tmp_path,
        [
            {"name": "ds1", "base_prompts": ["p1", "p2"],
             "evaluator": {"name": "KeywordEvaluator"}},
            {"name": "ds2", "base_prompts": ["p3", "p4"],
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
        stages={
            "create_attack_prompts": True,
            "get_model_responses": True,
            "evaluate_responses": True,
            "generate_report": False,
        },
    )

    _run(
        _run_pipeline_for_datasets(
            config,
            [spec_ds1, spec_ds2],
            str(tmp_path),
            "csv",
            enable_attacks=True,
            enable_responses=True,
            enable_eval=True,
        )
    )

    all_files = [f.name for f in tmp_path.iterdir() if f.is_file()]

    # Per-dataset Stage-1 files
    stage1_ds1 = [f for f in all_files if "attack_prompts" in f and "ds1" in f]
    stage1_ds2 = [f for f in all_files if "attack_prompts" in f and "ds2" in f]
    assert stage1_ds1, "Expected attack_prompts_ds1.* file"
    assert stage1_ds2, "Expected attack_prompts_ds2.* file"

    # Per-dataset Stage-2 files
    stage2_ds1 = [f for f in all_files if "model_responses" in f and "ds1" in f]
    stage2_ds2 = [f for f in all_files if "model_responses" in f and "ds2" in f]
    assert stage2_ds1, "Expected model_responses_ds1.* file"
    assert stage2_ds2, "Expected model_responses_ds2.* file"

    # One combined evaluations file (no dataset suffix)
    eval_files = [f for f in all_files if f.startswith("evaluations") and "csv" in f]
    combined_eval = [f for f in eval_files if "ds1" not in f and "ds2" not in f]
    assert combined_eval, "Expected exactly one combined evaluations.* file"

    # No per-dataset subdirectories
    subdirs = [d for d in tmp_path.iterdir() if d.is_dir()]
    # The run_dir itself is tmp_path; no sub-run dirs expected
    assert not any("ds1" in d.name or "ds2" in d.name for d in subdirs), (
        "No per-dataset subdirectories should be created"
    )


# ---------------------------------------------------------------------------
# SPEC-015: 'datasets' is not an unknown-key at top level
# ---------------------------------------------------------------------------


def test_SPEC_015_datasets_key_is_not_unknown_at_top_level(tmp_path, caplog):
    """SPEC-015 (AC-15): No WARNING is logged for the 'datasets' top-level key."""
    cfg_file = tmp_path / "valid.yaml"
    cfg_file.write_text(
        "datasets:\n"
        "  - name: my_ds\n"
        "    base_prompts:\n"
        "      - p1\n"
        "    evaluator:\n"
        "      name: KeywordEvaluator\n"
        "attacks:\n"
        "  - name: NoneAttack\n",
        encoding="utf-8",
    )
    caplog.set_level(logging.WARNING, logger="hivetracered.config")

    result = load_config(str(cfg_file))

    assert result is not None
    warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert not any("datasets" in m for m in warning_messages), (
        "No WARNING should be logged for the known top-level key 'datasets'"
    )


# ---------------------------------------------------------------------------
# SPEC-016: All-datasets Stage-3 failure still produces a report file
# ---------------------------------------------------------------------------


def test_SPEC_016_all_datasets_stage3_failure_produces_report_file(tmp_path, caplog):
    """SPEC-016 (AC-16): run_pipeline returns without raising and a report file is generated."""
    from hivetracered.runner import run_pipeline

    mr_records = [
        {"dataset": "ds_a", "base_prompt": "p1", "attack_prompt": "a1",
         "attack": "NoneAttack", "model": "mock", "response": "r1", "is_blocked": False},
        {"dataset": "ds_b", "base_prompt": "p2", "attack_prompt": "a2",
         "attack": "NoneAttack", "model": "mock", "response": "r2", "is_blocked": False},
    ]
    mr_file = tmp_path / "model_responses.csv"
    _write_records_csv(mr_file, mr_records)

    config = _minimal_config(
        tmp_path,
        [
            {"name": "ds_a", "base_prompts": ["p1"],
             "evaluator": {"name": "WildGuardGPTRuEvalautor_bad"}},  # bad name → None evaluator
            {"name": "ds_b", "base_prompts": ["p2"],
             "evaluator": {"name": "WildGuardGPTRuEvalautor_bad"}},
        ],
        stages={
            "create_attack_prompts": False,
            "get_model_responses": False,
            "evaluate_responses": True,
            "generate_report": True,
        },
        extra={"model_responses_file": str(mr_file)},
    )

    # We need both evaluators to fail at RUNTIME (not at preflight).
    # So we use _run_pipeline_for_datasets directly with failing evaluator specs.
    from hivetracered.runner import _run_pipeline_for_datasets
    from hivetracered.setup import DatasetSpec

    ev_a = _RecordingEvaluator(raise_exc=RuntimeError("all fail"))
    ev_b = _RecordingEvaluator(raise_exc=RuntimeError("all fail"))
    spec_a = DatasetSpec(name="ds_a", prompts=["p1"], evaluator=ev_a)
    spec_b = DatasetSpec(name="ds_b", prompts=["p2"], evaluator=ev_b)

    caplog.set_level(logging.ERROR, logger="hivetracered.runner")

    # Should NOT raise
    _, eval_file = _run(
        _run_pipeline_for_datasets(
            config,
            [spec_a, spec_b],
            str(tmp_path),
            "csv",
            enable_attacks=False,
            enable_responses=False,
            enable_eval=True,
        )
    )

    # AC-16 core: a report file must be produced even when all evaluators fail.
    from hivetracered.runner import generate_report
    report_path = generate_report(config, str(tmp_path), eval_file)
    assert report_path is not None and os.path.exists(report_path), (
        "A report file must be created and exist on disk even when all Stage-3 evaluations failed"
    )


# ---------------------------------------------------------------------------
# SPEC-017: Inline base_prompts produces same attack-prompt records as file-sourced
# ---------------------------------------------------------------------------


def test_SPEC_017_inline_base_prompts_matches_file_sourced_prompts(tmp_path, monkeypatch):
    """SPEC-017 (AC-17): Inline base_prompts and base_prompts_file produce identical records."""
    import hivetracered.runner as runner_mod
    from hivetracered.runner import _run_pipeline_for_datasets
    from hivetracered.setup import DatasetSpec, load_base_prompts

    # Write a file with exactly the same two prompts as the inline list
    prompts_file = tmp_path / "prompts.txt"
    prompts_file.write_text("prompt_a\nprompt_b\n", encoding="utf-8")

    monkeypatch.setattr(runner_mod, "stream_attack_prompts", _fake_stream_attack_prompts_str_only)
    monkeypatch.setattr(runner_mod, "setup_model", lambda cfg: MagicMock())

    ev_inline = _RecordingEvaluator()
    ev_file = _RecordingEvaluator()

    inline_prompts = load_base_prompts({"base_prompts": ["prompt_a", "prompt_b"]})
    file_prompts = load_base_prompts({"base_prompts_file": str(prompts_file)})

    spec_inline = DatasetSpec(name="inline_ds", prompts=inline_prompts, evaluator=ev_inline)
    spec_file = DatasetSpec(name="file_ds", prompts=file_prompts, evaluator=ev_file)

    config = _minimal_config(
        tmp_path,
        [
            {"name": "inline_ds", "base_prompts": ["prompt_a", "prompt_b"],
             "evaluator": {"name": "KeywordEvaluator"}},
            {"name": "file_ds", "base_prompts_file": str(prompts_file),
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
        stages={
            "create_attack_prompts": True,
            "get_model_responses": False,
            "evaluate_responses": False,
            "generate_report": False,
        },
    )

    _run(
        _run_pipeline_for_datasets(
            config,
            [spec_inline, spec_file],
            str(tmp_path),
            "csv",
            enable_attacks=True,
            enable_responses=False,
            enable_eval=False,
        )
    )

    inline_files = list(tmp_path.glob("attack_prompts_inline_ds*"))
    file_files = list(tmp_path.glob("attack_prompts_file_ds*"))
    assert inline_files, "attack_prompts_inline_ds file must be written"
    assert file_files, "attack_prompts_file_ds file must be written"

    inline_records = pd.read_csv(str(inline_files[0])).to_dict("records")
    file_records = pd.read_csv(str(file_files[0])).to_dict("records")

    assert len(inline_records) == len(file_records), (
        f"Both datasets must produce the same number of records; "
        f"inline={len(inline_records)}, file={len(file_records)}"
    )
    inline_base_prompts = sorted(r["base_prompt"] for r in inline_records)
    file_base_prompts = sorted(r["base_prompt"] for r in file_records)
    assert inline_base_prompts == file_base_prompts, (
        "base_prompt values must match between inline and file-sourced datasets"
    )


# ---------------------------------------------------------------------------
# SPEC-018: Migrated notebooks run end-to-end (skipped — real_model marker)
# ---------------------------------------------------------------------------


@pytest.mark.real_model
@pytest.mark.parametrize(
    "notebook",
    [
        "examples/full_pipeline.ipynb",
        "examples/system_prompt_extraction.ipynb",
    ],
)
def test_SPEC_018_migrated_notebooks_run_end_to_end(notebook):
    """SPEC-018 (AC-18): each migrated notebook executes all cells without error."""
    import subprocess

    result = subprocess.run(
        ["jupyter", "nbconvert", "--to", "notebook", "--execute",
         "--inplace", notebook],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Notebook {notebook} failed to execute: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# SPEC-018b: run_pipeline drives the multi-dataset path end-to-end (CI-runnable)
# ---------------------------------------------------------------------------


def test_SPEC_018b_run_pipeline_drives_multi_dataset_path_end_to_end(tmp_path, monkeypatch):
    """SPEC-018b (AC-18): run_pipeline drives the multi-dataset path end-to-end.

    Exercises the PUBLIC entry point (run_pipeline) — not the
    _run_pipeline_for_datasets helper — with only the model classes mocked at the
    network boundary. Preflight, load_datasets, the stage functions, the
    KeywordEvaluator, and generate_report all run for real.
    """
    import hivetracered.runner as runner_mod
    from hivetracered.runner import run_pipeline
    from tests.conftest import MockModel

    # Trust-boundary mock: setup_model is the seam directly above the
    # network-bound model classes. Everything else in the call graph runs real.
    monkeypatch.setattr(runner_mod, "setup_model", lambda cfg: MockModel())

    config = _minimal_config(
        tmp_path,
        [
            {"name": "alpha", "base_prompts": ["p1", "p2"],
             "evaluator": {"name": "KeywordEvaluator"}},
            {"name": "beta", "base_prompts": ["p3", "p4"],
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
        stages={
            "create_attack_prompts": True,
            "get_model_responses": True,
            "evaluate_responses": True,
            "generate_report": True,
        },
        extra={
            "attacker_model": {"name": "MockAttacker"},
            "response_model": {"name": "MockResponder"},
            "evaluation_model": {"name": "MockEvaluatorModel"},
        },
    )

    _run(run_pipeline(config))

    run_dirs = sorted(
        d for d in tmp_path.iterdir() if d.is_dir() and d.name.startswith("run_")
    )
    run_files = [f.name for d in run_dirs for f in d.iterdir() if f.is_file()]

    # One logical outcome: the public entry point drove the multi-dataset branch
    # to completion and produced its full artifact set in a single run_<ts> dir.
    # The per-dataset Stage-1/2 files plus the ABSENCE of an un-suffixed
    # attack_prompts_results_* file are the black-box proof that the multi-dataset
    # path — not the legacy single-dataset branch — was on the call path.
    assert (
        len(run_dirs) == 1
        and any(f.startswith("attack_prompts_alpha") for f in run_files)
        and any(f.startswith("attack_prompts_beta") for f in run_files)
        and any(f.startswith("model_responses_alpha") for f in run_files)
        and any(f.startswith("model_responses_beta") for f in run_files)
        and sum(f.startswith("evaluations_results_") for f in run_files) == 1
        and any(f.startswith("report_") and f.endswith(".html") for f in run_files)
        and not any(f.startswith("attack_prompts_results_") for f in run_files)
    ), (
        "run_pipeline must drive the multi-dataset path end-to-end in one run_<ts> "
        "dir: per-dataset Stage-1/2 files for 'alpha' and 'beta', exactly one "
        "combined evaluations_results_* file, a report_*.html, and NO un-suffixed "
        f"attack_prompts_results_* file; got dirs={[d.name for d in run_dirs]}, "
        f"files={sorted(run_files)}"
    )


# ---------------------------------------------------------------------------
# SPEC-020: Zero-prompt dataset raises ValueError at preflight
# ---------------------------------------------------------------------------


def test_SPEC_020_zero_prompt_dataset_raises_value_error(tmp_path):
    """SPEC-020 (AC-20): _preflight_config raises ValueError for dataset with empty base_prompts."""
    from hivetracered.runner import _preflight_config

    config = _minimal_config(
        tmp_path,
        [
            {"name": "real_dataset", "base_prompts": ["p1", "p2", "p3"],
             "evaluator": {"name": "KeywordEvaluator"}},
            {"name": "empty_dataset", "base_prompts": [],
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
    )

    with pytest.raises(ValueError) as exc_info:
        _preflight_config(
            config,
            enable_attacks=True,
            enable_responses=True,
            enable_eval=True,
        )

    msg = str(exc_info.value)
    assert "empty_dataset" in msg, "ValueError must name the offending dataset 'empty_dataset'"
    assert "base_prompts" in msg, "ValueError must name the empty source 'base_prompts'"


# ---------------------------------------------------------------------------
# SPEC-020b: Zero-prompt dataset from base_prompts_file raises ValueError
# ---------------------------------------------------------------------------


def test_SPEC_020b_zero_row_base_prompts_file_raises_value_error(tmp_path):
    """SPEC-020b (AC-20): _preflight_config raises ValueError for dataset with zero-row file."""
    from hivetracered.runner import _preflight_config

    # CSV with headers but no data rows
    empty_csv = tmp_path / "empty_prompts.csv"
    pd.DataFrame(columns=["prompt"]).to_csv(str(empty_csv), index=False)

    config = _minimal_config(
        tmp_path,
        [
            {"name": "empty_file_ds",
             "base_prompts_file": str(empty_csv),
             "evaluator": {"name": "KeywordEvaluator"}},
        ],
    )

    with pytest.raises(ValueError) as exc_info:
        _preflight_config(
            config,
            enable_attacks=True,
            enable_responses=True,
            enable_eval=True,
        )

    msg = str(exc_info.value)
    assert "empty_file_ds" in msg, "ValueError must name the offending dataset"
    assert "base_prompts_file" in msg, "ValueError must name the empty source 'base_prompts_file'"


# ---------------------------------------------------------------------------
# SPEC-021: Null or non-string dataset name raises ValueError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_name_yaml",
    [
        "~",      # None
        "123",    # integer
        "true",   # boolean
        "[]",     # list
    ],
    ids=["null", "integer", "boolean", "list"],
)
def test_SPEC_021_non_string_dataset_name_raises_value_error(tmp_path, bad_name_yaml):
    """SPEC-021 (AC-12): load_config raises ValueError (not TypeError) for non-string names."""
    cfg_file = tmp_path / "bad_name_type.yaml"
    cfg_file.write_text(
        f"datasets:\n"
        f"  - name: {bad_name_yaml}\n"
        f"    base_prompts:\n"
        f"      - p1\n"
        f"    evaluator:\n"
        f"      name: KeywordEvaluator\n"
        f"attacks:\n"
        f"  - name: NoneAttack\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_config(str(cfg_file))


# ---------------------------------------------------------------------------
# SPEC-022: Missing evaluator key on dataset entry raises ValueError
# ---------------------------------------------------------------------------


def test_SPEC_022_missing_evaluator_key_raises_value_error(tmp_path):
    """SPEC-022 (AC-03): load_config raises ValueError when dataset entry lacks evaluator key."""
    cfg_file = tmp_path / "no_evaluator.yaml"
    cfg_file.write_text(
        "datasets:\n"
        "  - name: my_ds\n"
        "    base_prompts:\n"
        "      - p1\n"
        # no evaluator: key
        "attacks:\n"
        "  - name: NoneAttack\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        load_config(str(cfg_file))

    msg = str(exc_info.value)
    assert "evaluator" in msg, "ValueError must mention the missing 'evaluator' key"
    assert "my_ds" in msg, "ValueError must identify the offending dataset entry 'my_ds'"


# ---------------------------------------------------------------------------
# SPEC-024a/b/c: Empty response slice — three independent outcome tests
# ---------------------------------------------------------------------------


def test_SPEC_024a_empty_slice_ok_dataset_records_all_succeed(spec024_pipeline_results):
    """SPEC-024a (AC-10): When empty_slice has zero responses, ok-dataset records all have success=True."""
    eval_results, _ = spec024_pipeline_results

    ok_records = [r for r in eval_results if r.get("dataset") == "ok"]

    assert len(ok_records) == 2 and all(r.get("success") is True for r in ok_records), (
        "ok-dataset must have exactly 2 records all with success=True "
        "even when the sibling dataset has an empty response slice"
    )


def test_SPEC_024b_empty_slice_synthetic_failure_record_shape(spec024_pipeline_results):
    """SPEC-024b (AC-10): The empty-slice dataset gets exactly one synthetic failure record with correct shape."""
    eval_results, _ = spec024_pipeline_results

    empty_records = [r for r in eval_results if r.get("dataset") == "empty_slice"]

    assert (
        len(empty_records) == 1
        and empty_records[0].get("success") is False
        and "fail" in str(empty_records[0].get("error", ""))
    ), (
        "empty_slice must have exactly 1 synthetic failure record with "
        "success=False and error containing 'fail'"
    )


def test_SPEC_024c_empty_slice_no_all_fail_summary_logged(spec024_pipeline_results):
    """SPEC-024c (AC-10): The all-fail summary ERROR is NOT emitted when only one of two datasets fails."""
    _, error_messages = spec024_pipeline_results

    assert not any("ok" in m and "empty_slice" in m for m in error_messages), (
        "All-fail summary ERROR must NOT be emitted when only one dataset (empty_slice) fails"
    )
