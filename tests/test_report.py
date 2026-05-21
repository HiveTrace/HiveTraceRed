"""Tests for hivetracered.report.

Spec sources:
- Module surface: src/hivetracered/report.py
- build_html_report docstring at src/hivetracered/report.py:447-457
- pipeline.framework_mapping.get_framework_mappings docstring (level-2)
- pipeline.mitigations.get_prioritized_mitigations docstring (level-2)
- de-facto contract from caller hivetracered/runner.py (`generate_report`)

Tests focus on the public surface of report.py:
- pure data-shaping helpers operating on tiny in-memory DataFrames,
- chart-builder helpers that emit plotly figures rendered to HTML,
- the build_html_report combiner,
- the `main` CLI entry point with tmp_path I/O.
"""

from __future__ import annotations

import json
import sys
from typing import Any
import numpy as np
import pandas as pd
import pytest

from hivetracered import report
from hivetracered.pipeline.framework_mapping import FRAMEWORKS
from hivetracered.report import (
    SUCCESS_RATE,
    BLOCK_RATE,
    _asr_max_injection,
    _asr_none_attack,
    _attack_detailed_html,
    _basic_rates,
    _best_attack,
    _bfmt,
    _build_attack_type_html,
    _build_attacks_html,
    _expand_evaluation,
    _explorer_row_html,
    _explorer_table_html,
    _framework_categories,
    _merge_mappings,
    _per_type_stats,
    _read_dataframe,
    _safe_get,
    _sample_block_html,
    _samples_html,
    _vulnerable_attack_types,
    _vulnerable_prompts,
    build_html_report,
    calculate_metrics,
    create_charts,
    generate_data_tables,
    get_chart_style,
    load_data,
    main,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """A small representative DataFrame with all columns the helpers expect.

    Rows hand-chosen to exercise:
    - successes vs failures,
    - blocked vs not blocked,
    - one error row,
    - two distinct attack_names ("NoneAttack" and "ContextSwitch"),
    - two distinct attack_types,
    - response strings of different lengths,
    - did_answer = True / False mix,
    - a base_prompt that succeeds in at least one attack.
    """
    return pd.DataFrame(
        [
            {
                "model": "test-model",
                "category": "Harmful Content Generation",
                "subcategory": "Phishing",
                "attack_type": "context_switching",
                "attack_name": "ContextSwitch",
                "base_prompt": "P1",
                "prompt": "ATTACK1",
                "response": "long response text " * 5,  # length > short
                "success": True,
                "is_blocked": False,
                "did_answer": True,
                "error": "",
            },
            {
                "model": "test-model",
                "category": "Harmful Content Generation",
                "subcategory": "Phishing",
                "attack_type": "context_switching",
                "attack_name": "ContextSwitch",
                "base_prompt": "P2",
                "prompt": "ATTACK2",
                "response": "no",
                "success": False,
                "is_blocked": True,
                "did_answer": False,
                "error": "",
            },
            {
                "model": "test-model",
                "category": "Harmful Content Generation",
                "subcategory": "Phishing",
                "attack_type": "simple_instructions",
                "attack_name": "NoneAttack",
                "base_prompt": "P1",
                "prompt": "P1",
                "response": "answer",
                "success": False,
                "is_blocked": False,
                "did_answer": True,
                "error": "boom",
            },
            {
                "model": "test-model",
                "category": "Harmful Content Generation",
                "subcategory": "Phishing",
                "attack_type": "simple_instructions",
                "attack_name": "NoneAttack",
                "base_prompt": "P2",
                "prompt": "P2",
                "response": "answer here",
                "success": True,
                "is_blocked": False,
                "did_answer": True,
                "error": "",
            },
        ]
    )


@pytest.fixture
def sample_df_with_response_length(sample_df: pd.DataFrame) -> pd.DataFrame:
    df = sample_df.copy()
    df["response_length"] = df["response"].str.len()
    return df


# ── get_chart_style ─────────────────────────────────────────────────


def test_get_chart_style_returns_required_plotly_layout_keys():
    style = get_chart_style()

    assert {"paper_bgcolor", "plot_bgcolor", "font", "xaxis", "yaxis"} <= set(style)


# ── _read_dataframe ─────────────────────────────────────────────────


def test_read_dataframe_reads_csv_extension(tmp_path):
    p = tmp_path / "data.csv"
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_csv(p, index=False)

    out = _read_dataframe(str(p))

    assert list(out.columns) == ["a", "b"]
    assert out["a"].tolist() == [1, 2]


def test_read_dataframe_reads_parquet_extension(tmp_path):
    p = tmp_path / "data.parquet"
    pd.DataFrame({"a": [1, 2]}).to_parquet(p)

    out = _read_dataframe(str(p))

    assert out["a"].tolist() == [1, 2]


def test_read_dataframe_reads_xlsx_extension(tmp_path):
    p = tmp_path / "data.xlsx"
    pd.DataFrame({"a": [1, 2]}).to_excel(p, index=False)

    out = _read_dataframe(str(p))

    assert out["a"].tolist() == [1, 2]


def test_read_dataframe_unknown_extension_falls_back_to_csv(tmp_path):
    # Implementation default for any non-parquet/xlsx/xls is read_csv.
    p = tmp_path / "data.txt"
    p.write_text("x,y\n1,2\n", encoding="utf-8")

    out = _read_dataframe(str(p))

    assert out["x"].tolist() == [1]


# ── _safe_get ───────────────────────────────────────────────────────


def test_safe_get_returns_value_for_dict_input():
    assert _safe_get({"k": "v"}, "k") == "v"


def test_safe_get_returns_default_when_dict_missing_key():
    assert _safe_get({"other": 1}, "missing", default="dflt") == "dflt"


def test_safe_get_parses_json_string_and_extracts_key():
    assert _safe_get('{"is_harmful": true}', "is_harmful") is True


def test_safe_get_returns_default_for_invalid_json_string():
    assert _safe_get("not json", "any") == "unknown"


def test_safe_get_returns_default_for_non_dict_json_value():
    # JSON parses to int — not a dict — so default returns.
    assert _safe_get("123", "any", default="fallback") == "fallback"


# ── _expand_evaluation ──────────────────────────────────────────────


def test_expand_evaluation_extracts_three_keys_from_dict_column():
    df = pd.DataFrame(
        {"evaluation": [{"is_harmful": True, "did_answer": False, "should_block": True}]}
    )

    _expand_evaluation(df)

    # bool() round-trips for both python bool and numpy.bool_ from CSV.
    assert bool(df["is_harmful"].iloc[0]) is True
    assert bool(df["did_answer"].iloc[0]) is False
    assert bool(df["should_block"].iloc[0]) is True


def test_expand_evaluation_uses_unknown_default_when_keys_missing():
    df = pd.DataFrame({"evaluation": [{}]})

    _expand_evaluation(df)

    assert df["is_harmful"].iloc[0] == "unknown"


# ── load_data ───────────────────────────────────────────────────────


def test_load_data_returns_empty_dataframe_when_file_missing(tmp_path, capsys):
    missing = tmp_path / "nope.csv"

    out = load_data(str(missing))

    captured = capsys.readouterr()
    assert out.empty
    assert "Error loading data" in captured.out


def test_load_data_casts_success_and_is_blocked_to_bool(tmp_path):
    p = tmp_path / "d.csv"
    pd.DataFrame(
        {"success": [1, 0], "is_blocked": [0, 1], "response": ["a", "bb"]}
    ).to_csv(p, index=False)

    out = load_data(str(p))

    assert out["success"].dtype == bool
    assert out["is_blocked"].dtype == bool
    # response_length added when response col exists.
    assert out["response_length"].tolist() == [1, 2]


def test_load_data_expands_evaluation_column_when_present(tmp_path):
    p = tmp_path / "d.csv"
    df_in = pd.DataFrame(
        {"evaluation": [json.dumps({"is_harmful": True, "did_answer": False, "should_block": True})]}
    )
    df_in.to_csv(p, index=False)

    out = load_data(str(p))

    # Stored as JSON str in CSV; _safe_get parses it.
    assert bool(out["is_harmful"].iloc[0]) is True
    assert bool(out["did_answer"].iloc[0]) is False


# ── _basic_rates ────────────────────────────────────────────────────


def test_basic_rates_for_empty_dataframe_returns_zeroes():
    total, sr, br, er = _basic_rates(pd.DataFrame())

    assert (total, sr, br, er) == (0, 0.0, 0.0, 0.0)


def test_basic_rates_computes_percentages_for_sample(sample_df):
    total, sr, br, er = _basic_rates(sample_df)

    # 4 rows, 2 successes => 50.0%, 1 blocked => 25.0%, 1 error => 25.0%.
    assert total == 4  # = len(sample_df)
    assert sr == pytest.approx(50.0)
    assert br == pytest.approx(25.0)
    assert er == pytest.approx(25.0)


# ── _best_attack ────────────────────────────────────────────────────


def test_best_attack_uses_strict_max_when_clear_winner():
    df = pd.DataFrame(
        {
            "attack_name": ["A", "A", "B", "B"],
            "success": [True, True, False, False],
        }
    )

    name, rate = _best_attack(df)

    assert name == "A"
    assert rate == pytest.approx(100.0)  # = 2/2 * 100


# ── _vulnerable_prompts ─────────────────────────────────────────────


def test_vulnerable_prompts_returns_zeros_for_empty_dataframe():
    assert _vulnerable_prompts(pd.DataFrame()) == (0, 0, 0.0)


def test_vulnerable_prompts_counts_unique_base_prompts_with_success(sample_df):
    # P1 succeeded (in ContextSwitch), P2 succeeded (in NoneAttack).
    vuln, total, rate = _vulnerable_prompts(sample_df)

    assert vuln == 2  # = 2 unique base_prompt values where success=True
    assert total == 2  # = nunique(base_prompt)
    assert rate == pytest.approx(100.0)


# ── _merge_mappings + _framework_categories ─────────────────────────


def test_merge_mappings_uses_attack_type_when_columns_present(sample_df):
    merged = _merge_mappings(
        sample_df,
        base_category="Harmful Content Generation",
        subcategories=None,
    )

    # OWASP LLM01 (Prompt Injection) is mapped to every attack type by spec.
    assert "OWASP_LLM_TOP_10" in merged
    assert "LLM01" in merged["OWASP_LLM_TOP_10"]


def test_framework_categories_formats_id_colon_name_strings_sorted():
    # Use OWASP LLM01 + LLM02 in a deterministic order.
    merged = {"OWASP_LLM_TOP_10": {"LLM02", "LLM01"}}

    out = _framework_categories(merged)

    expected = [
        "LLM01: " + FRAMEWORKS["OWASP_LLM_TOP_10"]["categories"]["LLM01"]["name"],
        "LLM02: " + FRAMEWORKS["OWASP_LLM_TOP_10"]["categories"]["LLM02"]["name"],
    ]
    assert out["OWASP_LLM_TOP_10"] == sorted(expected)


def test_framework_categories_skips_unknown_category_ids():
    merged = {"OWASP_LLM_TOP_10": {"LLM01", "DOES_NOT_EXIST"}}

    out = _framework_categories(merged)

    assert all("LLM01" in c or "DOES_NOT_EXIST" not in c for c in out["OWASP_LLM_TOP_10"])
    assert len(out["OWASP_LLM_TOP_10"]) == 1


# ── _asr_none_attack / _asr_max_injection ───────────────────────────


def test_asr_none_attack_returns_zero_when_no_none_attack_rows():
    df = pd.DataFrame({"attack_name": ["X"], "success": [True]})

    assert _asr_none_attack(df) == 0.0


def test_asr_none_attack_returns_mean_for_none_attack(sample_df):
    # 1 success out of 2 NoneAttack rows = 50%.
    assert _asr_none_attack(sample_df) == pytest.approx(50.0)


def test_asr_max_injection_returns_dash_when_no_injection_rows():
    df = pd.DataFrame({"attack_name": ["NoneAttack"], "success": [True]})

    rate, name = _asr_max_injection(df)

    assert rate == 0.0
    assert name == "-"


def test_asr_max_injection_returns_max_among_non_none_attacks(sample_df):
    rate, name = _asr_max_injection(sample_df)

    # Only injection row in sample is "ContextSwitch" with 1/2 = 50%.
    assert name == "ContextSwitch"
    assert rate == pytest.approx(50.0)


# ── _vulnerable_attack_types ────────────────────────────────────────


def test_vulnerable_attack_types_returns_empty_list_for_empty_dataframe():
    assert _vulnerable_attack_types(pd.DataFrame()) == []


def test_vulnerable_attack_types_returns_only_types_with_positive_success(sample_df):
    out = _vulnerable_attack_types(sample_df)

    # Both types have at least one success: context_switching, simple_instructions.
    assert out == sorted(["context_switching", "simple_instructions"])


def test_vulnerable_attack_types_excludes_types_with_zero_success_rate():
    df = pd.DataFrame(
        {
            "attack_type": ["good", "good", "bad", "bad"],
            "success": [True, False, False, False],
        }
    )

    assert _vulnerable_attack_types(df) == ["good"]


# ── calculate_metrics ───────────────────────────────────────────────


def test_calculate_metrics_handles_empty_dataframe_gracefully():
    out = calculate_metrics(pd.DataFrame())

    # Spec: empty df produces structurally complete dict with zero metrics.
    assert out["total_tests"] == 0
    assert out["success_rate"] == 0.0
    assert out["model_name"] == "Unknown"
    assert out["best_attack_name"] == "-"
    assert out["prioritized_mitigations"] == []  # = no vulnerable_attack_types


def test_calculate_metrics_aggregates_sample_dataframe(sample_df):
    out = calculate_metrics(sample_df)

    assert out["total_tests"] == 4  # = len(sample_df)
    assert out["model_name"] == "test-model"
    assert out["n_attack_types"] == 2  # = ContextSwitch type + simple_instructions type
    assert out["n_attacks"] == 2  # = ContextSwitch + NoneAttack
    assert out["success_rate"] == pytest.approx(50.0)
    assert out["base_category"] == "Harmful Content Generation"
    # Mitigations are produced because both types have successes.
    assert isinstance(out["prioritized_mitigations"], list)
    assert len(out["prioritized_mitigations"]) > 0
    assert "framework_mappings" in out
    assert "framework_categories" in out


# ── _per_type_stats ─────────────────────────────────────────────────


def test_per_type_stats_computes_unique_prompt_success_rate(sample_df):
    out = _per_type_stats(sample_df)

    # Each attack_type has 2 unique prompts; each has 1 successful unique prompt.
    rates = {entry["attack_type"]: entry[SUCCESS_RATE] for entry in out}
    assert rates["context_switching"] == pytest.approx(0.5)
    assert rates["simple_instructions"] == pytest.approx(0.5)


def test_per_type_stats_with_block_rate_returns_percent_and_block(sample_df):
    out = _per_type_stats(sample_df, include_block_rate=True)

    by_type = {entry["attack_type"]: entry for entry in out}
    # In include_block_rate mode, success rate is multiplied by 100.
    assert by_type["context_switching"][SUCCESS_RATE] == pytest.approx(50.0)
    # context_switching: 1 of 2 blocked = 50%.
    assert by_type["context_switching"][BLOCK_RATE] == pytest.approx(50.0)
    # simple_instructions: 0 of 2 blocked = 0%.
    assert by_type["simple_instructions"][BLOCK_RATE] == pytest.approx(0.0)


# ── chart-builder helpers ───────────────────────────────────────────




def test_build_attack_type_html_returns_no_data_message_when_all_below_threshold():
    # success rates 0% < threshold 3%.
    df = pd.DataFrame(
        {
            "attack_type": ["A", "A"],
            "success": [False, False],
            "is_blocked": [False, False],
            "attack_name": ["x", "x"],
            "base_prompt": ["p1", "p2"],
        }
    )

    out = _build_attack_type_html(df)

    assert "No attack types" in out


def test_build_attacks_html_returns_no_data_message_when_below_threshold():
    df = pd.DataFrame(
        {
            "attack_name": ["A", "A"],
            "success": [False, False],
            "is_blocked": [False, False],
        }
    )

    out = _build_attacks_html(df)

    assert "No individual attacks" in out


# ── create_charts ───────────────────────────────────────────────────


def test_create_charts_returns_seven_keyed_dict_for_sample(sample_df_with_response_length):
    out = create_charts(sample_df_with_response_length)

    expected_keys = {
        "fig_top_types_html",
        "fig_top_attacks_html",
        "fig_attack_type_html",
        "fig_attacks_html",
        "fig_length_html",
        "fig_avg_length_html",
        "fig_answer_html",
    }
    assert set(out.keys()) == expected_keys
    # Each individual chart builder must produce non-empty HTML for valid data.
    for key in expected_keys:
        assert "<div" in out[key], f"{key} returned empty/non-HTML for sample data"


def test_create_charts_returns_empty_strings_for_empty_dataframe():
    out = create_charts(pd.DataFrame())

    # All builders short-circuit to empty strings on missing columns.
    assert all(v == "" for v in out.values())


# ── _bfmt / _explorer_row_html / _explorer_table_html ───────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, "✅"),
        (False, "❌"),
        (np.bool_(True), "✅"),
        (np.bool_(False), "❌"),
        ("hello", "hello"),
    ],
    ids=["py-true", "py-false", "np-true", "np-false", "str"],
)
def test_bfmt_formats_booleans_with_emoji_and_others_via_str(value, expected):
    assert _bfmt(value) == expected


