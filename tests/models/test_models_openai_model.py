"""Unit tests for hivetracered.models.openai_model.OpenAIModel — adapter-specific.

Shared adapter contract tests (max_concurrency default, temperature resolution,
api_key env-vs-explicit, retry-policy wiring, batch_size deprecation) live in
tests/models/test_models_chatopenai_adapter_contract.py. This file pins
OpenAI-specific defaults and ChatOpenAI/InMemoryRateLimiter wiring details.

Mocking strategy: patch ChatOpenAI and InMemoryRateLimiter at the SUT module
scope to capture init kwargs, and patch load_dotenv so the project's local
.env cannot override our monkeypatched env values.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hivetracered.models import openai_model as om
from hivetracered.models.openai_model import OpenAIModel


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def fake_chat_openai(monkeypatch):
    instance = MagicMock(name="ChatOpenAI-instance")
    instance.with_retry.return_value = instance
    cls = MagicMock(name="ChatOpenAI-class", return_value=instance)
    monkeypatch.setattr(om, "ChatOpenAI", cls)
    return cls


@pytest.fixture
def fake_rate_limiter(monkeypatch):
    instance = MagicMock(name="InMemoryRateLimiter-instance")
    cls = MagicMock(name="InMemoryRateLimiter-class", return_value=instance)
    monkeypatch.setattr(om, "InMemoryRateLimiter", cls)
    return cls


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch):
    monkeypatch.setattr(om, "load_dotenv", lambda *a, **kw: False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


# ── Defaults specific to OpenAIModel ────────────────────────────────


def test_openai_model_default_model_name_is_gpt_4_1_nano(fake_chat_openai, fake_rate_limiter):
    model = OpenAIModel()

    assert model.model_name == "gpt-4.1-nano"
    assert model.base_url == "https://api.openai.com/v1"


def test_openai_model_default_max_retries_is_three(fake_chat_openai, fake_rate_limiter):
    model = OpenAIModel()

    assert model.max_retries == 3


# ── ChatOpenAI wiring (specific kwargs forwarded) ───────────────────


def test_openai_model_passes_args_to_chatopenai(fake_chat_openai, fake_rate_limiter):
    """Line 73: ChatOpenAI receives model, base_url, rate_limiter, and **kwargs."""
    OpenAIModel(model="gpt-5", base_url="https://example.com/v1", max_tokens=512)

    init_kwargs = fake_chat_openai.call_args.kwargs
    assert init_kwargs["model"] == "gpt-5"
    assert init_kwargs["base_url"] == "https://example.com/v1"
    assert init_kwargs["max_tokens"] == 512
    assert init_kwargs["rate_limiter"] is fake_rate_limiter.return_value


# ── Rate limiter math (rpm/60) ──────────────────────────────────────


def test_openai_model_rate_limiter_uses_rpm_per_60_seconds(fake_chat_openai, fake_rate_limiter):
    """Lines 69-72: InMemoryRateLimiter(requests_per_second=rpm/60, check_every_n_seconds=0.1)."""
    OpenAIModel(rpm=120)

    rl_kwargs = fake_rate_limiter.call_args.kwargs
    assert rl_kwargs["requests_per_second"] == pytest.approx(2.0)  # 120 / 60
    assert rl_kwargs["check_every_n_seconds"] == pytest.approx(0.1)
