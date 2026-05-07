"""Tests for hivetracered.pipeline.mitigations."""

from __future__ import annotations


from hivetracered.pipeline.mitigations import (
    SYSTEM_PROMPT_HARDENING,
    get_mitigations_for_type,
    get_prioritized_mitigations,
)


# ── get_mitigations_for_type ────────────────────────────────────────────


def test_get_mitigations_for_type_roleplay_returns_four_items_with_hardening():
    expected_count = 4  # = 4 entries in ATTACK_MITIGATIONS["roleplay"]

    result = get_mitigations_for_type("roleplay")

    assert len(result) == expected_count
    assert SYSTEM_PROMPT_HARDENING in result


def test_get_mitigations_for_type_unknown_returns_empty_list():
    result = get_mitigations_for_type("definitely_not_a_real_type")

    assert result == []


# ── get_prioritized_mitigations ─────────────────────────────────────────


def test_get_prioritized_mitigations_empty_input_returns_empty_list():
    result = get_prioritized_mitigations([])

    assert result == []


def test_get_prioritized_mitigations_single_type_each_covers_one():
    expected_keys = {"mitigation", "covers", "total", "attack_types"}

    result = get_prioritized_mitigations(["roleplay"])

    expected_total = 1  # single attack type
    expected_count = len(get_mitigations_for_type("roleplay"))
    assert len(result) == expected_count
    assert all(set(entry.keys()) == expected_keys for entry in result)  # = entry shape
    assert all(entry["covers"] == 1 for entry in result)
    assert all(entry["total"] == expected_total for entry in result)
    assert all(entry["attack_types"] == ["roleplay"] for entry in result)


def test_get_prioritized_mitigations_shared_mitigation_has_higher_covers():
    # roleplay and persuasion both list SYSTEM_PROMPT_HARDENING.
    types = ["roleplay", "persuasion"]
    expected_max_covers = 2  # = both share the mitigation

    result = get_prioritized_mitigations(types)

    shared = [e for e in result if e["mitigation"] == SYSTEM_PROMPT_HARDENING]
    assert len(shared) == 1
    assert shared[0]["covers"] == expected_max_covers
    assert shared[0]["attack_types"] == sorted(types)


def test_get_prioritized_mitigations_sorted_by_covers_descending():
    result = get_prioritized_mitigations(["roleplay", "persuasion"])

    covers_seq = [entry["covers"] for entry in result]
    assert covers_seq == sorted(covers_seq, reverse=True)


def test_get_prioritized_mitigations_total_equals_input_length():
    types = ["roleplay", "persuasion", "iterative"]
    expected_total = len(types)  # = 3

    result = get_prioritized_mitigations(types)

    assert all(entry["total"] == expected_total for entry in result)
