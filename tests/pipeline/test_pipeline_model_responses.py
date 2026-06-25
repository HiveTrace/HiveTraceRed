"""Unit tests for the model_responses pipeline module.

Covers stream_model_responses: yielded record shape, ordering, error
propagation from the model, and is_blocked flag.
"""

from __future__ import annotations

from hivetracered.pipeline.model_responses import stream_model_responses
from tests.conftest import MockModel, async_collect


# ── Yielded shape ───────────────────────────────────────────────────


def test_stream_model_responses_record_contains_response_and_metadata():
    model = MockModel(side_effect=[{"content": "the-answer"}])
    attack_prompts = [{"prompt": "hello", "attack_name": "A", "extra": "kept"}]

    results = async_collect(stream_model_responses(model, attack_prompts))

    record = results[0]
    assert record["response"] == "the-answer"
    assert record["raw_response"] == {"content": "the-answer"}
    assert record["model"] == "MockModel"
    assert record["model_params"] == {"model_name": "mock"}
    assert record["is_blocked"] is False
    assert record["extra"] == "kept"  # original column preserved
    assert record["prompt"] == "hello"


# ── Ordering ────────────────────────────────────────────────────────


def test_stream_model_responses_preserves_input_order():
    model = MockModel(side_effect=[{"content": f"r{i}"} for i in range(5)])
    attack_prompts = [{"prompt": f"p{i}", "attack_name": "A"} for i in range(5)]

    results = async_collect(stream_model_responses(model, attack_prompts))

    assert [r["response"] for r in results] == [f"r{i}" for i in range(5)]
    assert [r["prompt"] for r in results] == [f"p{i}" for i in range(5)]


# ── Error propagation ───────────────────────────────────────────────


def test_stream_model_responses_records_error_when_model_returns_error_field():
    # Per the source: when a response dict has "error" key, the record copies it.
    model = MockModel(side_effect=[{"content": "", "error": "rate-limited"}])
    attack_prompts = [{"prompt": "p", "attack_name": "A"}]

    results = async_collect(stream_model_responses(model, attack_prompts))

    assert results[0]["error"] == "rate-limited"
    assert results[0]["response"] == ""


def test_stream_model_responses_does_not_add_error_field_on_success():
    model = MockModel(side_effect=[{"content": "ok"}])
    attack_prompts = [{"prompt": "p", "attack_name": "A"}]

    results = async_collect(stream_model_responses(model, attack_prompts))

    assert "error" not in results[0]


# ── Circuit breaker ─────────────────────────────────────────────────


def test_stream_model_responses_circuit_breaker_marks_remaining_without_sending():
    # 3 errors in a row at threshold 3 -> stop sending, mark the rest skipped_after_failures.
    model = MockModel(side_effect=[
        {"content": "", "error": "no balance"},
        {"content": "", "error": "no balance"},
        {"content": "", "error": "no balance"},
        {"content": "unused"},
        {"content": "unused"},
    ])
    attack_prompts = [{"prompt": f"p{i}", "attack_name": "A"} for i in range(5)]

    results = async_collect(
        stream_model_responses(model, attack_prompts, consecutive_failures=3)
    )

    # Contract preserved: one record per prompt, in order.
    assert len(results) == 5
    assert [r["prompt"] for r in results] == [f"p{i}" for i in range(5)]
    # Remaining prompts are synthetic skipped errors, model never queried for them.
    assert results[3]["error"].startswith("skipped_after_failures:")
    assert results[4]["error"].startswith("skipped_after_failures:")
    assert results[4]["response"] == ""
    assert model.call_log == ["p0", "p1", "p2"]


def test_stream_model_responses_breaker_disabled_when_zero():
    model = MockModel(side_effect=[{"content": "", "error": "e"} for _ in range(4)])
    attack_prompts = [{"prompt": f"p{i}", "attack_name": "A"} for i in range(4)]

    results = async_collect(
        stream_model_responses(model, attack_prompts, consecutive_failures=0)
    )

    assert len(results) == 4
    assert all("skipped_after_failures" not in (r.get("error") or "") for r in results)
    assert model.call_log == ["p0", "p1", "p2", "p3"]


# ── Stage-1 error passthrough ───────────────────────────────────────


def test_stream_model_responses_does_not_send_records_with_stage1_error():
    # A record that already failed in Stage 1 (error set, empty prompt) must NOT
    # be sent to the target; its error passes straight through, order preserved.
    model = MockModel(side_effect=[{"content": "real-answer"}])
    attack_prompts = [
        {"prompt": "", "base_prompt": "p0", "error": "attacker failed"},
        {"prompt": "real", "base_prompt": "p1"},
    ]

    results = async_collect(stream_model_responses(model, attack_prompts))

    assert [r["base_prompt"] for r in results] == ["p0", "p1"]
    assert model.call_log == ["real"]            # only the clean prompt was sent
    assert results[0]["error"] == "attacker failed"
    assert results[0]["response"] == ""
    assert results[1]["response"] == "real-answer"
    assert "error" not in results[1]


# ── is_blocked flag ─────────────────────────────────────────────────


class _BlockingModel(MockModel):
    def is_answer_blocked(self, answer: dict) -> bool:
        return answer.get("content") == "BLOCKED"


def test_stream_model_responses_marks_blocked_when_model_says_blocked():
    model = _BlockingModel(side_effect=[{"content": "BLOCKED"}, {"content": "ok"}])
    attack_prompts = [
        {"prompt": "p0", "attack_name": "A"},
        {"prompt": "p1", "attack_name": "A"},
    ]

    results = async_collect(stream_model_responses(model, attack_prompts))

    assert results[0]["is_blocked"] is True
    assert results[1]["is_blocked"] is False


# ── Empty input ─────────────────────────────────────────────────────


def test_stream_model_responses_empty_input_yields_nothing():
    model = MockModel()

    results = async_collect(stream_model_responses(model, []))

    assert results == []