def test_explorer_row_html_emits_data_attributes_and_cells():
    row = pd.Series(
        {
            "attack_type": "context_switching",
            "success": True,
            "is_blocked": False,
            "attack_name": "X",
        }
    )

    html = _explorer_row_html(row, ["attack_name", "attack_type", "success", "is_blocked"])

    assert 'data-attack-type="context_switching"' in html
    assert 'data-success="true"' in html
    assert 'data-blocked="false"' in html
    assert "<td>X</td>" in html
    assert "<td>✅</td>" in html  # success bool
    assert "<td>❌</td>" in html  # is_blocked bool


def test_explorer_table_html_renders_rows_for_each_record(sample_df):
    cols = ["attack_name", "attack_type", "success", "is_blocked"]

    html = _explorer_table_html(sample_df, cols)

    assert html.count("<tr ") == len(sample_df)
    # Header per column.
    for c in cols:
        assert f"<th>{c}</th>" in html


def test_explorer_table_html_with_empty_columns_renders_empty_table(sample_df):
    html = _explorer_table_html(sample_df, [])

    assert "<table" in html
    # No <tr ...> rows because display_columns is empty.
    assert "<tr " not in html


# ── _sample_block_html / _samples_html ──────────────────────────────


def test_sample_block_html_includes_attack_name_and_response_text():
    row = {
        "attack_name": "MyAttack",
        "success": True,
        "base_prompt": "BASE",
        "prompt": "ATK",
        "response": "RESP",
    }

    html = _sample_block_html(row)

    assert "MyAttack" in html
    assert "✅ Success" in html
    assert "BASE" in html and "ATK" in html and "RESP" in html


