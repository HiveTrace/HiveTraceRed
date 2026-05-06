"""Unit tests for hivetracered.models.cloud_ru_model.CloudRuModel — adapter-specific.

Shared adapter contract tests live in tests/models/test_models_chatopenai_adapter_contract.py.
This file pins CloudRu-specific defaults, the rpm-floor quirk, and the
max_bucket_size wiring (none of which the other ChatOpenAI adapters share).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hivetracered.models import cloud_ru_model as cm
from hivetracered.models.cloud_ru_model import CloudRuModel


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def fake_chat_openai(monkeypatch):
    instance = MagicMock(name="ChatOpenAI-instance")
    instance.with_retry.return_value = instance
    cls = MagicMock(name="ChatOpenAI-class", return_value=instance)
    monkeypatch.setattr(cm, "ChatOpenAI", cls)
    return cls


@pytest.fixture
def fake_rate_limiter(monkeypatch):
    instance = MagicMock(name="InMemoryRateLimiter-instance")
    cls = MagicMock(name="InMemoryRateLimiter-class", return_value=instance)
    monkeypatch.setattr(cm, "InMemoryRateLimiter", cls)
    return cls


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch):
    monkeypatch.setattr(cm, "load_dotenv", lambda *a, **kw: False)
    monkeypatch.delenv("SBER_CLOUD_API_KEY", raising=False)


# ── Defaults specific to CloudRuModel ────────────────────────────────


def test_cloud_ru_default_model_is_gigachat_max(fake_chat_openai, fake_rate_limiter):
    model = CloudRuModel()

    assert model.model_name == "GigaChat/GigaChat-2-Max"


# ── ChatOpenAI wiring (default base_url + override) ─────────────────


def test_cloud_ru_passes_args_to_chatopenai(fake_chat_openai, fake_rate_limiter):
    """ChatOpenAI receives model, base_url (default + override), rate_limiter, and **kwargs."""
    # Default base_url branch
    CloudRuModel(max_tokens=256, top_p=0.9)
    init_kwargs = fake_chat_openai.call_args.kwargs
    assert init_kwargs["model"] == "GigaChat/GigaChat-2-Max"
    assert init_kwargs["base_url"] == "https://foundation-models.api.cloud.ru/v1"
    assert init_kwargs["rate_limiter"] is fake_rate_limiter.return_value
    assert init_kwargs["max_tokens"] == 256
    assert init_kwargs["top_p"] == pytest.approx(0.9)

    # Override branch
    CloudRuModel(model="GigaChat/Pro", base_url="https://override.example/v1")
    init_kwargs = fake_chat_openai.call_args.kwargs
    assert init_kwargs["model"] == "GigaChat/Pro"
    assert init_kwargs["base_url"] == "https://override.example/v1"


# ── Rate limiter quirks (max(1,rpm)/60 floor + max_bucket_size) ─────


@pytest.mark.parametrize(
    ("ctor_kwargs", "expected_rps"),
    [
        ({}, 1.0),  # default rpm=60 → 60/60 = 1.0
        ({"rpm": 0}, 1.0 / 60.0),  # max(1, 0)/60 — floor to 1
    ],
    ids=["default-rpm-60", "rpm-zero-floored-to-one"],
)
def test_cloud_ru_rate_limiter_rps_resolution(fake_chat_openai, fake_rate_limiter, ctor_kwargs, expected_rps):
    """Line 78: max(1, rpm)/60 — covers both default and floor branches (CloudRu-specific)."""
    CloudRuModel(**ctor_kwargs)

    rl_kwargs = fake_rate_limiter.call_args.kwargs
    assert rl_kwargs["requests_per_second"] == pytest.approx(expected_rps)


def test_cloud_ru_rate_limiter_uses_max_bucket_size_from_max_concurrency(fake_chat_openai, fake_rate_limiter):
    """Line 80: max_bucket_size=self.max_concurrency (CloudRu-specific)."""
    CloudRuModel(max_concurrency=4)

    rl_kwargs = fake_rate_limiter.call_args.kwargs
    assert rl_kwargs["max_bucket_size"] == 4
