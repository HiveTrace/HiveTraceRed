"""Unit tests for hivetracered.models.vllm_model.VLLMModel — adapter-specific.

Shared adapter contract tests live in tests/models/test_models_chatopenai_adapter_contract.py.
VLLMModel quirks: `model` is a required ctor arg (no default), default base_url
points at localhost, and there is NO rate limiter / no rpm parameter — none of
which the other ChatOpenAI adapters share.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hivetracered.models import vllm_model as vm
from hivetracered.models.vllm_model import VLLMModel


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def fake_chat_openai(monkeypatch):
    instance = MagicMock(name="ChatOpenAI-instance")
    instance.with_retry.return_value = instance
    cls = MagicMock(name="ChatOpenAI-class", return_value=instance)
    monkeypatch.setattr(vm, "ChatOpenAI", cls)
    return cls


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch):
    monkeypatch.setattr(vm, "load_dotenv", lambda *a, **kw: False)
    monkeypatch.delenv("VLLM_BASE_URL", raising=False)
    monkeypatch.delenv("VLLM_API_KEY", raising=False)


# ── Required-arg gate ───────────────────────────────────────────────


def test_vllm_model_argument_is_required(fake_chat_openai):
    """The signature has no default for `model` (line 26)."""
    with pytest.raises(TypeError):
        VLLMModel()


def test_vllm_records_model_name_and_max_retries(fake_chat_openai):
    model = VLLMModel(model="meta-llama/Llama-2-7b-chat-hf", max_retries=2)

    assert model.model_name == "meta-llama/Llama-2-7b-chat-hf"
    assert model.max_retries == 2


# ── ChatOpenAI wiring (no rate_limiter) ─────────────────────────────


def test_vllm_chatopenai_wiring(fake_chat_openai):
    """Lines 73-78: ChatOpenAI receives model, base_url (default+override), kwargs; no rate_limiter."""
    # Default base_url branch + extra kwargs
    VLLMModel(model="meta-llama/Llama-3", max_tokens=128)
    init_kwargs = fake_chat_openai.call_args.kwargs
    assert init_kwargs["model"] == "meta-llama/Llama-3"
    assert init_kwargs["base_url"] == "http://localhost:8000/v1"
    assert init_kwargs["max_tokens"] == 128
    assert "rate_limiter" not in init_kwargs

    # base_url override branch
    VLLMModel(model="m", base_url="http://gpu-host:8000/v1")
    init_kwargs = fake_chat_openai.call_args.kwargs
    assert init_kwargs["base_url"] == "http://gpu-host:8000/v1"
