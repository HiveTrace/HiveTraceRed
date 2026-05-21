"""Unit tests for KeywordEvaluator."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hivetracered.evaluators.keyword_evaluator import KeywordEvaluator
from tests.conftest import async_collect


# ── __init__: default keyword loading ─────────────────────────────────


def test_init_with_no_keywords_invokes_load_keywords():
    # When keywords is None, evaluator must call load_keywords() to load defaults.
    sentinel = ["alpha", "beta"]

    with patch(
        "hivetracered.evaluators.keyword_evaluator.load_keywords",
        return_value=sentinel,
    ) as mocked:
        evaluator = KeywordEvaluator()

    mocked.assert_called_once_with()
    assert evaluator.keywords == sentinel


def test_init_with_explicit_keywords_does_not_call_load_keywords():
    with patch(
        "hivetracered.evaluators.keyword_evaluator.load_keywords"
    ) as mocked:
        evaluator = KeywordEvaluator(keywords=["x", "y"])

    mocked.assert_not_called()
    assert evaluator.keywords == ["x", "y"]


# ── evaluate: basic matching + occurrence counting ────────────────────


@pytest.mark.parametrize(
    "keyword, response, expected_success, expected_matched, expected_count",
    [
        ("bomb", "how to make a bomb", False, ["bomb"], 1),
        ("forbidden", "totally innocuous content", True, [], 0),
        ("abc", "abc abc abc", False, ["abc"], 3),
    ],
    ids=["match-once", "no-match", "match-thrice"],
)
def test_evaluate_basic_match_and_count(keyword, response, expected_success, expected_matched, expected_count):
    evaluator = KeywordEvaluator(keywords=[keyword])

    result = evaluator.evaluate("p", response)

    assert result["success"] is expected_success
    assert result["matched_keywords"] == expected_matched
    assert result["keyword_count"][keyword] == expected_count


# ── case sensitivity ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "case_sensitive, expected_success, expected_match",
    [
        (True, True, []),       # different case -> no match
        (False, False, ["bomb"]),  # case-insensitive matches
    ],
    ids=["sensitive", "insensitive"],
)
def test_evaluate_case_sensitivity(case_sensitive, expected_success, expected_match):
    evaluator = KeywordEvaluator(keywords=["bomb"], case_sensitive=case_sensitive)

    result = evaluator.evaluate("p", "Bomb in headlines")

    assert result["success"] is expected_success
    assert result["matched_keywords"] == expected_match


# ── match_all logic ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "match_all, response, expected_success, expected_matched_set",
    [
        # match_all=True with one keyword present -> not all matched -> not blocked
        (True, "alpha is here, second word absent", True, {"alpha"}),
        # match_all=True with all keywords present -> blocked
        (True, "alpha and beta both here", False, {"alpha", "beta"}),
    ],
    ids=["all-partial", "all-complete"],
)
def test_evaluate_match_all(match_all, response, expected_success, expected_matched_set):
    evaluator = KeywordEvaluator(keywords=["alpha", "beta"], match_all=match_all)

    result = evaluator.evaluate("p", response)

    assert result["success"] is expected_success
    assert set(result["matched_keywords"]) == expected_matched_set


# ── response type extraction ──────────────────────────────────────────


class _RespWithContent:
    content = "the secret is exposed"


@pytest.mark.parametrize(
    "response, expected_count",
    [
        ({"content": "the secret is out"}, 1),  # dict with content key
        (_RespWithContent(), 1),                # object with .content attr
        (123, 1),  # int has no .content; str(123) -> "123"; "12" appears in "123"
    ],
    ids=["dict-content", "object-content-attr", "int-fallback-str"],
)
def test_evaluate_extracts_response_text_by_type(response, expected_count):
    keyword = "12" if isinstance(response, int) else "secret"
    evaluator = KeywordEvaluator(keywords=[keyword])

    result = evaluator.evaluate("p", response)

    assert result["keyword_count"][keyword] == expected_count
    assert result["success"] is False


# ── get_description ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "kwargs, must_contain",
    [
        ({"match_all": False}, "any"),
        ({"match_all": True}, "all"),
        ({"case_sensitive": True}, "case-sensitive"),
        ({"case_sensitive": False}, "case-insensitive"),
    ],
    ids=["match_any", "match_all", "case_sensitive", "case_insensitive"],
)
def test_get_description_auto_generated_includes_mode_words(kwargs, must_contain):
    evaluator = KeywordEvaluator(keywords=["x"], **kwargs)

    desc = evaluator.get_description()

    assert must_contain in desc


def test_get_description_custom_overrides_default():
    evaluator = KeywordEvaluator(keywords=["x"], description="my-custom")

    assert evaluator.get_description() == "my-custom"


# ── get_name ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({}, "Keyword Evaluator"),
        ({"name": "my-name"}, "my-name"),
    ],
    ids=["default", "custom"],
)
def test_get_name(kwargs, expected):
    evaluator = KeywordEvaluator(keywords=["x"], **kwargs)

    assert evaluator.get_name() == expected


# ── get_params ────────────────────────────────────────────────────────


def test_get_params_contains_required_keys():
    evaluator = KeywordEvaluator(keywords=["x"], case_sensitive=True, match_all=True)

    params = evaluator.get_params()

    assert set(params.keys()) >= {"keywords", "case_sensitive", "match_all", "name", "description"}
    assert params["keywords"] == ["x"]
    assert params["case_sensitive"] is True
    assert params["match_all"] is True


# ── stream_abatch ─────────────────────────────────────────────────────


def test_stream_abatch_yields_one_result_per_prompt_response_pair():
    evaluator = KeywordEvaluator(keywords=["bad"])
    prompts = ["p1", "p2", "p3"]
    responses = ["bad word", "ok", "another bad word"]

    results = async_collect(evaluator.stream_abatch(prompts, responses))

    assert len(results) == 3  # = len(prompts)
    assert [r["success"] for r in results] == [False, True, False]