def test_sample_block_html_marks_failure_when_success_false():
    html = _sample_block_html(
        {"attack_name": "A", "success": False, "base_prompt": "b", "prompt": "p", "response": "r"}
    )

    assert "❌ Failed" in html


def test_samples_html_uses_full_df_when_no_successes():
    df = pd.DataFrame(
        {
            "attack_name": ["A", "B"],
            "success": [False, False],
            "base_prompt": ["bp1", "bp2"],
            "prompt": ["p1", "p2"],
            "response": ["r1", "r2"],
        }
    )

    out = _samples_html(df)

    # Falls back to full df when no successes; deterministic via random_state.
    assert "❌ Failed" in out


def test_samples_html_emits_one_block_per_sample_for_small_df(sample_df):
    out = _samples_html(sample_df)

    # Both successes < 5; sample size = min(5, n_successes) = 2.
    assert out.count("<details") == 2


# ── _attack_detailed_html ───────────────────────────────────────────


def test_attack_detailed_html_renders_table_with_percentage_strings(sample_df):
    out = _attack_detailed_html(sample_df)

    # Pandas to_html output for the percentage columns.
    assert "<table" in out
    assert "%</td>" in out  # success/block rate strings end with %
    assert "ContextSwitch" in out and "NoneAttack" in out


