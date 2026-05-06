"""Shared contract tests across the four ChatOpenAI-based adapters.

OpenAIModel, CloudRuModel, OpenRouterModel, and VLLMModel each construct a
ChatOpenAI client (with optional rate-limiter and retry-wrapping) and resolve
their API key from a per-adapter env var. This file consolidates the shared
tests where the only variation is (module, class, env var name, kwarg name,
whether a rate limiter is wired). Adapter-specific quirks (default model name,
quirky kwarg names, rate-limiter math, required ctor args) live in each
adapter's own file.
"""

from __future__ import annotations

import warnings
from types import ModuleType
from typing import Any, Dict, Optional, Tuple
from unittest.mock import MagicMock

import pytest

from hivetracered.models import (
    cloud_ru_model as cm,
    openai_model as om,
    openrouter_model as orm,
    vllm_model as vm,
)
from hivetracered.models.cloud_ru_model import CloudRuModel
from hivetracered.models.openai_model import OpenAIModel
from hivetracered.models.openrouter_model import OpenRouterModel
from hivetracered.models.vllm_model import VLLMModel


def _setup_adapter(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    env_var: str,
    has_rate_limiter: bool,
) -> Tuple[MagicMock, Optional[MagicMock]]:
    """Patch ChatOpenAI, optional InMemoryRateLimiter, and load_dotenv on the
    adapter's module; clear its env var. Returns the patched class mocks so
    tests can assert init kwargs.
    """
    chat_instance = MagicMock(name="ChatOpenAI-instance")
    chat_instance.with_retry.return_value = chat_instance
    fake_chat = MagicMock(name="ChatOpenAI-class", return_value=chat_instance)
    monkeypatch.setattr(module, "ChatOpenAI", fake_chat)

    fake_rate_limiter: Optional[MagicMock] = None
    if has_rate_limiter:
        rl_instance = MagicMock(name="InMemoryRateLimiter-instance")
        fake_rate_limiter = MagicMock(name="InMemoryRateLimiter-class", return_value=rl_instance)
        monkeypatch.setattr(module, "InMemoryRateLimiter", fake_rate_limiter)

    monkeypatch.setattr(module, "load_dotenv", lambda *a, **kw: False)
    monkeypatch.delenv(env_var, raising=False)

    return fake_chat, fake_rate_limiter


# Parametrize row shape: (model_cls, module, env_var, key_kwarg_name, has_rate_limiter, ctor_required_kwargs)
ADAPTERS = [
    pytest.param(OpenAIModel,     om,  "OPENAI_API_KEY",     "api_key",        True,  {},               id="openai"),
    pytest.param(CloudRuModel,    cm,  "SBER_CLOUD_API_KEY", "api_key",        True,  {},               id="cloud_ru"),
    pytest.param(OpenRouterModel, orm, "OPENROUTER_API_KEY", "openai_api_key", True,  {},               id="openrouter"),
    pytest.param(VLLMModel,       vm,  "VLLM_API_KEY",       "api_key",        False, {"model": "m"},   id="vllm"),
]


# ── default_max_concurrency_is_one ─────────────────────────────────────


@pytest.mark.parametrize(
    ("model_cls", "module", "env_var", "key_kwarg_name", "has_rate_limiter", "ctor_required_kwargs"),
    ADAPTERS,
)
def test_default_max_concurrency_is_one(
    monkeypatch, model_cls, module, env_var, key_kwarg_name, has_rate_limiter, ctor_required_kwargs
):
    _setup_adapter(monkeypatch, module, env_var, has_rate_limiter)

    model = model_cls(**ctor_required_kwargs)

    assert model.max_concurrency == 1


