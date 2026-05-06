"""Unit tests for hivetracered.models.llamacpp_model.LlamaCppModel.

Tests focus on SUBCLASS-specific behavior in __init__:
  * model_path validation: FileNotFoundError when path missing (lines 104-108),
  * model_name format: "llamacpp:<basename>" (line 81),
  * forwarding of n_ctx / n_gpu_layers / n_batch / n_threads to ChatLlamaCpp,
  * multiprocessing.cpu_count() used for default n_threads (lines 117-118),
  * default temperature injection 0.000001 when omitted (lines 113-114),
  * batch_size deprecation warning + back-propagation (lines 85-93),
  * default max_concurrency=1 fallback (lines 96-97),
  * batch_size alias preservation (line 101),
  * get_params() returns batch_size + max_concurrency keys.

Parent-class behavior (invoke/ainvoke/batch/abatch/stream_abatch/
is_answer_blocked/_add_retry_policy) is intentionally NOT tested -- it lives
on LangchainModel.

Real-model loading is impossible in CI: ChatLlamaCpp would attempt to mmap a
GGUF file. Mocking is mandatory.
"""

from __future__ import annotations

import warnings

import pytest

# Skip this module if langchain_community is not importable.
pytest.importorskip("langchain_community")

from hivetracered.models import llamacpp_model as lm  # noqa: E402
from hivetracered.models.llamacpp_model import LlamaCppModel  # noqa: E402


# ── Fakes ───────────────────────────────────────────────────────────


class _FakeRetryWrapped:
    """Stand-in for the object client.with_retry(...) returns.

    Parent get_params() calls self.client.dict(); we expose a small subset of
    fields drawn from the captured constructor kwargs to keep parity with what
    a real pydantic-based ChatLlamaCpp would surface.
    """

    def __init__(self, owner: "_FakeChatLlamaCpp") -> None:
        self._owner = owner

    def dict(self) -> dict:
        kw = self._owner.init_kwargs
        return {
            "model_path": kw.get("model_path"),
            "n_ctx": kw.get("n_ctx"),
            "n_gpu_layers": kw.get("n_gpu_layers"),
            "n_batch": kw.get("n_batch"),
            "n_threads": kw.get("n_threads"),
            "temperature": kw.get("temperature"),
        }


class _FakeChatLlamaCpp:
    """Mock ChatLlamaCpp class. Captures init kwargs without loading any GGUF."""

    instances: list["_FakeChatLlamaCpp"] = []

    def __init__(self, **kwargs) -> None:
        self.init_kwargs = kwargs
        type(self).instances.append(self)

    def with_retry(self, **_retry_kwargs) -> _FakeRetryWrapped:
        return _FakeRetryWrapped(self)


@pytest.fixture(autouse=True)
def _patch_chat_llamacpp(monkeypatch):
    """Replace ChatLlamaCpp at module-import scope of the SUT."""
    _FakeChatLlamaCpp.instances = []
    monkeypatch.setattr(lm, "ChatLlamaCpp", _FakeChatLlamaCpp)


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch):
    """Disable .env file overrides (SUT calls load_dotenv(override=True), line 80)."""
    monkeypatch.setattr(lm, "load_dotenv", lambda *a, **kw: False)


@pytest.fixture
def fake_model_file(tmp_path):
    """Create a real (empty) file so the FileNotFoundError gate (line 104) passes."""
    path = tmp_path / "test-model.gguf"
    path.write_bytes(b"")  # Existence is what's checked; contents are not validated.
    return str(path)


# ── Validation: model_path must exist ───────────────────────────────


def test_init_raises_file_not_found_before_client_construction(tmp_path):
    """Lines 104-108: os.path.exists check raises FileNotFoundError BEFORE
    ChatLlamaCpp(...) is invoked. Otherwise a real env would mmap a non-existent file.
    """
    missing = tmp_path / "does-not-exist.gguf"

    with pytest.raises(FileNotFoundError, match=r"Model file not found"):
        LlamaCppModel(model_path=str(missing))

    assert _FakeChatLlamaCpp.instances == []  # client never built


# ── Identity & model_name ───────────────────────────────────────────


def test_init_model_name_is_basename_prefixed(fake_model_file):
    """Line 81: self.model_name = f"llamacpp:{os.path.basename(model_path)}";
    line 120: model_path forwarded verbatim to ChatLlamaCpp."""
    model = LlamaCppModel(model_path=fake_model_file)

    # fake_model_file ends in 'test-model.gguf' (defined in fixture).
    assert model.model_name == "llamacpp:test-model.gguf"
    assert _FakeChatLlamaCpp.instances[0].init_kwargs["model_path"] == fake_model_file


# ── Forwarding of llama.cpp tunables ────────────────────────────────


