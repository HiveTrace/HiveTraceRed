"""Unit tests for hivetracered.models.yandex_model.YandexGPTModel.

The SUT integrates the Yandex AI Studio SDK and exposes the project's Model
contract. Tests mock the SDK at the architectural seam: the AIStudio class
factory and the chained client object it returns. No real network calls are
made; asyncio.sleep is patched so async batch loops complete instantly.
"""

from __future__ import annotations

import asyncio
import warnings
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import MagicMock

import pytest

# Skip the whole module if the Yandex SDK isn't importable in this env.
pytest.importorskip("yandex_ai_studio_sdk")
pytest.importorskip("grpc")

from grpc import StatusCode  # noqa: E402
from grpc.aio import AioRpcError  # noqa: E402
from grpc.aio._metadata import Metadata  # noqa: E402

from hivetracered.models import yandex_model as ym  # noqa: E402
from hivetracered.models.yandex_model import (  # noqa: E402
    YANDEX_INTERNET_SEARCH_NOTICE,
    YandexGPTModel,
)
from tests.conftest import async_collect  # noqa: E402


# ── Helpers ─────────────────────────────────────────────────────────


def _fake_response(
    text: str = "hello world",
    role: str = "assistant",
    status: int = 1,
    input_tokens: int = 5,
    completion_tokens: int = 7,
    total_tokens: int = 12,
    model_version: str = "yandexgpt/1.0",
) -> SimpleNamespace:
    """Build a SimpleNamespace mimicking the SDK's response object shape.

    Shape derived from yandex_model._format_response (lines 113-141):
    response.alternatives[0].{text,role,status}, response.usage.{...}, response.model_version.
    """
    alt = SimpleNamespace(text=text, role=role, status=status)
    usage = SimpleNamespace(
        input_text_tokens=input_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
    return SimpleNamespace(
        alternatives=[alt],
        usage=usage,
        model_version=model_version,
    )


def _make_aio_rpc_error(message: str = "rpc-failed") -> AioRpcError:
    """Construct a real AioRpcError (the SUT catches this exact type)."""
    return AioRpcError(
        code=StatusCode.UNAVAILABLE,
        initial_metadata=Metadata(),
        trailing_metadata=Metadata(),
        details=message,
    )


@pytest.fixture
def mock_sdk(monkeypatch):
    """Replace AIStudio at module scope; return the chained client mock.

    The SUT does:
        sdk = AIStudio(folder_id=..., auth=..., retry_policy=...)
        self.client = sdk.models.completions(model_name).configure(**kwargs)
    We mock the AIStudio class so YandexGPTModel.__init__ obtains a MagicMock
    chain whose final .configure(...) return value is the test-controlled
    `client`. Tests reach into `client.run`, `client.run_deferred`, etc.
    """
    fake_aistudio_cls = MagicMock(name="AIStudioClass")
    sdk_instance = fake_aistudio_cls.return_value
    client = MagicMock(name="client")
    sdk_instance.models.completions.return_value.configure.return_value = client
    monkeypatch.setattr(ym, "AIStudio", fake_aistudio_cls)
    return SimpleNamespace(aistudio_cls=fake_aistudio_cls, client=client)


@pytest.fixture(autouse=True)
def _patch_asyncio_sleep(monkeypatch):
    """Replace asyncio.sleep on the SUT module so async batch loops are instant."""

    async def _instant(_seconds: float, *_, **__) -> None:
        return None

    monkeypatch.setattr(ym.asyncio, "sleep", _instant)


@pytest.fixture(autouse=True)
def _scrub_yandex_env(monkeypatch):
    """Provide deterministic dummy env.

    The SUT calls load_dotenv(override=True) which would otherwise pull values
    from the project's local .env and overwrite our monkeypatched env. Patch
    load_dotenv on the SUT module to a no-op so monkeypatch.setenv wins.
    """
    monkeypatch.setattr(ym, "load_dotenv", lambda *a, **kw: False)
    monkeypatch.setenv("YANDEX_FOLDER_ID", "test-folder-id")
    monkeypatch.setenv("YANDEX_GPT_API_KEY", "test-api-key-SECRET")


def _run(coro):
    """Run an async coroutine to completion (project uses no pytest-asyncio)."""
    return asyncio.new_event_loop().run_until_complete(coro)


# ── Constructor ─────────────────────────────────────────────────────


def test_init_default_model_name_is_yandexgpt(mock_sdk):
    """Default model="yandexgpt" (line 32); explicit forwarded to completions()."""
    model = YandexGPTModel()
    assert model.model_name == "yandexgpt"

    YandexGPTModel(model="yandexgpt-lite")
    mock_sdk.aistudio_cls.return_value.models.completions.assert_called_with("yandexgpt-lite")


@pytest.mark.parametrize(
    ("ctor_kwargs", "expected"),
    [({}, 10), ({"max_concurrency": 4}, 4)],
    ids=["default-10", "explicit-4"],
)
def test_init_max_concurrency_resolution(mock_sdk, ctor_kwargs, expected):
    """Lines 62-63 + 67: default 10; explicit override preserved; batch_size alias matches."""
    model = YandexGPTModel(**ctor_kwargs)

    assert model.max_concurrency == expected


def test_init_deprecated_batch_size_emits_warning_and_back_propagates(mock_sdk):
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        model = YandexGPTModel(batch_size=3)

    deprecations = [w for w in captured if issubclass(w.category, DeprecationWarning)]
    assert deprecations  # at least one DeprecationWarning was raised
    assert model.max_concurrency == 3  # batch_size flowed into max_concurrency


@pytest.mark.parametrize(
    ("ctor_kwargs", "expected"),
    [
        ({}, 0.000001),  # lines 71-72: default injected
        ({"temperature": 0.5}, 0.5),
    ],
    ids=["default-injected", "user-supplied-preserved"],
)
def test_init_temperature_resolution(mock_sdk, ctor_kwargs, expected):
    model = YandexGPTModel(**ctor_kwargs)

    assert model.kwargs["temperature"] == pytest.approx(expected)


def test_init_passes_env_credentials_to_aistudio(mock_sdk):
    """Lines 80-82: AIStudio receives folder_id and auth from env vars."""
    YandexGPTModel()

    kwargs = mock_sdk.aistudio_cls.call_args.kwargs
    assert kwargs["folder_id"] == "test-folder-id"
    assert kwargs["auth"] == "test-api-key-SECRET"


def test_init_configures_retry_policy_with_max_retries(mock_sdk):
    YandexGPTModel(max_retries=7)

    retry_policy = mock_sdk.aistudio_cls.call_args.kwargs["retry_policy"]
    assert retry_policy.max_attempts == 7  # passed as max_attempts, lines 75-77


def test_init_calls_configure_with_user_kwargs(mock_sdk):
    YandexGPTModel(temperature=0.2, max_tokens=500)

    completions_call = mock_sdk.aistudio_cls.return_value.models.completions.return_value
    configure_kwargs = completions_call.configure.call_args.kwargs
    assert configure_kwargs["temperature"] == pytest.approx(0.2)
    assert configure_kwargs["max_tokens"] == 500


# ── _format_prompt ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("hi there", [{"role": "user", "text": "hi there"}]),
        (
            [{"role": "human", "content": "ping"}],
            [{"role": "user", "text": "ping"}],
        ),
        (
            [
                {"role": "ai", "content": "from-ai"},
                {"role": "assistant", "content": "from-assistant"},
            ],
            [
                {"role": "assistant", "text": "from-ai"},
                {"role": "assistant", "text": "from-assistant"},
            ],
        ),
        (
            [
                {"role": "system", "content": "be helpful"},
                {"role": "user", "content": "go"},
            ],
            [
                {"role": "system", "text": "be helpful"},
                {"role": "user", "text": "go"},
            ],
        ),
        (
            [{"role": "tool", "content": "unsupported"}, {"role": "user", "content": "ok"}],
            [{"role": "user", "text": "ok"}],
        ),
    ],
    ids=["string-wraps-user", "human-to-user", "ai-and-assistant-roles", "system-kept", "unknown-role-dropped"],
)
def test_format_prompt_role_mapping(mock_sdk, prompt, expected):
    """Lines 99-110: string wraps into user; role aliases mapped; unknown roles skipped."""
    model = YandexGPTModel()

    assert model._format_prompt(prompt) == expected