# ── generate_data_tables ────────────────────────────────────────────


def test_generate_data_tables_returns_expected_keys_for_sample(sample_df):
    out = generate_data_tables(sample_df)

    assert set(out.keys()) == {
        "attack_detailed_html",
        "explorer_table_html",
        "samples_html",
        "display_columns",
    }
    assert out["display_columns"] == ["attack_name", "attack_type", "success", "is_blocked"]


def test_generate_data_tables_handles_empty_dataframe():
    out = generate_data_tables(pd.DataFrame())

    assert out["attack_detailed_html"] == ""
    assert out["display_columns"] == []
    assert out["samples_html"] == ""


# ── build_html_report ───────────────────────────────────────────────


def _minimal_metrics() -> dict[str, Any]:
    """Minimum keys build_html_report reads from `metrics`."""
    return {
        "total_tests": 0,
        "success_rate": 0.0,
        "blocked_rate": 0.0,
        "error_rate": 0.0,
        "best_attack_name": "-",
        "best_attack_rate": 0.0,
        "vulnerable_prompts": 0,
        "total_prompts": 0,
        "vulnerable_prompts_rate": 0.0,
        "model_name": "Unknown",
        "n_attack_types": 0,
        "n_attacks": 0,
        "base_category": "Unknown",
        "framework_categories": {},
        "asr_none_attack": 0.0,
        "asr_max_attack": 0.0,
        "best_attack_name_detailed": "-",
        "prioritized_mitigations": [],
    }


