"""Unit tests for GoalCompletionEvaluator."""

from __future__ import annotations

import pytest

from hivetracered.evaluators.goal_completion_evaluator import (
    DEFAULT_GOAL_COMPLETION_TEMPLATE,
    GoalCompletionEvaluator,
)


# ── __init__ ──────────────────────────────────────────────────────────


def test_init_with_no_template_uses_default(mock_model):
    evaluator = GoalCompletionEvaluator(model=mock_model)

    assert evaluator.evaluation_prompt_template == DEFAULT_GOAL_COMPLETION_TEMPLATE


# ── _parse_evaluation_response: JSON tier ─────────────────────────────


def test_parse_valid_json_extracts_all_four_scores(mock_model):
    evaluator = GoalCompletionEvaluator(model=mock_model)
    content = '{"relevance": 7, "completeness": 8, "actionability": 6, "overall": 9}'

    result = evaluator._parse_evaluation_response({"content": content})

    assert result["relevance"] == 7
    assert result["completeness"] == 8
    assert result["actionability"] == 6
    assert result["overall_rating"] == 9


# ── threshold logic ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "overall, expected_success, expected_score",
    [
        (6, False, 0.6),  # below threshold
        (7, True, 0.7),   # at threshold (>=)
        (10, True, 1.0),  # above threshold
    ],
    ids=["below", "at-boundary", "above"],
)
def test_parse_threshold_decision(mock_model, overall, expected_success, expected_score):
    evaluator = GoalCompletionEvaluator(model=mock_model, success_threshold=0.7)
    content = f'{{"relevance": 1, "completeness": 1, "actionability": 1, "overall": {overall}}}'

    result = evaluator._parse_evaluation_response({"content": content})

    assert result["success"] is expected_success
    assert result["score"] == pytest.approx(expected_score)


# ── default values when fields missing ───────────────────────────────


def test_parse_partial_fields_uses_defaults_for_missing(mock_model):
    # Missing overall + missing sub-dimensions both default to 1.
    evaluator = GoalCompletionEvaluator(model=mock_model)
    content = '{"relevance": 8, "overall": 9}'

    result = evaluator._parse_evaluation_response({"content": content})

    assert result["relevance"] == 8
    assert result["overall_rating"] == 9
    assert result["completeness"] == 1  # default
    assert result["actionability"] == 1  # default


# ── regex fallback when JSON parse fails ─────────────────────────────


def test_parse_regex_fallback_extracts_scores_from_prose(mock_model):
    # Surrounding text breaks JSON parse; regex picks each "field": N.
    evaluator = GoalCompletionEvaluator(model=mock_model)
    content = 'My evaluation: "relevance": 6, "completeness": 7, "actionability": 8, "overall": 8 done.'

    result = evaluator._parse_evaluation_response({"content": content})

    assert result["relevance"] == 6
    assert result["completeness"] == 7
    assert result["actionability"] == 8
    assert result["overall_rating"] == 8


def test_parse_regex_fallback_missing_fields_default_to_1(mock_model):
    evaluator = GoalCompletionEvaluator(model=mock_model)
    # Not JSON, only contains relevance — others missing.
    content = 'partial: "relevance": 5 only'

    result = evaluator._parse_evaluation_response({"content": content})

    assert result["relevance"] == 5
    assert result["completeness"] == 1
    assert result["actionability"] == 1
    assert result["overall_rating"] == 1


# ── completely unparseable -> all defaults ───────────────────────────


def test_parse_unrelated_text_returns_all_defaults(mock_model):
    evaluator = GoalCompletionEvaluator(model=mock_model)

    result = evaluator._parse_evaluation_response({"content": "no scores anywhere"})

    assert result["relevance"] == 1
    assert result["completeness"] == 1
    assert result["actionability"] == 1
    assert result["overall_rating"] == 1
    assert result["success"] is False


# ── get_params ────────────────────────────────────────────────────────


def test_get_params_includes_success_threshold(mock_model):
    evaluator = GoalCompletionEvaluator(model=mock_model, success_threshold=0.3)

    params = evaluator.get_params()

    assert params["success_threshold"] == 0.3
    assert "evaluation_prompt_template" in params


# ── _coerce_score helper ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        (0, 1, 1),  # clamps min
        (15, 1, 10),  # clamps max
        ("not-a-number", 7, 7),  # falls through to default
        (None, 3, 3),
        ("8", 1, 8),  # numeric string ok
    ],
    ids=["below-min", "above-max", "non-numeric-str", "none", "numeric-str"],
)
def test_coerce_score_handles_various_inputs(value, default, expected):
    assert GoalCompletionEvaluator._coerce_score(value, default) == expected
