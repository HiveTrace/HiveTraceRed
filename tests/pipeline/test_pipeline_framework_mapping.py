"""Tests for hivetracered.pipeline.framework_mapping."""

from __future__ import annotations

import pytest

from hivetracered.pipeline.framework_mapping import (
    ATTACK_TYPE_FRAMEWORK_MAP,
    FRAMEWORKS,
    get_all_frameworks,
    get_attack_types_for_category,
    get_dataset_categories_for_framework_category,
    get_framework_coverage,
    get_framework_mappings,
)


# ── get_framework_mappings ──────────────────────────────────────────────


def test_get_framework_mappings_no_args_returns_empty_dict():
    result = get_framework_mappings()

    assert result == {}


def test_get_framework_mappings_roleplay_returns_prompt_injection_base():
    # Spec from module docstring: "Attack types -> always LLM01 (Prompt Injection)"
    # plus _PROMPT_INJECTION_BASE definition.
    expected_owasp = {"LLM01"}
    expected_atlas = {"AML.TA0005", "AML.TA0012", "AML.TA0007"}
    expected_fstek = {"п.61а", "п.61б", "п.66"}

    result = get_framework_mappings(attack_type="roleplay")

    assert result["OWASP_LLM_TOP_10"] == expected_owasp
    assert result["MITRE_ATLAS"] == expected_atlas
    assert result["FSTEK_117"] == expected_fstek


def test_get_framework_mappings_none_attack_overrides_attack_type():
    # NoneAttack mapping is empty per ATTACK_NAME_FRAMEWORK_MAP; takes priority.
    result = get_framework_mappings(attack_name="NoneAttack", attack_type="roleplay")

    assert result["OWASP_LLM_TOP_10"] == set()
    assert result["MITRE_ATLAS"] == set()
    assert result["FSTEK_117"] == set()


def test_get_framework_mappings_base_category_merges_additively():
    # roleplay -> {LLM01}; "Harmful Content Generation" adds {LLM04}.
    expected_owasp = {"LLM01", "LLM04"}

    result = get_framework_mappings(
        attack_type="roleplay", base_category="Harmful Content Generation",
    )

    assert result["OWASP_LLM_TOP_10"] == expected_owasp


def test_get_framework_mappings_subcategory_overlay_adds_categories():
    # "System Prompt Extraction" subcategory adds LLM07 to LLM01 from roleplay.
    expected_owasp = {"LLM01", "LLM07"}

    result = get_framework_mappings(
        attack_type="roleplay", subcategories=["System Prompt Extraction"],
    )

    assert result["OWASP_LLM_TOP_10"] == expected_owasp


@pytest.mark.parametrize(
    ("kwargs",),
    [
        ({"attack_type": "definitely_not_a_real_type"},),
        ({"attack_name": "DefinitelyNotARealAttack"},),
        ({"base_category": "DefinitelyNotARealCategory"},),
        ({"subcategories": ["DefinitelyNotARealSub"]},),
    ],
    ids=["unknown-type", "unknown-name", "unknown-base", "unknown-sub"],
)
def test_get_framework_mappings_unknown_names_yield_no_entries(kwargs):
    result = get_framework_mappings(**kwargs)

    assert result == {}


# ── get_framework_coverage ──────────────────────────────────────────────


def test_get_framework_coverage_empty_input_zero_covered_zero_pct():
    expected_owasp_total = len(FRAMEWORKS["OWASP_LLM_TOP_10"]["categories"])  # = 10

    result = get_framework_coverage({})

    assert result["OWASP_LLM_TOP_10"]["covered"] == 0
    assert result["OWASP_LLM_TOP_10"]["coverage_pct"] == 0.0
    assert result["OWASP_LLM_TOP_10"]["total"] == expected_owasp_total


def test_get_framework_coverage_full_llm01_covers_only_owasp():
    # Single category covered out of 10 -> 1/10 == 10.0 %.
    owasp_total = len(FRAMEWORKS["OWASP_LLM_TOP_10"]["categories"])  # = 10
    expected_pct = round(1 / owasp_total * 100, 1)  # = 10.0

    result = get_framework_coverage({"OWASP_LLM_TOP_10": {"LLM01"}})

    assert result["OWASP_LLM_TOP_10"]["covered"] == 1
    assert result["OWASP_LLM_TOP_10"]["covered_list"] == ["LLM01"]
    assert result["OWASP_LLM_TOP_10"]["coverage_pct"] == expected_pct
    assert result["MITRE_ATLAS"]["covered"] == 0


def test_get_framework_coverage_spurious_category_is_ignored():
    result = get_framework_coverage({"OWASP_LLM_TOP_10": {"NOT_A_REAL_CATEGORY"}})

    assert result["OWASP_LLM_TOP_10"]["covered"] == 0
    assert result["OWASP_LLM_TOP_10"]["covered_list"] == []


def test_get_framework_coverage_pct_rounded_to_one_decimal():
    # 2 / 10 = 20.0 (already 1-decimal); 3 / 10 = 30.0; pick 1/16 (MITRE) for non-trivial round.
    atlas_total = len(FRAMEWORKS["MITRE_ATLAS"]["categories"])  # = 16
    expected_pct = round(1 / atlas_total * 100, 1)  # = 6.2

    result = get_framework_coverage({"MITRE_ATLAS": {"AML.TA0002"}})

    assert result["MITRE_ATLAS"]["coverage_pct"] == expected_pct


# ── get_attack_types_for_category ───────────────────────────────────────


def test_get_attack_types_for_category_llm01_returns_all_eleven_sorted():
    # All 11 attack types in ATTACK_TYPE_FRAMEWORK_MAP map to LLM01.
    expected = sorted(ATTACK_TYPE_FRAMEWORK_MAP.keys())  # = 11 entries

    result = get_attack_types_for_category("OWASP_LLM_TOP_10", "LLM01")

    assert result == expected
    assert len(result) == len(ATTACK_TYPE_FRAMEWORK_MAP)


def test_get_attack_types_for_category_unknown_category_returns_empty():
    result = get_attack_types_for_category("OWASP_LLM_TOP_10", "LLM07")

    assert result == []


# ── get_dataset_categories_for_framework_category ───────────────────────


def test_get_dataset_categories_for_framework_category_llm02_returns_internal_info():
    # Per BASE_CATEGORY_FRAMEWORK_MAP: only "Internal Information Exposure" maps to LLM02.
    expected = ["Internal Information Exposure"]

    result = get_dataset_categories_for_framework_category("OWASP_LLM_TOP_10", "LLM02")

    assert result == expected


# ── get_all_frameworks ──────────────────────────────────────────────────


def test_get_all_frameworks_contains_three_top_level_keys():
    expected_keys = {"OWASP_LLM_TOP_10", "MITRE_ATLAS", "FSTEK_117"}

    result = get_all_frameworks()

    assert set(result.keys()) == expected_keys
