"""Unit tests for ModelEvaluator abstract base class."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from hivetracered.evaluators.model_evaluator import ModelEvaluator
from tests.conftest import MockModel, async_collect


# ── Concrete test subclass that satisfies the abstract API ────────────


class _ConcreteModelEvaluator(ModelEvaluator):
    """Minimal concrete subclass for testing the ModelEvaluator base."""

    def _parse_evaluation_response(self, evaluation_response: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True, "raw": evaluation_response}


class _RespWithContent:
    content = "from-attr"


# ── create_evaluation_prompt: prompt extraction ────────────────────────


def test_create_evaluation_prompt_string_prompt_is_inserted_verbatim(mock_model):
    evaluator = _ConcreteModelEvaluator(model=mock_model, evaluation_prompt_template="P:{prompt} R:{response}")

    out = evaluator.create_evaluation_prompt("hello", "world")

    assert out == "P:hello R:world"


def test_create_evaluation_prompt_message_list_concatenates_role_and_content(mock_model):
    evaluator = _ConcreteModelEvaluator(model=mock_model, evaluation_prompt_template="{prompt}//{response}")
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "human", "content": "hi"},
    ]

    out = evaluator.create_evaluation_prompt(msgs, "ok")

    assert out == "system: sys\nhuman: hi//ok"


def test_create_evaluation_prompt_unrecognized_prompt_falls_back_to_str(mock_model):
    evaluator = _ConcreteModelEvaluator(model=mock_model, evaluation_prompt_template="{prompt}|{response}")

    # Non-list/non-str prompt -> str(prompt).
    out = evaluator.create_evaluation_prompt(123, "r")

    assert out == "123|r"


@pytest.mark.parametrize(
    "response, expected_text",
    [
        ({"content": "extracted"}, "extracted"),  # dict with content key
        (_RespWithContent(), "from-attr"),         # object with .content
        (42, "42"),                                # fallback to str()
    ],
    ids=["dict-content", "object-content-attr", "int-fallback-str"],
)
def test_create_evaluation_prompt_extracts_response_text_by_type(mock_model, response, expected_text):
    evaluator = _ConcreteModelEvaluator(model=mock_model, evaluation_prompt_template="{prompt}|{response}")

    out = evaluator.create_evaluation_prompt("p", response)

    assert out == f"p|{expected_text}"


# ── evaluate calls model.invoke with the formatted prompt ──────────────


def test_evaluate_calls_model_invoke_with_formatted_prompt():
    model = MockModel(response={"content": "judge-output"})
    evaluator = _ConcreteModelEvaluator(model=model, evaluation_prompt_template="ASK:{prompt}|GOT:{response}")

    result = evaluator.evaluate("p1", "r1")

    assert model.call_log == ["ASK:p1|GOT:r1"]
    assert result == {"success": True, "raw": {"content": "judge-output"}}


# ── stream_abatch yields one parsed result per prompt-response pair ────


def test_stream_abatch_formats_prompts_and_yields_parsed_per_pair():
    model = MockModel(side_effect=[{"content": "a"}, {"content": "b"}])
    evaluator = _ConcreteModelEvaluator(model=model, evaluation_prompt_template="<{prompt}|{response}>")

    results = async_collect(evaluator.stream_abatch(["p0", "p1"], ["r0", "r1"]))

    assert len(results) == 2  # = len(prompts)
    assert model.call_log == ["<p0|r0>", "<p1|r1>"]
    assert [r["raw"]["content"] for r in results] == ["a", "b"]


# ── get_name / get_description defaults vs custom ─────────────────────


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({}, "Model-based Evaluator"),
        ({"name": "MyEval"}, "MyEval"),
    ],
    ids=["default", "custom"],
)
def test_get_name(mock_model, kwargs, expected):
    evaluator = _ConcreteModelEvaluator(model=mock_model, evaluation_prompt_template="t", **kwargs)

    assert evaluator.get_name() == expected


@pytest.mark.parametrize(
    "kwargs, check",
    [
        ({}, lambda d: d == "Evaluates responses using a language model to analyze prompt-response pairs"),
        ({"description": "custom-desc"}, lambda d: d == "custom-desc"),
    ],
    ids=["default", "custom"],
)
def test_get_description(mock_model, kwargs, check):
    evaluator = _ConcreteModelEvaluator(model=mock_model, evaluation_prompt_template="t", **kwargs)

    assert check(evaluator.get_description())


def test_get_params_returns_dict_with_required_keys(mock_model):
    evaluator = _ConcreteModelEvaluator(model=mock_model, evaluation_prompt_template="TPL")

    params = evaluator.get_params()

    assert params["evaluation_prompt_template"] == "TPL"
    assert "name" in params and "description" in params
    assert params["model_name"] == "mock"  # propagated from mock_model.get_params()