# ── temperature_resolution ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("model_cls", "module", "env_var", "key_kwarg_name", "has_rate_limiter", "ctor_required_kwargs"),
    ADAPTERS,
)
@pytest.mark.parametrize(
    ("extra_kwargs", "expected_temp"),
    [
        ({}, 0.000001),  # default near-zero injected when omitted
        ({"temperature": 0.42}, 0.42),  # user value preserved
    ],
    ids=["default-injected", "user-supplied-preserved"],
)
def test_temperature_resolution(
    monkeypatch, model_cls, module, env_var, key_kwarg_name, has_rate_limiter,
    ctor_required_kwargs, extra_kwargs, expected_temp,
):
    _setup_adapter(monkeypatch, module, env_var, has_rate_limiter)

    model = model_cls(**ctor_required_kwargs, **extra_kwargs)

    assert model.kwargs["temperature"] == pytest.approx(expected_temp, abs=1e-12)


# ── api_key_resolution: env-var fallback + explicit override ───────────


@pytest.mark.parametrize(
    ("model_cls", "module", "env_var", "key_kwarg_name", "has_rate_limiter", "ctor_required_kwargs"),
    ADAPTERS,
)
@pytest.mark.parametrize(
    ("explicit_arg", "env_value", "expected"),
    [
        (None, "ENV-SECRET", "ENV-SECRET"),  # falls through to env var
        ("explicit-key", "ENV-SECRET", "explicit-key"),  # explicit overrides env
    ],
    ids=["from-env", "explicit-overrides-env"],
)
def test_api_key_resolution(
    monkeypatch, model_cls, module, env_var, key_kwarg_name, has_rate_limiter,
    ctor_required_kwargs, explicit_arg, env_value, expected,
):
    fake_chat, _ = _setup_adapter(monkeypatch, module, env_var, has_rate_limiter)
    monkeypatch.setenv(env_var, env_value)

    ctor_kwargs: Dict[str, Any] = dict(ctor_required_kwargs)
    if explicit_arg is not None:
        ctor_kwargs["api_key"] = explicit_arg
    model_cls(**ctor_kwargs)

    init_kwargs = fake_chat.call_args.kwargs
    assert init_kwargs[key_kwarg_name] == expected


# ── wraps_client_with_retry_policy ─────────────────────────────────────


@pytest.mark.parametrize(
    ("model_cls", "module", "env_var", "key_kwarg_name", "has_rate_limiter", "ctor_required_kwargs"),
    ADAPTERS,
)
def test_wraps_client_with_retry_policy(
    monkeypatch, model_cls, module, env_var, key_kwarg_name, has_rate_limiter, ctor_required_kwargs
):
    fake_chat, _ = _setup_adapter(monkeypatch, module, env_var, has_rate_limiter)

    model_cls(**ctor_required_kwargs, max_retries=5)

    instance = fake_chat.return_value
    instance.with_retry.assert_called_once()
    assert instance.with_retry.call_args.kwargs["stop_after_attempt"] == 5


# ── batch_size deprecation warning + back-propagation to max_concurrency ─


@pytest.mark.parametrize(
    ("model_cls", "module", "env_var", "key_kwarg_name", "has_rate_limiter", "ctor_required_kwargs"),
    ADAPTERS,
)
def test_batch_size_emits_deprecation_warning(
    monkeypatch, model_cls, module, env_var, key_kwarg_name, has_rate_limiter, ctor_required_kwargs
):
    _setup_adapter(monkeypatch, module, env_var, has_rate_limiter)

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        model_cls(**ctor_required_kwargs, batch_size=4)

    deprecations = [w for w in captured if issubclass(w.category, DeprecationWarning)]
    assert deprecations
    assert "batch_size" in str(deprecations[0].message)


@pytest.mark.parametrize(
    ("model_cls", "module", "env_var", "key_kwarg_name", "has_rate_limiter", "ctor_required_kwargs"),
    ADAPTERS,
)
def test_batch_size_back_propagates_to_max_concurrency(
    monkeypatch, model_cls, module, env_var, key_kwarg_name, has_rate_limiter, ctor_required_kwargs
):
    _setup_adapter(monkeypatch, module, env_var, has_rate_limiter)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        model = model_cls(**ctor_required_kwargs, batch_size=7)

    assert model.max_concurrency == 7
    assert model.batch_size == 7
