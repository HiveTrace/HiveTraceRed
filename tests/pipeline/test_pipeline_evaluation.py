"""Unit tests for the evaluation pipeline module.

Covers stream_evaluated_responses: blocked-response short-circuit, evaluator
streaming over unblocked responses, ordering preservation, and empty input.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List

from hivetracered.evaluators.base_evaluator import BaseEvaluator
from hivetracered.pipeline.evaluation import (
    RESPONSE_BLOCKED,
    stream_evaluated_responses,
)
from tests.conftest import async_collect


class _ScriptedEvaluator(BaseEvaluator):
    """Evaluator returning preconfigured per-response results in order.

    Used to test stream_evaluated_responses without depending on KeywordEvaluator's
    keyword loading or matching logic.
    """

    def __init__(self, results: List[Dict[str, Any]]):
        self._results = list(results)

    def evaluate(self, prompt, response):
        return self._results.pop(0)

    async def stream_abatch(self, prompts, responses) -> AsyncGenerator[Dict[str, Any], None]:
        for r in self._results:
            yield r

    def get_name(self) -> str:
        return "_ScriptedEvaluator"

    def get_description(self) -> str:
        return "scripted"

    def get_params(self) -> Dict[str, Any]:
        return {"scripted": True}


# ── Empty input ─────────────────────────────────────────────────────


def test_stream_evaluated_responses_empty_input_yields_nothing():
    evaluator = _ScriptedEvaluator([])

    results = async_collect(stream_evaluated_responses(evaluator, []))

    assert results == []


# ── Successful evaluation path ──────────────────────────────────────


def test_stream_evaluated_responses_preserves_input_order():
    evaluator = _ScriptedEvaluator([
        {"success": True, "tag": "first"},
        {"success": True, "tag": "second"},
        {"success": True, "tag": "third"},
    ])
    responses = [
        {"base_prompt": f"p{i}", "response": f"r{i}", "model": "M"} for i in range(3)
    ]

    results = async_collect(stream_evaluated_responses(evaluator, responses))

    assert [r["base_prompt"] for r in results] == ["p0", "p1", "p2"]


def test_stream_evaluated_responses_attaches_evaluator_metadata():
    evaluator = _ScriptedEvaluator([{"success": True, "score": 0.5}])
    responses = [{"base_prompt": "p", "response": "r", "model": "M"}]

    results = async_collect(stream_evaluated_responses(evaluator, responses))

    assert results[0]["evaluator"] == "_ScriptedEvaluator"
    assert results[0]["evaluator_params"] == {"scripted": True}
    assert results[0]["evaluation"] == {"success": True, "score": 0.5}


# ── Blocked-response short-circuit ──────────────────────────────────


def test_stream_evaluated_responses_blocked_response_marked_unsuccessful_with_reason():
    evaluator = _ScriptedEvaluator([])  # no unblocked → no batch results
    responses = [{"base_prompt": "p", "response": "", "is_blocked": True}]

    results = async_collect(stream_evaluated_responses(evaluator, responses))

    assert len(results) == 1
    assert results[0]["success"] is False
    assert results[0]["evaluation"]["reason"] == RESPONSE_BLOCKED
    assert results[0]["evaluator"] == ""


def test_stream_evaluated_responses_mixed_blocked_and_unblocked_preserves_order():
    # responses[0] blocked, [1] unblocked, [2] blocked
    evaluator = _ScriptedEvaluator([{"success": True, "score": 1.0}])
    responses = [
        {"base_prompt": "p0", "response": "", "is_blocked": True},
        {"base_prompt": "p1", "response": "ok", "is_blocked": False},
        {"base_prompt": "p2", "response": "", "is_blocked": True},
    ]

    results = async_collect(stream_evaluated_responses(evaluator, responses))

    assert [r["base_prompt"] for r in results] == ["p0", "p1", "p2"]
    assert results[0]["evaluation"]["reason"] == RESPONSE_BLOCKED
    assert results[1]["success"] is True
    assert results[2]["evaluation"]["reason"] == RESPONSE_BLOCKED


