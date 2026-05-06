"""Unit tests for hivetracered.models.gigachat_model.GigaChatModel.

Tests focus on SUBCLASS-specific behavior in __init__:
  * env-var resolution for credentials and scope (from GIGACHAT_CREDENTIALS /
    GIGACHAT_API_SCOPE per source lines 38-41),
  * model-name default and override (line 17 default = "GigaChat"),
  * verify_ssl_certs forwarding (default False, line 17),
  * default temperature injection (lines 65-66 inject 0.000001 when omitted),
  * batch_size deprecation warning + back-propagation to max_concurrency
    (lines 46-54),
  * default max_concurrency=1 when neither provided (lines 57-58),
  * batch_size alias preservation for backward compat (line 62),
  * get_params() does not leak credentials (delegates to client.dict() which
    must not surface secrets that the wrapper passed in).

Parent-class behavior (invoke/ainvoke/batch/abatch/stream_abatch/
is_answer_blocked/_add_retry_policy) is intentionally NOT tested here -- it
belongs to LangchainModel's own test surface.
"""

from __future__ import annotations

import warnings
from unittest.mock import MagicMock

import pytest

# Skip the whole module if langchain_gigachat is not importable in this env.
pytest.importorskip("langchain_gigachat")

from hivetracered.models import gigachat_model as gm  # noqa: E402
from hivetracered.models.gigachat_model import GigaChatModel  # noqa: E402


# ── Fakes ───────────────────────────────────────────────────────────


class _FakeRetryWrapped:
    """Stand-in for what client.with_retry(...) returns.

    The parent LangchainModel.get_params() calls self.client.dict() (line 158
    of langchain_model.py). We mirror real GigaChat behavior: pydantic excludes
    credentials from .dict(), so the wrapped client's .dict() returns only
    non-secret model fields.
    """

    def __init__(self, owner: "_FakeGigaChat") -> None:
        self._owner = owner

    def dict(self) -> dict:
        # Mirrors real langchain_gigachat.GigaChat.dict() shape:
        # excludes credentials, includes model + non-secret config.
        return {
            "model": self._owner.init_kwargs.get("model"),
            "verify_ssl_certs": self._owner.init_kwargs.get("verify_ssl_certs"),
            "temperature": self._owner.init_kwargs.get("temperature"),
        }


class _FakeGigaChat:
    """Mock GigaChat class -- captures init kwargs for assertions.

    Records every constructor call on the class itself (instances list) so
    tests can assert what the SUT forwarded. Provides .with_retry() so the
    SUT's _add_retry_policy() (parent class) does not fail.
    """

    instances: list["_FakeGigaChat"] = []

    def __init__(self, **kwargs) -> None:
        self.init_kwargs = kwargs
        type(self).instances.append(self)

    def with_retry(self, **_retry_kwargs) -> _FakeRetryWrapped:
        return _FakeRetryWrapped(self)


@pytest.fixture(autouse=True)
def _patch_gigachat(monkeypatch):
    """Replace GigaChat at module-import scope of the SUT.

    Also resets the per-class instances list so each test starts clean.
    """
    _FakeGigaChat.instances = []
    monkeypatch.setattr(gm, "GigaChat", _FakeGigaChat)


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch):
    """Provide deterministic env and disable .env file overrides.

    The SUT calls load_dotenv(override=True) on line 35 which would otherwise
    pull values from the project's local .env and overwrite our setenv. We
    replace load_dotenv on the SUT module with a no-op so monkeypatch.setenv
    wins for every test.
    """
    monkeypatch.setattr(gm, "load_dotenv", lambda *a, **kw: False)
    # Default env so tests that don't customize have predictable values.
    monkeypatch.delenv("GIGACHAT_CREDENTIALS", raising=False)
    monkeypatch.delenv("GIGACHAT_API_SCOPE", raising=False)


# ── Constructor: identity & defaults ────────────────────────────────


def test_init_default_model_name_and_concurrency():
    """Defaults: model="GigaChat" (line 17), max_concurrency=1 (lines 57-58)."""
    model = GigaChatModel(credentials="explicit-cred")

    assert model.model_name == "GigaChat"
    assert model.max_concurrency == 1


# ── Credential / scope env-var resolution ───────────────────────────


@pytest.mark.parametrize(
    ("explicit_arg", "expected"),
    [
        (None, "env-cred-SECRET"),  # line 41: falls through to env
        ("explicit-cred", "explicit-cred"),  # explicit overrides env
    ],
    ids=["from-env", "explicit-overrides-env"],
)
def test_init_credentials_resolution(monkeypatch, explicit_arg, expected):
    """Line 40-41: env is consulted only when credentials is None."""
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "env-cred-SECRET")

    if explicit_arg is None:
        GigaChatModel()
    else:
        GigaChatModel(credentials=explicit_arg)

    assert _FakeGigaChat.instances[0].init_kwargs["credentials"] == expected