# ── _format_response ────────────────────────────────────────────────


def test_format_response_surfaces_alternative_usage_and_model_version(mock_sdk):
    """Lines 113-141: format extracts text/role/status from alternatives[0],
    usage as dict, and model_version verbatim."""
    model = YandexGPTModel()

    formatted = model._format_response(
        _fake_response(
            text="t",
            role="assistant",
            status=1,
            input_tokens=11,
            completion_tokens=22,
            total_tokens=33,
            model_version="vX.Y",
        )
    )

    assert formatted["content"] == "t"
    assert formatted["role"] == "assistant"
    assert formatted["status"] == 1
    assert formatted["usage"] == {
        "input_text_tokens": 11,
        "completion_tokens": 22,
        "total_tokens": 33,
    }
    assert formatted["model_version"] == "vX.Y"


# ── invoke (sync) ───────────────────────────────────────────────────


def test_invoke_calls_client_run_with_formatted_prompt_and_returns_formatted_dict(mock_sdk):
    """Lines 153-155: invoke formats prompt, calls client.run, returns _format_response output."""
    mock_sdk.client.run.return_value = _fake_response(text="ok-1")
    model = YandexGPTModel()

    result = model.invoke("ping")

    assert result["content"] == "ok-1"
    mock_sdk.client.run.assert_called_once_with([{"role": "user", "text": "ping"}])


