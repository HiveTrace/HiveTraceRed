"""Tests for hivetracered.config.load_config.

Spec sources:
- Module docstring at src/hivetracered/config.py:1-8
- load_config docstring at src/hivetracered/config.py:53-62 (Raises FileNotFoundError
  on missing path, ValueError on empty/non-mapping content; warns on unknown keys
  at top level / under 'stages' / under 'report' but preserves them).
"""

from __future__ import annotations

import logging

import pytest

from hivetracered.config import load_config


# ── error paths ───────────────────────────────────────────────────────


def test_load_config_missing_file_raises_file_not_found(tmp_path):
    missing_path = tmp_path / "nope.yaml"  # never created

    with pytest.raises(FileNotFoundError, match=r"Config file not found"):
        load_config(str(missing_path))


def test_load_config_empty_file_raises_value_error(tmp_path):
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match=r"is empty"):
        load_config(str(empty_file))


def test_load_config_non_mapping_raises_value_error(tmp_path):
    # YAML list at top level → load_config rejects (must be a mapping).
    cfg_file = tmp_path / "bad.yaml"
    cfg_file.write_text("- a\n- b\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"must be a mapping, got list"):
        load_config(str(cfg_file))


# ── happy paths ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("yaml_body", "expected_result", "where_marker", "unknown_key"),
    [
        # top-level: 'evaluat_responses' is a typo of 'evaluate_responses'
        (
            "evaluat_responses: true\n",
            {"evaluat_responses": True},
            "top level",
            "evaluat_responses",
        ),
        # under 'stages':
        (
            "stages:\n  evaluat_responses: true\n",
            {"stages": {"evaluat_responses": True}},
            "'stages'",
            "evaluat_responses",
        ),
        # under 'report': 'output_filenam' typo of 'output_filename'
        (
            "report:\n  output_filenam: report.html\n",
            {"report": {"output_filenam": "report.html"}},
            "'report'",
            "output_filenam",
        ),
    ],
    ids=["top_level", "stages", "report"],
)
def test_load_config_unknown_key_warns_but_returns(
    tmp_path, caplog, yaml_body, expected_result, where_marker, unknown_key
):
    cfg_file = tmp_path / "typo.yaml"
    cfg_file.write_text(yaml_body, encoding="utf-8")
    caplog.set_level(logging.WARNING, logger="hivetracered.config")

    result = load_config(str(cfg_file))

    assert result == expected_result  # = preserved verbatim
    warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(where_marker in m and unknown_key in m for m in warning_messages)


def test_load_config_only_known_keys_emits_no_warning(tmp_path, caplog):
    cfg_file = tmp_path / "clean.yaml"
    cfg_file.write_text(
        "stages:\n"
        "  create_attack_prompts: true\n"
        "  evaluate_responses: false\n"
        "report:\n"
        "  output_filename: report.html\n"
        "  include_in_run_dir: true\n"
        "output_dir: out\n",
        encoding="utf-8",
    )
    caplog.set_level(logging.WARNING, logger="hivetracered.config")

    result = load_config(str(cfg_file))

    assert "stages" in result and "report" in result
    warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warning_messages == []  # = no unknown-key warnings expected
