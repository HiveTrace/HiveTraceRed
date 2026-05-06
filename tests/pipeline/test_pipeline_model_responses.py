"""Unit tests for the model_responses pipeline module.

Covers stream_model_responses: yielded record shape, ordering, error
propagation from the model, and is_blocked flag.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List

import pytest

from hivetracered.models.base_model import Model
from hivetracered.pipeline.model_responses import stream_model_responses
from tests.conftest import MockModel, async_collect


# ── Yielded shape ───────────────────────────────────────────────────


def test_stream_model_responses_record_contains_response_and_metadata(tmp_path):
    model = MockModel(side_effect=[{"content": "the-answer"}])
    attack_prompts = [{"prompt": "hello", "attack_name": "A", "extra": "kept"}]

    results = async_collect(stream_model_responses(model, attack_prompts, str(tmp_path)))

    record = results[0]
    assert record["response"] == "the-answer"
    assert record["raw_response"] == {"content": "the-answer"}
    assert record["model"] == "MockModel"
    assert record["model_params"] == {"model_name": "mock"}
    assert record["is_blocked"] is False
    assert record["extra"] == "kept"  # original column preserved
    assert record["prompt"] == "hello"


# ── Ordering ────────────────────────────────────────────────────────


def test_stream_model_responses_preserves_input_order(tmp_path):
    model = MockModel(side_effect=[{"content": f"r{i}"} for i in range(5)])
    attack_prompts = [{"prompt": f"p{i}", "attack_name": "A"} for i in range(5)]

    results = async_collect(stream_model_responses(model, attack_prompts, str(tmp_path)))

    assert [r["response"] for r in results] == [f"r{i}" for i in range(5)]
    assert [r["prompt"] for r in results] == [f"p{i}" for i in range(5)]


# ── Error propagation ───────────────────────────────────────────────


def test_stream_model_responses_records_error_when_model_returns_error_field(tmp_path):
    # Per the source: when a response dict has "error" key, the record copies it.
    model = MockModel(side_effect=[{"content": "", "error": "rate-limited"}])
    attack_prompts = [{"prompt": "p", "attack_name": "A"}]

    results = async_collect(stream_model_responses(model, attack_prompts, str(tmp_path)))

    assert results[0]["error"] == "rate-limited"
    assert results[0]["response"] == ""


def test_stream_model_responses_does_not_add_error_field_on_success(tmp_path):
    model = MockModel(side_effect=[{"content": "ok"}])
    attack_prompts = [{"prompt": "p", "attack_name": "A"}]

    results = async_collect(stream_model_responses(model, attack_prompts, str(tmp_path)))

    assert "error" not in results[0]


# ── is_blocked flag ─────────────────────────────────────────────────


class _BlockingModel(MockModel):
    def is_answer_blocked(self, answer: dict) -> bool:
        return answer.get("content") == "BLOCKED"


def test_stream_model_responses_marks_blocked_when_model_says_blocked(tmp_path):
    model = _BlockingModel(side_effect=[{"content": "BLOCKED"}, {"content": "ok"}])
    attack_prompts = [
        {"prompt": "p0", "attack_name": "A"},
        {"prompt": "p1", "attack_name": "A"},
    ]

    results = async_collect(stream_model_responses(model, attack_prompts, str(tmp_path)))

    assert results[0]["is_blocked"] is True
    assert results[1]["is_blocked"] is False


# ── Empty input ─────────────────────────────────────────────────────


def test_stream_model_responses_empty_input_yields_nothing(tmp_path):
    model = MockModel()

    results = async_collect(stream_model_responses(model, [], str(tmp_path)))

    assert results == []