# ── ainvoke (async) ─────────────────────────────────────────────────


def test_ainvoke_uses_run_deferred_then_wait(mock_sdk):
    operation = MagicMock(name="operation")
    operation.wait.return_value = _fake_response(text="async-ok")
    mock_sdk.client.run_deferred.return_value = operation
    model = YandexGPTModel()

    result = _run(model.ainvoke("hi"))

    assert result["content"] == "async-ok"
    mock_sdk.client.run_deferred.assert_called_once_with([{"role": "user", "text": "hi"}])
    operation.wait.assert_called_once()


def test_ainvoke_returns_blocked_sentinel_on_aio_rpc_error(mock_sdk):
    """Lines 176-181: AioRpcError → exact sentinel; sentinel must satisfy is_answer_blocked."""
    mock_sdk.client.run_deferred.side_effect = _make_aio_rpc_error()
    model = YandexGPTModel()

    result = _run(model.ainvoke("hi"))

    assert result == {
        "content": YANDEX_INTERNET_SEARCH_NOTICE,
        "role": "assistant",
        "status": 4,
    }


# ── batch (sync) ────────────────────────────────────────────────────


def test_batch_returns_one_result_per_prompt_in_order(mock_sdk):
    mock_sdk.client.run.side_effect = [
        _fake_response(text="r0"),
        _fake_response(text="r1"),
        _fake_response(text="r2"),
    ]
    model = YandexGPTModel(max_concurrency=2)

    results = model.batch(["p0", "p1", "p2"])

    assert [r["content"] for r in results] == ["r0", "r1", "r2"]


def test_batch_sequential_path_when_max_concurrency_zero(mock_sdk):
    """Lines 197-201: max_concurrency==0 takes the sequential branch."""
    mock_sdk.client.run.side_effect = [
        _fake_response(text="seq-0"),
        _fake_response(text="seq-1"),
    ]
    model = YandexGPTModel(max_concurrency=0)

    results = model.batch(["a", "b"])

    assert [r["content"] for r in results] == ["seq-0", "seq-1"]
    assert mock_sdk.client.run.call_count == 2


# ── abatch (async) ──────────────────────────────────────────────────


def test_abatch_returns_responses_in_input_order(mock_sdk):
    op0 = MagicMock(name="op0")
    op0.get_result.return_value = _fake_response(text="a0")
    op1 = MagicMock(name="op1")
    op1.get_result.return_value = _fake_response(text="a1")
    op2 = MagicMock(name="op2")
    op2.get_result.return_value = _fake_response(text="a2")
    # last_operation status loop must terminate; the SUT polls .get_status().is_running.
    op2.get_status.return_value = SimpleNamespace(is_running=False)
    mock_sdk.client.run_deferred.side_effect = [op0, op1, op2]
    model = YandexGPTModel(max_concurrency=2)

    results = _run(model.abatch(["p0", "p1", "p2"]))

    assert [r["content"] for r in results] == ["a0", "a1", "a2"]


