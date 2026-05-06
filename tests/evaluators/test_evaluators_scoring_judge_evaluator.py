"""Unit tests for ScoringJudgeEvaluator."""

from __future__ import annotations

import pytest

from hivetracered.evaluators.scoring_judge_evaluator import (
    DEFAULT_SCORING_JUDGE_TEMPLATE,
    ScoringJudgeEvaluator,
)


# ── __init__ ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "kwargs, expected_template",
    [
        ({}, DEFAULT_SCORING_JUDGE_TEMPLATE),
        ({"evaluation_prompt_template": "ask {prompt} got {response}"}, "ask {prompt} got {response}"),
    ],
    ids=["default-template", "custom-template"],
)
def test_init_template(mock_model, kwargs, expected_template):
    evaluator = ScoringJudgeEvaluator(model=mock_model, **kwargs)

    assert evaluator.evaluation_prompt_template == expected_template


# ── _parse_evaluation_response: JSON tier + threshold logic ──────────


@pytest.mark.parametrize(
    "rating, expected_score, expected_success",
    [
        (1, 0.1, False),   # min, below threshold
        (5, 0.5, False),   # mid, below threshold
        (7, 0.7, True),    # at-boundary (>= inclusive)
        (9, 0.9, True),    # above threshold
        (10, 1.0, True),   # max
    ],
    ids=["min", "below", "at-boundary", "above", "max"],
)
def test_parse_evaluation_response_json_rating_score_and_threshold(mock_model, rating, expected_score, expected_success):
    # Default threshold is 0.7; covers (a) JSON rating extraction,
    # (b) score = rating/10 formula, (c) success = score >= threshold.
    evaluator = ScoringJudgeEvaluator(model=mock_model, success_threshold=0.7)

    result = evaluator._parse_evaluation_response({"content": f'{{"rating": {rating}}}'})

    assert result["rating"] == rating
    assert result["score"] == pytest.approx(expected_score)
    assert result["success"] is expected_success


# ── Bound clamping (max 10, min 1) ────────────────────────────────────


@pytest.mark.parametrize(
    "raw_rating, expected_rating",
    [
        (99, 10),  # clamps above
        (0, 1),    # clamps below
    ],
    ids=["above-max", "below-min"],
)
def test_parse_evaluation_response_clamps_rating(mock_model, raw_rating, expected_rating):
    evaluator = ScoringJudgeEvaluator(model=mock_model)

    result = evaluator._parse_evaluation_response({"content": f'{{"rating": {raw_rating}}}'})

    assert result["rating"] == expected_rating


# ── Tier 2: regex fallback when JSON parse fails ──────────────────────


def test_parse_evaluation_response_regex_fallback_extracts_rating_from_prose(mock_model):
    # Not pure JSON, but contains "rating": N pattern.
    evaluator = ScoringJudgeEvaluator(model=mock_model)

    result = evaluator._parse_evaluation_response({"content": 'I think {"rating": 8} is right'})

    assert result["rating"] == 8


# ── Tier 3: bare-number fallback ──────────────────────────────────────


def test_parse_evaluation_response_bare_number_fallback_uses_last_number(mock_model):
    # No JSON, no "rating": pattern; last number 1-10 is used.
    evaluator = ScoringJudgeEvaluator(model=mock_model)

    result = evaluator._parse_evaluation_response({"content": "First 3, then 7."})

    assert result["rating"] == 7  # last bare number wins


# ── Tier 4: complete failure -> default 1 ─────────────────────────────


def test_parse_evaluation_response_unparseable_returns_default_rating_1(mock_model):
    evaluator = ScoringJudgeEvaluator(model=mock_model)

    result = evaluator._parse_evaluation_response({"content": "no numbers here at all"})

    assert result["rating"] == 1


def test_parse_evaluation_response_missing_content_key_returns_default_rating_1(mock_model):
    evaluator = ScoringJudgeEvaluator(model=mock_model)

    # Empty content (key missing -> default "")
    result = evaluator._parse_evaluation_response({})

    assert result["rating"] == 1
    assert result["success"] is False


# ── get_params ────────────────────────────────────────────────────────


def test_get_params_includes_success_threshold(mock_model):
    evaluator = ScoringJudgeEvaluator(model=mock_model, success_threshold=0.4)

    params = evaluator.get_params()

    assert params["success_threshold"] == 0.4
    assert "evaluation_prompt_template" in params
    assert "name" in params
    assert "description" in params