@pytest.mark.parametrize(
    ("kwarg_name", "ctor_kwargs", "expected"),
    [
        ("n_ctx", {}, 10000),  # line 30 default
        ("n_ctx", {"n_ctx": 4096}, 4096),
        ("n_gpu_layers", {}, -1),  # line 31 default = auto-detect
        ("n_gpu_layers", {"n_gpu_layers": 32}, 32),
        ("n_batch", {}, 512),  # line 32 default
    ],
    ids=["n_ctx-default", "n_ctx-explicit", "n_gpu_layers-default", "n_gpu_layers-explicit", "n_batch-default"],
)
def test_init_forwards_llama_tunables_to_chat_llamacpp(fake_model_file, kwarg_name, ctor_kwargs, expected):
    """Lines 30-32: defaults; user overrides forwarded verbatim."""
    LlamaCppModel(model_path=fake_model_file, **ctor_kwargs)

    assert _FakeChatLlamaCpp.instances[0].init_kwargs[kwarg_name] == expected


# ── multiprocessing.cpu_count() default for n_threads ───────────────


@pytest.mark.parametrize(
    ("cpu_count", "expected_n_threads"),
    [(8, 7), (1, 1)],  # normal case, floor case
    ids=["cpu_count=8", "cpu_count=1-floored-to-1"],
)
def test_init_default_n_threads_uses_cpu_count_minus_one_with_floor(
    fake_model_file, monkeypatch, cpu_count, expected_n_threads
):
    """Lines 117-118: n_threads = max(1, cpu_count() - 1)."""
    monkeypatch.setattr(lm.multiprocessing, "cpu_count", lambda: cpu_count)

    LlamaCppModel(model_path=fake_model_file)

    assert _FakeChatLlamaCpp.instances[0].init_kwargs["n_threads"] == expected_n_threads


def test_init_explicit_n_threads_skips_cpu_count_branch(fake_model_file, monkeypatch):
    """Lines 117-118: cpu_count() is only consulted when n_threads is None."""

    def _boom() -> int:
        raise AssertionError("cpu_count must NOT be called when n_threads is given")

    monkeypatch.setattr(lm.multiprocessing, "cpu_count", _boom)

    LlamaCppModel(model_path=fake_model_file, n_threads=4)

    assert _FakeChatLlamaCpp.instances[0].init_kwargs["n_threads"] == 4


# ── Default temperature injection (lines 113-114) ───────────────────


@pytest.mark.parametrize(
    ("ctor_kwargs", "expected"),
    [
        ({}, 0.000001),  # default injected (lines 113-114)
        ({"temperature": 0.7}, 0.7),  # user value preserved
    ],
    ids=["default-injected", "user-supplied-preserved"],
)
def test_init_temperature_resolution(fake_model_file, ctor_kwargs, expected):
    model = LlamaCppModel(model_path=fake_model_file, **ctor_kwargs)

    assert model.kwargs["temperature"] == pytest.approx(expected)


# ── max_concurrency / batch_size ────────────────────────────────────


@pytest.mark.parametrize(
    ("ctor_kwargs", "expected"),
    [
        ({}, 1),  # lines 96-97: default 1 when neither given
        ({"max_concurrency": 3}, 3),  # explicit preserved
    ],
    ids=["default-1", "explicit-3"],
)
def test_init_max_concurrency_resolution(fake_model_file, ctor_kwargs, expected):
    """Lines 96-97 + 101: max_concurrency value flows to batch_size alias."""
    model = LlamaCppModel(model_path=fake_model_file, **ctor_kwargs)

    assert model.max_concurrency == expected


# ── Deprecation: batch_size ─────────────────────────────────────────


def test_init_deprecated_batch_size_emits_deprecation_warning(fake_model_file):
    """Lines 85-91: passing batch_size triggers DeprecationWarning."""
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        LlamaCppModel(model_path=fake_model_file, batch_size=2)

    deprecations = [w for w in captured if issubclass(w.category, DeprecationWarning)]
    assert deprecations  # at least one DeprecationWarning was raised
    assert "batch_size" in str(deprecations[0].message)


def test_init_batch_size_back_propagates_to_max_concurrency_when_unset(fake_model_file):
    """Lines 92-93: max_concurrency picks up batch_size only when it is None."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        model = LlamaCppModel(model_path=fake_model_file, batch_size=4)

    assert model.max_concurrency == 4
    assert model.batch_size == 4


def test_init_max_concurrency_wins_over_batch_size_when_both_set(fake_model_file):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        model = LlamaCppModel(model_path=fake_model_file, batch_size=2, max_concurrency=9)

    assert model.max_concurrency == 9


# ── max_retries forwarding ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("ctor_kwargs", "expected"),
    [({}, 3), ({"max_retries": 7}, 7)],
    ids=["default-3", "custom-7"],
)
def test_init_max_retries_resolution(fake_model_file, ctor_kwargs, expected):
    model = LlamaCppModel(model_path=fake_model_file, **ctor_kwargs)

    assert model.max_retries == expected


# ── Extra kwargs passthrough ────────────────────────────────────────


def test_init_forwards_extra_kwargs_to_chat_llamacpp(fake_model_file):
    """Line 125: **self.kwargs is splatted into ChatLlamaCpp()."""
    LlamaCppModel(model_path=fake_model_file, top_p=0.95, max_tokens=256)

    forwarded = _FakeChatLlamaCpp.instances[0].init_kwargs
    assert forwarded["top_p"] == pytest.approx(0.95)
    assert forwarded["max_tokens"] == 256


