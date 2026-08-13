# pyright: reportUnusedParameter=false, reportUnusedFunction=false
"""verify_ssl wiring tests for httpx-based models.

Pins that verify_ssl=False / CA-bundle-path reaches the underlying HTTP client
for every model that supports it, and that the default (True) leaves the SDK's
own client construction untouched.
"""

from __future__ import annotations

import ssl
from unittest.mock import MagicMock

import certifi
import httpx
import pytest

from hivetracered.models.langchain_model import LangchainModel


def test_httpx_clients_default_is_empty():
    assert LangchainModel._httpx_clients(True) == {}


@pytest.mark.parametrize("verify", [False, certifi.where()])
def test_httpx_clients_builds_clients(verify):
    clients = LangchainModel._httpx_clients(verify)
    assert isinstance(clients["http_client"], httpx.Client)
    assert isinstance(clients["http_async_client"], httpx.AsyncClient)


def test_ssl_verify_normalizes_ca_path_to_context():
    assert LangchainModel._ssl_verify(False) is False
    assert LangchainModel._ssl_verify(True) is True
    assert isinstance(LangchainModel._ssl_verify(certifi.where()), ssl.SSLContext)


def _fake_chat_cls(monkeypatch, module, attr):
    instance = MagicMock()
    instance.with_retry.return_value = instance
    cls = MagicMock(return_value=instance)
    monkeypatch.setattr(module, attr, cls)
    monkeypatch.setattr(module, "load_dotenv", lambda *a, **kw: False)
    return cls


@pytest.mark.parametrize("mod_name", ["openai_model", "openrouter_model", "cloud_ru_model", "vllm_model"])
def test_chatopenai_models_pass_httpx_clients(monkeypatch, mod_name):
    import importlib
    module = importlib.import_module(f"hivetracered.models.{mod_name}")
    cls = _fake_chat_cls(monkeypatch, module, "ChatOpenAI")
    model_cls = next(
        v for v in vars(module).values()
        if isinstance(v, type) and issubclass(v, LangchainModel) and v is not LangchainModel
    )

    model_cls(model="m", api_key="k", verify_ssl=False)
    kwargs = cls.call_args.kwargs
    assert isinstance(kwargs["http_client"], httpx.Client)
    assert isinstance(kwargs["http_async_client"], httpx.AsyncClient)

    cls.reset_mock()
    model_cls(model="m", api_key="k")
    kwargs = cls.call_args.kwargs
    assert "http_client" not in kwargs
    assert "http_async_client" not in kwargs


def test_gemini_model_passes_client_args(monkeypatch):
    from hivetracered.models import gemini_model as gm
    cls = _fake_chat_cls(monkeypatch, gm, "ChatGoogleGenerativeAI")

    gm.GeminiModel(verify_ssl=False)
    assert cls.call_args.kwargs["client_args"] == {"verify": False}

    cls.reset_mock()
    gm.GeminiModel()
    assert "client_args" not in cls.call_args.kwargs


def test_ollama_model_passes_client_kwargs(monkeypatch):
    from hivetracered.models import ollama_model as om
    cls = _fake_chat_cls(monkeypatch, om, "ChatOllama")

    om.OllamaModel(verify_ssl=certifi.where())
    verify = cls.call_args.kwargs["client_kwargs"]["verify"]
    assert isinstance(verify, ssl.SSLContext)

    cls.reset_mock()
    om.OllamaModel()
    assert "client_kwargs" not in cls.call_args.kwargs


def test_gemini_native_model_passes_http_options(monkeypatch):
    from hivetracered.models import gemini_native_model as gnm
    client_cls = MagicMock()
    monkeypatch.setattr(gnm.genai, "Client", client_cls)
    monkeypatch.setattr(gnm, "load_dotenv", lambda *a, **kw: False)
    monkeypatch.setenv("GOOGLE_API_KEY", "k")

    gnm.GeminiNativeModel(verify_ssl=False)
    http_options = client_cls.call_args.kwargs["http_options"]
    assert http_options.client_args == {"verify": False}
    assert http_options.async_client_args == {"verify": False}

    client_cls.reset_mock()
    gnm.GeminiNativeModel()
    assert client_cls.call_args.kwargs == {}
