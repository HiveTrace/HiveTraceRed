"""Auto-discovery conformance tests for all registered evaluators.

Automatically discovers all evaluators from EVALUATOR_CLASSES and validates each
against the BaseEvaluator contract. No per-evaluator test code needed.
"""

from __future__ import annotations

import pytest

from hivetracered.evaluators.base_evaluator import BaseEvaluator
from hivetracered.evaluators.model_evaluator import ModelEvaluator
from hivetracered.pipeline.constants import EVALUATOR_CLASSES
from tests.conftest import MockModel, async_collect


# ── Import setup_evaluator from __main__ ────────────────────────────

from hivetracered.__main__ import setup_evaluator


# ── Classification & instantiation helpers ──────────────────────────


def classify(evaluator_class):
    """Return 'model' if requires a Model, 'standalone' otherwise."""
    if issubclass(evaluator_class, ModelEvaluator):
        return "model"
    return "standalone"


# Mock responses that each evaluator's _parse_evaluation_response can handle
MOCK_RESPONSES = {
    "WildGuardGPTEvaluator": {"content": "1. no\n2. refuse\n3. no"},
    "WildGuardGPTRuEvaluator": {"content": "1. нет\n2. отказывается\n3. нет"},
    "WildGuardGPTRuHalEvaluator": {"content": "1. нет\n2. отказывается\n3. нет\n4. нет"},
    "ScoringJudgeEvaluator": {"content": '{"rating": 5}'},
    "GoalCompletionEvaluator": {"content": '{"relevance": 5, "completeness": 5, "actionability": 5, "overall": 5}'},
}

DEFAULT_MOCK_RESPONSE = {"content": "1. no\n2. refuse\n3. no"}


def make_instance(evaluator_name, evaluator_class, family):
    """Instantiate an evaluator with appropriate mocks."""
    if family == "model":
        response = MOCK_RESPONSES.get(evaluator_name, DEFAULT_MOCK_RESPONSE)
        model = MockModel(response=response)
        return evaluator_class(model=model)
    # Standalone evaluators
    if evaluator_name == "SystemPromptDetectionEvaluator":
        return evaluator_class(system_prompt="test system prompt")
    return evaluator_class()


# ── Parametrize over all registered evaluators ──────────────────────

ALL_EVALUATORS = [
    (name, cls, classify(cls))
    for name, cls in EVALUATOR_CLASSES.items()
]


@pytest.mark.parametrize(
    "evaluator_name,evaluator_class,family",
    ALL_EVALUATORS,
    ids=[e[0] for e in ALL_EVALUATORS],
)
class TestEvaluatorConformance:
    """Conformance tests applied to every registered evaluator."""

    # ── Instantiation ───────────────────────────────────────────

    def test_instantiation(self, evaluator_name, evaluator_class, family):
        evaluator = make_instance(evaluator_name, evaluator_class, family)
        assert evaluator is not None

    # ── Metadata ────────────────────────────────────────────────

    def test_get_name(self, evaluator_name, evaluator_class, family):
        evaluator = make_instance(evaluator_name, evaluator_class, family)
        name = evaluator.get_name()
        assert isinstance(name, str) and len(name) > 0

    def test_get_description(self, evaluator_name, evaluator_class, family):
        evaluator = make_instance(evaluator_name, evaluator_class, family)
        desc = evaluator.get_description()
        assert isinstance(desc, str) and len(desc) > 0

    def test_get_params(self, evaluator_name, evaluator_class, family):
        evaluator = make_instance(evaluator_name, evaluator_class, family)
        params = evaluator.get_params()
        assert isinstance(params, dict)

    # ── evaluate(string prompt) ─────────────────────────────────

    def test_evaluate_string(self, evaluator_name, evaluator_class, family):
        evaluator = make_instance(evaluator_name, evaluator_class, family)
        result = evaluator.evaluate("test prompt", "test response")
        assert isinstance(result, dict)
        assert "success" in result
        assert isinstance(result["success"], bool)

    # ── evaluate(message list prompt) ───────────────────────────

    def test_evaluate_message_list(self, evaluator_name, evaluator_class, family):
        evaluator = make_instance(evaluator_name, evaluator_class, family)
        msgs = [{"role": "human", "content": "test prompt"}]
        result = evaluator.evaluate(msgs, "test response")
        assert isinstance(result, dict)
        assert "success" in result
        assert isinstance(result["success"], bool)

    # ── stream_abatch ───────────────────────────────────────────

    def test_stream_abatch(self, evaluator_name, evaluator_class, family):
        evaluator = make_instance(evaluator_name, evaluator_class, family)
        prompts = [f"prompt {i}" for i in range(5)]
        responses = [f"response {i}" for i in range(5)]
        results = async_collect(evaluator.stream_abatch(prompts, responses))
        assert len(results) == 5, (
            f"{evaluator_name}.stream_abatch returned {len(results)} results, expected 5"
        )

    def test_stream_abatch_order(self, evaluator_name, evaluator_class, family):
        if family == "standalone":
            # Standalone evaluators are deterministic, just check count
            evaluator = make_instance(evaluator_name, evaluator_class, family)
            prompts = [f"prompt {i}" for i in range(5)]
            responses = [f"response {i}" for i in range(5)]
            results = async_collect(evaluator.stream_abatch(prompts, responses))
            assert len(results) == 5
        else:
            # Model-based: use side_effect to verify order
            response = MOCK_RESPONSES.get(evaluator_name, DEFAULT_MOCK_RESPONSE)
            responses_list = [dict(response) for _ in range(5)]
            model = MockModel(side_effect=responses_list)
            if evaluator_name == "SystemPromptDetectionEvaluator":
                evaluator = evaluator_class(system_prompt="test", model=model)
            else:
                evaluator = evaluator_class(model=model)
            prompts = [f"prompt {i}" for i in range(5)]
            responses = [f"response {i}" for i in range(5)]
            results = async_collect(evaluator.stream_abatch(prompts, responses))
            assert len(results) == 5
            # Each result must have 'success' key
            for r in results:
                assert "success" in r

    # ── Registration ────────────────────────────────────────────

    def test_registration(self, evaluator_name, evaluator_class, family):
        assert evaluator_name in EVALUATOR_CLASSES
        assert EVALUATOR_CLASSES[evaluator_name] is evaluator_class

    # ── Pipeline wiring ─────────────────────────────────────────

    def test_pipeline_wiring(self, evaluator_name, evaluator_class, family):
        mock = MockModel(response=MOCK_RESPONSES.get(evaluator_name, DEFAULT_MOCK_RESPONSE))
        if evaluator_name == "SystemPromptDetectionEvaluator":
            config = {"name": evaluator_name, "params": {"system_prompt": "test"}}
        else:
            config = {"name": evaluator_name}
        evaluator = setup_evaluator(config, model=mock)
        assert isinstance(evaluator, evaluator_class)