def test_abatch_substitutes_blocked_sentinel_on_aio_rpc_error(mock_sdk):
    op_ok = MagicMock(name="op_ok")
    op_ok.get_result.return_value = _fake_response(text="ok")
    op_ok.get_status.return_value = SimpleNamespace(is_running=False)
    # First run_deferred raises, second succeeds; sentinel must keep its slot.
    mock_sdk.client.run_deferred.side_effect = [_make_aio_rpc_error(), op_ok]
    model = YandexGPTModel(max_concurrency=2)

    results = _run(model.abatch(["bad", "good"]))

    assert results[0]["status"] == 4  # sentinel content for the failing slot
    assert results[0]["content"] == YANDEX_INTERNET_SEARCH_NOTICE
    assert results[1]["content"] == "ok"  # success preserved at original index


def test_abatch_empty_prompts_returns_empty_list(mock_sdk):
    model = YandexGPTModel(max_concurrency=2)

    results = _run(model.abatch([]))

    assert results == []  # no operations submitted, empty list returned


def test_abatch_polls_until_last_operation_completes(mock_sdk):
    """Lines 243-247: while is_running, the SUT polls via asyncio.sleep(0.1)."""
    op = MagicMock(name="op")
    op.get_result.return_value = _fake_response(text="done")
    # First poll reports running, second reports done -> exits loop after 1 sleep.
    op.get_status.side_effect = [
        SimpleNamespace(is_running=True),
        SimpleNamespace(is_running=False),
    ]
    mock_sdk.client.run_deferred.return_value = op
    model = YandexGPTModel(max_concurrency=1)

    results = _run(model.abatch(["only-prompt"]))

    assert results[0]["content"] == "done"
    # Status was polled twice (true, false); the body of the loop ran once.
    assert op.get_status.call_count == 2


# ── stream_abatch (async generator) ─────────────────────────────────


def test_stream_abatch_yields_one_record_per_prompt_in_order(mock_sdk):
    op0 = MagicMock(name="op0")
    op0.wait.return_value = _fake_response(text="s0")
    op1 = MagicMock(name="op1")
    op1.wait.return_value = _fake_response(text="s1")
    mock_sdk.client.run_deferred.side_effect = [op0, op1]
    model = YandexGPTModel(max_concurrency=4)

    results = async_collect(model.stream_abatch(["p0", "p1"]))

    assert [r["content"] for r in results] == ["s0", "s1"]


def test_stream_abatch_yields_error_sentinel_with_metadata_for_failed_prompt(mock_sdk):
    """Lines 309-317: on AioRpcError, stream_abatch yields a richer sentinel."""
    op_ok = MagicMock(name="op_ok")
    op_ok.wait.return_value = _fake_response(text="ok")
    err = _make_aio_rpc_error("submit-failure")
    mock_sdk.client.run_deferred.side_effect = [err, op_ok]
    model = YandexGPTModel(max_concurrency=4)

    results = async_collect(model.stream_abatch(["bad", "good"]))

    assert results[0]["status"] == 4
    assert results[0]["error_type"] == "AioRpcError"
    assert "submit-failure" in results[0]["error"]
    assert results[1]["content"] == "ok"


# ── is_answer_blocked ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "expected"),
    [(4, True), (1, False)],
    ids=["status-4-blocked", "status-1-ok"],
)
def test_is_answer_blocked_returns_true_only_for_status_four(mock_sdk, status, expected):
    model = YandexGPTModel()

    assert model.is_answer_blocked({"status": status}) is expected


# ── get_params ──────────────────────────────────────────────────────


def test_get_params_returns_model_name_batch_size_and_user_kwargs(mock_sdk):
    """Lines 278-282: get_params returns model_name, batch_size, **self.kwargs."""
    model = YandexGPTModel(model="yandexgpt-lite", max_concurrency=5, max_tokens=128)

    params = model.get_params()

    assert params["model_name"] == "yandexgpt-lite"
    assert params["batch_size"] == 5
    assert params["max_tokens"] == 128
