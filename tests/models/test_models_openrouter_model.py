# pyright: reportUnusedParameter=false, reportUnusedFunction=false
"""Unit tests for hivetracered.models.openrouter_model.OpenRouterModel — adapter-specific.

Shared adapter contract tests live in tests/models/test_models_chatopenai_adapter_contract.py.
This file pins OpenRouter-specific defaults and the `openai_api_key` kwarg quirk
(only adapter that uses that name instead of `api_key`).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hivetracered.models import langchain_model as lm
from hivetracered.models import openrouter_model as orm
from hivetracered.models.openrouter_model import OpenRouterModel


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def fake_chat_openai(monkeypatch):
    instance = MagicMock(name="ChatOpenAI-instance")
    instance.with_retry.return_value = instance
    cls = MagicMock(name="ChatOpenAI-class", return_value=instance)
    monkeypatch.setattr(orm, "ChatOpenAI", cls)
    return cls


@pytest.fixture
def fake_rate_limiter(monkeypatch):
    instance = MagicMock(name="InMemoryRateLimiter-instance")
    cls = MagicMock(name="InMemoryRateLimiter-class", return_value=instance)
    monkeypatch.setattr(lm, "InMemoryRateLimiter", cls)
    return cls


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch):
    monkeypatch.setattr(orm, "load_dotenv", lambda *a, **kw: False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


# ── Defaults specific to OpenRouterModel ────────────────────────────


def test_openrouter_default_model_name_is_nemotron(fake_chat_openai, fake_rate_limiter):
    model = OpenRouterModel()

    assert model.model_name == "nvidia/nemotron-nano-9b-v2"
    assert model.base_url == "https://openrouter.ai/api/v1"


# ── Quirk: kwarg name is `openai_api_key`, not `api_key` ────────────


def test_openrouter_does_not_pass_api_key_kwarg_to_chatopenai(fake_chat_openai, fake_rate_limiter, monkeypatch):
    """Quirk: OpenRouter uses `openai_api_key=` not `api_key=` (line 77)."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")

    OpenRouterModel()

    init_kwargs = fake_chat_openai.call_args.kwargs
    assert "api_key" not in init_kwargs


# ── ChatOpenAI wiring ───────────────────────────────────────────────


def test_openrouter_passes_args_to_chatopenai(fake_chat_openai, fake_rate_limiter):
    """Line 77: ChatOpenAI receives model, base_url, and **kwargs."""
    OpenRouterModel(model="meta-llama/llama-3", base_url="https://other-router/api/v1", max_tokens=999)

    init_kwargs = fake_chat_openai.call_args.kwargs
    assert init_kwargs["model"] == "meta-llama/llama-3"
    assert init_kwargs["base_url"] == "https://other-router/api/v1"
    assert init_kwargs["max_tokens"] == 999


# ── Rate limiter math ───────────────────────────────────────────────


def test_openrouter_rate_limiter_uses_rpm_per_60(fake_chat_openai, fake_rate_limiter):
    """Lines 73-76: InMemoryRateLimiter(requests_per_second=rpm/60, check_every_n_seconds=0.1)."""
    OpenRouterModel(rpm=300)

    rl_kwargs = fake_rate_limiter.call_args.kwargs
    assert rl_kwargs["requests_per_second"] == pytest.approx(5.0)  # 300/60
