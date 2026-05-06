"""Unit tests for hivetracered.models.langchain_model.

LangchainModel is a generic, abstract wrapper around any LangChain BaseChatModel
or BaseLLM exposed as ``self.client``. ``__init__`` is abstract — concrete
subclasses are expected to set ``model_name``, ``max_concurrency``,
``batch_size``, ``max_retries``, ``kwargs`` and ``client`` themselves.

These tests instantiate a tiny concrete subclass that hands in a MagicMock /
AsyncMock LangChain client. The architectural seam being mocked is therefore
the LangChain client itself — never LangchainModel's own methods.

Coverage targets:
- _add_retry_policy: forwards correct kwargs to client.with_retry
- invoke / ainvoke: dict-conversion of returned message
- batch / abatch: config branching on max_concurrency, order preservation
- stream_abatch: input-order yielding + per-prompt error capture
- is_answer_blocked: finish_reason="blacklist" detection
- get_params: merges client.dict() with max_concurrency + batch_size
- BatchCallback: on_llm_end increments counter, sync + async context manager

Async tests use ``asyncio.new_event_loop().run_until_complete(...)`` because the
project does not depend on pytest-asyncio.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, List
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from hivetracered.models.langchain_model import BatchCallback, LangchainModel


# ── Helpers ──────────────────────────────────────────────────────────


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _async_collect(async_gen: AsyncGenerator) -> list:
    out = []
    async for item in async_gen:
        out.append(item)
    return out


def _msg(content: str = "hi", **extra) -> dict:
    """A LangChain BaseMessage-shaped object iterable as dict().

    LangchainModel does ``dict(response)`` — the cheapest stand-in is a real
    dict (which iterates as itself). Extra keys mirror BaseMessage fields the
    SUT may surface (e.g. ``response_metadata``).
    """
    base = {"content": content, "type": "ai", "response_metadata": {}}
    base.update(extra)
    return base


class _ConcreteLangchainModel(LangchainModel):
    """Minimal concrete subclass that bypasses the abstract __init__.

    LangchainModel.__init__ is decorated @abstractmethod, but its body is
    ``pass``. Subclasses are documented to set the required attributes
    themselves; we do exactly that, with an injected client mock.
    """

    def __init__(
        self,
        client: Any,
        *,
        model_name: str = "fake-model",
        max_concurrency: int = 0,
        max_retries: int = 3,
        **kwargs,
    ):
        self.client = client
        self.model_name = model_name
        self.max_concurrency = max_concurrency
        self.batch_size = max_concurrency
        self.max_retries = max_retries
        self.kwargs = kwargs


# ── Subclass-conformance / inheritance ──────────────────────────────


# ── _add_retry_policy ───────────────────────────────────────────────


def test_add_retry_policy_forwards_expected_kwargs_to_client_with_retry():
    raw_client = MagicMock(name="raw_client")
    wrapped = MagicMock(name="wrapped_client")
    raw_client.with_retry.return_value = wrapped
    model = _ConcreteLangchainModel(client=raw_client, max_retries=5)

    out = model._add_retry_policy(raw_client)

    raw_client.with_retry.assert_called_once()
    kwargs = raw_client.with_retry.call_args.kwargs
    assert kwargs["stop_after_attempt"] == 5  # = self.max_retries
    assert kwargs["wait_exponential_jitter"] is True
    # The exact tuple comes from the implementation's documented retry policy
    # (network/connection + timeout). Tested as set membership rather than
    # tuple equality so the test doesn't pin order.
    assert ConnectionError in kwargs["retry_if_exception_type"]
    assert TimeoutError in kwargs["retry_if_exception_type"]
    assert out is wrapped


# ── invoke (sync) ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "prompt",
    ["hi", [{"role": "system", "content": "be helpful"}, {"role": "user", "content": "hi"}]],
    ids=["string-prompt", "message-list-prompt"],
)
def test_invoke_forwards_prompt_and_dict_converts_response(prompt):
    """Lines 92: invoke calls client.invoke verbatim; result is dict-converted."""
    client = MagicMock()
    client.invoke.return_value = _msg("hello")
    model = _ConcreteLangchainModel(client=client)

    out = model.invoke(prompt)

    client.invoke.assert_called_once_with(prompt)
    assert out["content"] == "hello"
    assert out["type"] == "ai"  # round-tripped via dict()


# ── ainvoke (async) ─────────────────────────────────────────────────


def test_ainvoke_awaits_client_ainvoke_and_dict_converts():
    client = MagicMock()
    client.ainvoke = AsyncMock(return_value=_msg("async-hello"))
    model = _ConcreteLangchainModel(client=client)

    out = _run(model.ainvoke("hi"))

    client.ainvoke.assert_awaited_once_with("hi")
    assert out["content"] == "async-hello"


# ── batch (sync) ────────────────────────────────────────────────────


def test_batch_zero_concurrency_omits_config_nonzero_passes_max_concurrency():
    """Combined: max_concurrency == 0 → no config kwarg; non-zero → config={"max_concurrency": N}."""
    # Zero branch.
    client0 = MagicMock()
    client0.batch.return_value = [_msg("a"), _msg("b"), _msg("c")]
    model0 = _ConcreteLangchainModel(client=client0, max_concurrency=0)
    out = model0.batch(["p0", "p1", "p2"])
    client0.batch.assert_called_once_with(["p0", "p1", "p2"])
    assert [r["content"] for r in out] == ["a", "b", "c"]

    # Non-zero branch.
    client1 = MagicMock()
    client1.batch.return_value = [_msg("a"), _msg("b")]
    model1 = _ConcreteLangchainModel(client=client1, max_concurrency=4)
    model1.batch(["x", "y"])
    client1.batch.assert_called_once_with(["x", "y"], config={"max_concurrency": 4})


# ── abatch (async) ──────────────────────────────────────────────────


def test_abatch_with_max_concurrency_zero_passes_only_callbacks():
    client = MagicMock()
    client.abatch = AsyncMock(return_value=[_msg("a"), _msg("b")])
    model = _ConcreteLangchainModel(client=client, max_concurrency=0)

    out = _run(model.abatch(["p0", "p1"]))

    assert client.abatch.await_count == 1
    args, kwargs = client.abatch.call_args
    assert args == (["p0", "p1"],)
    assert "config" in kwargs
    assert "callbacks" in kwargs["config"]
    assert "max_concurrency" not in kwargs["config"]
    assert isinstance(kwargs["config"]["callbacks"][0], BatchCallback)
    assert [r["content"] for r in out] == ["a", "b"]


def test_abatch_with_nonzero_concurrency_passes_max_concurrency_and_callbacks():
    client = MagicMock()
    client.abatch = AsyncMock(return_value=[_msg("a"), _msg("b"), _msg("c")])
    model = _ConcreteLangchainModel(client=client, max_concurrency=3)

    _run(model.abatch(["x", "y", "z"]))

    kwargs = client.abatch.call_args.kwargs
    assert kwargs["config"]["max_concurrency"] == 3
    assert isinstance(kwargs["config"]["callbacks"][0], BatchCallback)


# ── is_answer_blocked ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ({"response_metadata": {"finish_reason": "blacklist"}}, True),
        ({"response_metadata": {"finish_reason": "stop"}}, False),
        ({"content": "hi"}, False),  # no response_metadata at all
        ({"response_metadata": {}}, False),  # metadata present, no finish_reason
    ],
    ids=["blacklist-true", "stop-false", "no-metadata-false", "metadata-without-finish-reason-false"],
)
def test_is_answer_blocked_returns_true_only_for_blacklist_finish_reason(answer, expected):
    """LangchainModel.is_answer_blocked only flags finish_reason == 'blacklist'."""
    model = _ConcreteLangchainModel(client=MagicMock())

    assert model.is_answer_blocked(answer) is expected


# ── get_params ──────────────────────────────────────────────────────


def test_get_params_merges_client_dict_with_concurrency_fields():
    client = MagicMock()
    client.dict.return_value = {"model_name": "gpt-fake", "temperature": 0.7}
    model = _ConcreteLangchainModel(
        client=client, model_name="gpt-fake", max_concurrency=8
    )

    params = model.get_params()

    assert params["model_name"] == "gpt-fake"
    assert params["temperature"] == 0.7
    assert params["max_concurrency"] == 8
    assert params["batch_size"] == 8  # = max_concurrency by construction
    client.dict.assert_called_once_with()


def test_get_params_overrides_client_concurrency_fields_with_model_attrs():
    # If the client.dict() happens to include keys that collide with the
    # outer fields, the outer values win because they appear last in {**a, ...}.
    client = MagicMock()
    client.dict.return_value = {"max_concurrency": 999, "batch_size": 999}
    model = _ConcreteLangchainModel(client=client, max_concurrency=2)

    params = model.get_params()

    assert params["max_concurrency"] == 2
    assert params["batch_size"] == 2


# ── stream_abatch ───────────────────────────────────────────────────


def test_stream_abatch_yields_one_record_per_prompt_in_input_order():
    client = MagicMock()

    async def fake_ainvoke(prompt):
        # Yield control so tasks interleave; preservation must be by index
        # not by completion order.
        await asyncio.sleep(0)
        return _msg(f"r:{prompt}")

    client.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    model = _ConcreteLangchainModel(client=client, max_concurrency=3)
    prompts = [f"p{i}" for i in range(5)]

    out = _run(_async_collect(model.stream_abatch(prompts)))

    assert len(out) == 5
    assert [r["content"] for r in out] == [f"r:p{i}" for i in range(5)]


def test_stream_abatch_captures_per_prompt_exception_as_error_dict():
    """Lines 179-186: per-prompt exception becomes an error dict, slot preserved."""
    client = MagicMock()

    async def fake_ainvoke(prompt):
        if prompt == "bad":
            raise RuntimeError("kaboom")
        return _msg(f"r:{prompt}")

    client.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    model = _ConcreteLangchainModel(client=client, max_concurrency=2)

    out = _run(_async_collect(model.stream_abatch(["good", "bad", "good2"])))

    assert len(out) == 3
    assert out[0]["content"] == "r:good"
    assert out[1]["content"] == ""
    assert out[1]["error_type"] == "RuntimeError"
    assert "kaboom" in out[1]["error"]
    assert out[2]["content"] == "r:good2"


def test_stream_abatch_empty_prompt_list_yields_nothing():
    client = MagicMock()
    client.ainvoke = AsyncMock(return_value=_msg("never"))
    model = _ConcreteLangchainModel(client=client, max_concurrency=2)

    out = _run(_async_collect(model.stream_abatch([])))

    assert out == []
    client.ainvoke.assert_not_awaited()


# ── BatchCallback ───────────────────────────────────────────────────


def test_batch_callback_on_llm_end_increments_count():
    cb = BatchCallback(total=2)
    try:
        cb.on_llm_end(MagicMock(), run_id=uuid4())
        cb.on_llm_end(MagicMock(), run_id=uuid4())
    finally:
        cb.progress_bar.close()

    assert cb.count == 2  # = number of on_llm_end calls


class _RecordingBar:
    """Hand-rolled stand-in for tqdm — records __enter__/__exit__/__del__ calls.

    Cannot use MagicMock because Python forbids assigning ``__del__`` on it
    (unsupported magic). We need a real ``__del__`` so that
    ``BatchCallback.__del__ -> self.progress_bar.__del__()`` is a no-op.
    """

    def __init__(self):
        self.entered = 0
        self.exited = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.exited += 1
        return False

    def __del__(self):
        return None


def test_batch_callback_sync_context_manager_enters_and_exits_progress_bar():
    cb = BatchCallback(total=1)
    cb.progress_bar.close()  # close the real bar created in __init__
    cb.progress_bar = _RecordingBar()

    with cb as entered:
        assert entered is cb
        assert cb.progress_bar.entered == 1
    assert cb.progress_bar.exited == 1


def test_batch_callback_async_context_manager_delegates_to_sync():
    cb = BatchCallback(total=1)
    cb.progress_bar.close()
    cb.progress_bar = _RecordingBar()

    async def runner():
        async with cb as entered:
            assert entered is cb
        return True

    assert _run(runner()) is True
    assert cb.progress_bar.entered == 1
    assert cb.progress_bar.exited == 1