def _empty_charts() -> dict[str, str]:
    return {
        "fig_top_types_html": "",
        "fig_top_attacks_html": "",
        "fig_attack_type_html": "",
        "fig_attacks_html": "",
        "fig_length_html": "",
        "fig_avg_length_html": "",
        "fig_answer_html": "",
    }


def _empty_data_tables() -> dict[str, Any]:
    return {
        "attack_detailed_html": "",
        "explorer_table_html": "",
        "samples_html": "",
        "display_columns": [],
    }


def test_build_html_report_emits_doctype_and_required_tabs_for_empty_input():
    html = build_html_report(pd.DataFrame(), _minimal_metrics(), _empty_charts(), _empty_data_tables())

    assert "<!DOCTYPE html>" in html
    # Five tabs as documented in the body builder.
    for tab_id in ("tab1", "tab2", "tab3", "tab4", "tab5"):
        assert f'id="{tab_id}"' in html
    assert "Executive Summary" in html
    assert "Mitigation Recommendations" in html
    # Empty mitigations list → "no vulnerable types" message (merged from
    # test_build_html_report_includes_no_mitigations_message_when_list_empty).
    assert "No vulnerable attack types detected" in html


def test_build_html_report_renders_mitigation_items_when_provided():
    metrics = _minimal_metrics()
    metrics["prioritized_mitigations"] = [
        {"mitigation": "MyMit", "covers": 2, "total": 4, "attack_types": ["a", "b"]},
    ]

    html = build_html_report(pd.DataFrame(), metrics, _empty_charts(), _empty_data_tables())

    assert "MyMit" in html
    assert "Prioritized Mitigations" in html