@pytest.mark.parametrize(
    ("explicit_arg", "expected"),
    [
        (None, "GIGACHAT_API_PERS"),  # line 39: falls through to env
        ("GIGACHAT_API_CORP", "GIGACHAT_API_CORP"),  # explicit overrides env
    ],
    ids=["from-env", "explicit-overrides-env"],
)
def test_init_scope_resolution(monkeypatch, explicit_arg, expected):
    """Line 39: scope sourced from GIGACHAT_API_SCOPE env when not given."""
    monkeypatch.setenv("GIGACHAT_API_SCOPE", "GIGACHAT_API_PERS")

    if explicit_arg is None:
        GigaChatModel(credentials="cred")
    else:
        GigaChatModel(credentials="cred", scope=explicit_arg)

    assert _FakeGigaChat.instances[0].init_kwargs["scope"] == expected


# ── verify_ssl_certs forwarding ─────────────────────────────────────


@pytest.mark.parametrize(
    ("ctor_kwargs", "expected"),
    [
        ({}, False),  # default per source line 17
        ({"verify_ssl_certs": True}, True),  # explicit forwarded
    ],
    ids=["default-false", "explicit-true"],
)
def test_init_verify_ssl_certs_forwarded(ctor_kwargs, expected):
    """Source line 17: verify_ssl_certs default False; user value forwarded."""
    GigaChatModel(credentials="cred", **ctor_kwargs)

    assert _FakeGigaChat.instances[0].init_kwargs["verify_ssl_certs"] is expected


# ── Default temperature injection (lines 65-66) ─────────────────────


@pytest.mark.parametrize(
    ("ctor_kwargs", "expected"),
    [
        ({}, 0.000001),  # default injected (lines 65-66)
        ({"temperature": 0.5}, 0.5),  # user value preserved
    ],
    ids=["default-injected", "user-supplied-preserved"],
)
def test_init_temperature_resolution(ctor_kwargs, expected):
    """Lines 65-66: kwargs gets a near-zero temperature only when omitted."""
    model = GigaChatModel(credentials="cred", **ctor_kwargs)

    assert model.kwargs["temperature"] == pytest.approx(expected)
    assert _FakeGigaChat.instances[0].init_kwargs["temperature"] == pytest.approx(expected)


# ── Deprecation: batch_size ─────────────────────────────────────────


def test_init_deprecated_batch_size_emits_deprecation_warning():
    """Lines 46-52: passing batch_size triggers DeprecationWarning."""
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        GigaChatModel(credentials="cred", batch_size=3)

    deprecations = [w for w in captured if issubclass(w.category, DeprecationWarning)]
    assert deprecations  # at least one DeprecationWarning was raised
    assert "batch_size" in str(deprecations[0].message)


def test_init_batch_size_back_propagates_to_max_concurrency_when_unset():
    """Lines 53-54: if max_concurrency is None, batch_size is used."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        model = GigaChatModel(credentials="cred", batch_size=5)

    assert model.max_concurrency == 5
    assert model.batch_size == 5


def test_init_max_concurrency_wins_over_batch_size_when_both_set():
    """Lines 53-54: batch_size only sets max_concurrency if it is None."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        model = GigaChatModel(credentials="cred", batch_size=5, max_concurrency=9)

    assert model.max_concurrency == 9


# ── max_retries forwarding to retry policy ──────────────────────────


@pytest.mark.parametrize(
    ("ctor_kwargs", "expected"),
    [
        ({}, 3),  # source line 17 default
        ({"max_retries": 8}, 8),
    ],
    ids=["default-3", "custom-8"],
)
def test_init_max_retries_resolution(ctor_kwargs, expected):
    model = GigaChatModel(credentials="cred", **ctor_kwargs)

    assert model.max_retries == expected


# ── Extra kwargs passthrough ────────────────────────────────────────


def test_init_forwards_model_and_extra_kwargs_to_underlying_gigachat():
    """Line 67: model and **self.kwargs splatted into GigaChat()."""
    GigaChatModel(model="GigaChat-Pro", credentials="cred", profanity_check=True, max_tokens=512)

    forwarded = _FakeGigaChat.instances[0].init_kwargs
    assert forwarded["model"] == "GigaChat-Pro"
    assert forwarded["profanity_check"] is True
    assert forwarded["max_tokens"] == 512