def test_build_html_report_renders_framework_badges_for_known_frameworks():
    metrics = _minimal_metrics()
    metrics["framework_categories"] = {
        "OWASP_LLM_TOP_10": ["LLM01: Prompt Injection"],
        "MITRE_ATLAS": ["AML.TA0002: Reconnaissance"],
    }

    html = build_html_report(pd.DataFrame(), metrics, _empty_charts(), _empty_data_tables())

    assert "OWASP LLM Top 10" in html
    assert "MITRE ATLAS" in html
    assert "LLM01: Prompt Injection" in html


def test_build_html_report_includes_record_count_and_model_in_footer(sample_df):
    metrics = _minimal_metrics()
    metrics["model_name"] = "MyModel"
    metrics["n_attack_types"] = 3
    metrics["n_attacks"] = 5

    html = build_html_report(sample_df, metrics, _empty_charts(), _empty_data_tables())

    assert f"Loaded {len(sample_df)} records" in html
    assert "MyModel" in html
    assert "<strong>Attack Types:</strong> 3" in html
    assert "<strong>Total Attacks:</strong> 5" in html


# ── main (CLI) ──────────────────────────────────────────────────────


def test_main_writes_html_report_to_output_path(tmp_path, monkeypatch, capsys):
    # Arrange: create a tiny CSV the load_data path can ingest.
    data_csv = tmp_path / "df.csv"
    pd.DataFrame(
        {
            "model": ["m"],
            "attack_type": ["context_switching"],
            "attack_name": ["X"],
            "category": ["Harmful Content Generation"],
            "subcategory": ["Phishing"],
            "base_prompt": ["bp"],
            "prompt": ["p"],
            "response": ["r"],
            "success": [True],
            "is_blocked": [False],
            "did_answer": [True],
            "error": [""],
        }
    ).to_csv(data_csv, index=False)

    out_path = tmp_path / "report.html"
    monkeypatch.setattr(sys, "argv", ["report", "--data-file", str(data_csv), "--output", str(out_path)])

    main()

    captured = capsys.readouterr()
    assert out_path.exists()
    contents = out_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in contents
    assert f"Report generated: {out_path}" in captured.out


def test_main_reports_empty_when_data_file_missing(tmp_path, monkeypatch, capsys):
    # load_data prints an error and returns empty DataFrame; main warns and writes report.
    out_path = tmp_path / "out.html"
    monkeypatch.setattr(
        sys,
        "argv",
        ["report", "--data-file", str(tmp_path / "missing.csv"), "--output", str(out_path)],
    )

    main()

    captured = capsys.readouterr()
    assert "Warning: No data loaded" in captured.out
    # Even with empty data, an HTML file is produced.
    assert out_path.exists()


def test_main_handles_unexpected_exception_and_prints_traceback(tmp_path, monkeypatch, capsys):
    # Force load_data to raise unexpectedly to exercise the except branch.
    def _boom(_path):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(report, "load_data", _boom)
    monkeypatch.setattr(
        sys,
        "argv",
        ["report", "--data-file", str(tmp_path / "x.csv"), "--output", str(tmp_path / "y.html")],
    )

    main()  # should NOT raise; the except branch returns None.

    captured = capsys.readouterr()
    assert "Error processing data" in captured.out
    assert "kaboom" in captured.out or "kaboom" in captured.err
