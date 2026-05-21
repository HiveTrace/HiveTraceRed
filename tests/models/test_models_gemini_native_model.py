"""Unit tests for hivetracered.models.gemini_native_model.GeminiNativeModel.

Tests are spec-grounded against the docstring and Model ABC contract.
All external seams are mocked: the google.genai.Client SDK is replaced
at module-import scope, time.sleep / asyncio.sleep / tenacity.nap.sleep
are patched so retries do not introduce wall-clock waits.
"""

from __future__ import annotations

import asyncio
import warnings
from unittest.mock import MagicMock

import pytest

# Skip the whole module if google.genai is not importable in this env.
pytest.importorskip("google.genai")

from hivetracered.models import gemini_native_model as gnm
from hivetracered.models.gemini_native_model import GeminiNativeModel
from tests.conftest import async_collect


# ── Helpers ─────────────────────────────────────────────────────────


def _make_response(text: str) -> MagicMock:
    """Build a stand-in for genai.types.GenerateContentResponse.

    The wrapper only reads `.text` from the response object
    (gemini_native_model.py line 194).
    """
    resp = MagicMock(name="GenerateContentResponse")
    resp.text = text
    return resp


def _make_client_returning(text: str) -> MagicMock:
    """Build a fake genai.Client whose generate_content returns `text`."""
    client = MagicMock(name="Client")
    client.models.generate_content.return_value = _make_response(text)
    return client


@pytest.fixture
def fake_client():
    """Fake genai.Client that returns a valid structured JSON response."""
    return _make_client_returning('{"response": "hi there"}')


@pytest.fixture
def patched_genai(monkeypatch, fake_client):
    """Patch genai.Client so constructing GeminiNativeModel never hits Google."""
    factory = MagicMock(return_value=fake_client)
    monkeypatch.setattr(gnm.genai, "Client", factory)
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-test-key")
    return factory


@pytest.fixture
def no_retry_sleep(monkeypatch):
    """Make tenacity retry waits instantaneous so tests stay deterministic."""
    import tenacity.nap

    monkeypatch.setattr(tenacity.nap, "sleep", lambda _seconds: None)
    monkeypatch.setattr(gnm.time, "sleep", lambda _seconds: None)


@pytest.fixture
def model(patched_genai):
    """Default model with RPM disabled and concurrency 2."""
    return GeminiNativeModel(model="test-gemini", max_concurrency=2, rpm=0)


# ── Constructor / API key ───────────────────────────────────────────


def test_init_raises_when_google_api_key_missing(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    # load_dotenv(override=True) may inject a key from a local .env file —
    # neutralize it so the env-var check actually runs.
    monkeypatch.setattr(gnm, "load_dotenv", lambda override=True: None)

    with pytest.raises(ValueError, match=r"GOOGLE_API_KEY"):
        GeminiNativeModel(model="m")


def test_init_default_temperature_is_low(patched_genai):
    """docstring lines 92-94: very low default when temperature omitted."""
    m = GeminiNativeModel(model="m", rpm=0)

    assert m.kwargs["temperature"] == pytest.approx(0.000001)


def test_init_batch_size_emits_deprecation_warning(patched_genai):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        GeminiNativeModel(model="m", batch_size=4, rpm=0)

    deprecation_msgs = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecation_msgs, "expected a DeprecationWarning for batch_size"
    assert "batch_size" in str(deprecation_msgs[0].message)


def test_init_batch_size_falls_back_to_max_concurrency(patched_genai):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        m = GeminiNativeModel(model="m", batch_size=7, rpm=0)

    # Per source line 61-62: when max_concurrency is None, batch_size value is used.
    assert m.max_concurrency == 7


def test_init_default_max_concurrency_is_zero(patched_genai):
    m = GeminiNativeModel(model="m", rpm=0)

    # Per source line 64-66.
    assert m.max_concurrency == 0


# ── get_params ──────────────────────────────────────────────────────


def test_get_params_reflects_constructor_args(patched_genai):
    m = GeminiNativeModel(
        model="g", max_concurrency=3, thinking_budget=42, rpm=10, temperature=0.25
    )

    params = m.get_params()

    assert params == {
        "model": "g",
        "batch_size": 3,
        "thinking_budget": 42,
        "rpm": 10,
        "temperature": 0.25,
    }


# ── invoke (str prompt happy path) ──────────────────────────────────


def test_invoke_string_response_shape_and_sdk_call(model, fake_client):
    """Source lines 194-285 + 277: invoke(str) parses fake_client's
    {"response":"hi there"} JSON, returns dict with content/role/model/
    structured_content/raw_response, and forwards prompt verbatim as `contents`.
    """
    result = model.invoke("hello world")

    # SDK boundary call.
    fake_client.models.generate_content.assert_called_once()
    kwargs = fake_client.models.generate_content.call_args.kwargs
    assert kwargs["contents"] == "hello world"
    assert kwargs["model"] == "test-gemini"

    # Returned dict shape.
    assert isinstance(result, dict)
    assert result["content"] == "hi there"  # JSON["response"] of fake_client
    assert result["role"] == "assistant"  # source line 277
    assert result["model"] == "test-gemini"
    assert result["structured_content"] == {"response": "hi there"}
    assert result["raw_response"] is fake_client.models.generate_content.return_value


# ── invoke (message list -> Gemini message format) ─────────────────


@pytest.mark.parametrize(
    ("input_msg", "expected_role", "expected_text"),
    [
        ({"role": "assistant", "content": "prior reply"}, "model", "prior reply"),  # line 250-251
        ({"role": "system", "content": "you are helpful"}, "user", "you are helpful"),  # line 252-253
        ({"role": "user", "content": "hi"}, "user", "hi"),  # passthrough
        ({"content": "hi"}, "user", "hi"),  # line 248: default role
    ],
    ids=["assistant-to-model", "system-to-user", "user-preserved", "missing-role-defaults-user"],
)
def test_invoke_message_list_role_mapping(model, fake_client, input_msg, expected_role, expected_text):
    """Lines 248-253: invoke remaps message roles to Gemini's role+parts shape."""
    model.invoke([input_msg])

    sent = fake_client.models.generate_content.call_args.kwargs["contents"]
    assert isinstance(sent, list)
    assert sent[0]["role"] == expected_role
    assert sent[0]["parts"] == [{"text": expected_text}]


def test_invoke_message_list_multi_turn_preserves_order(model, fake_client):
    msgs = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
    ]

    model.invoke(msgs)

    sent = fake_client.models.generate_content.call_args.kwargs["contents"]
    assert len(sent) == 3
    assert [m["parts"][0]["text"] for m in sent] == ["Q1", "A1", "Q2"]
    assert [m["role"] for m in sent] == ["user", "model", "user"]


# ── invoke error/exception paths ───────────────────────────────────


def test_invoke_invalid_prompt_type_returns_error_dict(model, no_retry_sleep):
    # _invoke_internal raises ValueError on non-str/non-list prompts (line 260).
    # invoke() wraps the retry attempt; after exhausting retries it returns an
    # error dict (lines 225-231).
    result = model.invoke(12345)  # type: ignore[arg-type]

    assert "error" in result
    assert "Error:" in result["content"]
    assert result["model"] == "test-gemini"


def test_invoke_returns_error_dict_when_client_raises(patched_genai, no_retry_sleep):
    bad_client = MagicMock()
    bad_client.models.generate_content.side_effect = ConnectionError("network is down")
    patched_genai.return_value = bad_client

    m = GeminiNativeModel(model="m", rpm=0, max_retries=2)
    result = m.invoke("p")

    # After retries exhausted, error is reported in returned dict (lines 225-231).
    assert "Error:" in result["content"]
    assert "network is down" in result["error"]
    assert result["model"] == "m"


def test_invoke_retries_then_succeeds(patched_genai, no_retry_sleep):
    flaky_client = MagicMock()
    flaky_client.models.generate_content.side_effect = [
        ConnectionError("fail-1"),
        ConnectionError("fail-2"),
        _make_response('{"response": "finally"}'),
    ]
    patched_genai.return_value = flaky_client

    m = GeminiNativeModel(model="m", rpm=0, max_retries=5)
    result = m.invoke("p")

    assert result["content"] == "finally"
    # Retried twice, succeeded on third call.
    assert flaky_client.models.generate_content.call_count == 3


def test_invoke_falls_back_to_raw_text_when_response_not_json(patched_genai, no_retry_sleep):
    raw_text_client = MagicMock()
    raw_text_client.models.generate_content.return_value = _make_response("plain non-json")
    patched_genai.return_value = raw_text_client

    m = GeminiNativeModel(model="m", rpm=0)
    result = m.invoke("p")

    # Per source lines 197-202: parsing fails, content becomes raw text,
    # structured_content stays None.
    assert result["content"] == "plain non-json"
    assert result["structured_content"] is None


# ── Rate limiting ──────────────────────────────────────────────────


def test_wait_for_rate_limit_no_op_when_rpm_zero(patched_genai, monkeypatch):
    sleep_calls = []
    monkeypatch.setattr(gnm.time, "sleep", lambda s: sleep_calls.append(s))

    m = GeminiNativeModel(model="m", rpm=0)
    m._wait_for_rate_limit()

    # Per source lines 137-138.
    assert sleep_calls == []


def test_wait_for_rate_limit_sleeps_when_quota_exceeded(patched_genai, monkeypatch):
    sleep_calls = []
    monkeypatch.setattr(gnm.time, "sleep", lambda s: sleep_calls.append(s))

    # Pin time so window math is predictable.
    fake_now = [1_000_000.0]
    monkeypatch.setattr(gnm.time, "time", lambda: fake_now[0])

    m = GeminiNativeModel(model="m", rpm=2)
    # Pre-populate the window with two recent requests at time 1_000_000.
    m.request_times = [fake_now[0], fake_now[0]]

    m._wait_for_rate_limit()

    # We should have slept ~60 seconds (60 - (now - oldest=now) = 60).
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == pytest.approx(60, abs=1e-6)


# ── batch (sync) ───────────────────────────────────────────────────


def test_batch_processes_more_prompts_than_concurrency(patched_genai):
    fake = MagicMock()
    fake.models.generate_content.side_effect = [
        _make_response('{"response": "r' + str(i) + '"}') for i in range(5)
    ]
    patched_genai.return_value = fake

    m = GeminiNativeModel(model="m", max_concurrency=2, rpm=0)
    results = m.batch(["p0", "p1", "p2", "p3", "p4"])

    assert [r["content"] for r in results] == ["r0", "r1", "r2", "r3", "r4"]
    assert fake.models.generate_content.call_count == 5


# ── ainvoke / abatch (async) ───────────────────────────────────────


def test_ainvoke_delegates_to_invoke(model, fake_client):
    result = asyncio.new_event_loop().run_until_complete(model.ainvoke("p"))

    assert result["content"] == "hi there"
    assert fake_client.models.generate_content.called


def test_abatch_returns_results_in_input_order(patched_genai):
    fake = MagicMock()
    fake.models.generate_content.side_effect = [
        _make_response('{"response": "r' + str(i) + '"}') for i in range(3)
    ]
    patched_genai.return_value = fake

    m = GeminiNativeModel(model="m", max_concurrency=3, rpm=0)
    results = asyncio.new_event_loop().run_until_complete(m.abatch(["p0", "p1", "p2"]))

    assert [r["content"] for r in results] == ["r0", "r1", "r2"]




# ── stream_abatch ──────────────────────────────────────────────────


def test_stream_abatch_yields_one_result_per_prompt(patched_genai):
    fake = MagicMock()
    fake.models.generate_content.side_effect = [
        _make_response('{"response": "r' + str(i) + '"}') for i in range(4)
    ]
    patched_genai.return_value = fake

    m = GeminiNativeModel(model="m", max_concurrency=2, rpm=0)
    results = async_collect(m.stream_abatch(["p0", "p1", "p2", "p3"]))

    # Per Model.stream_abatch contract — one result per input prompt.
    assert len(results) == 4
    contents = sorted(r["content"] for r in results)
    assert contents == ["r0", "r1", "r2", "r3"]


def test_stream_abatch_wraps_exceptions_in_error_dict(patched_genai, no_retry_sleep):
    # Make the SDK always raise. After retries are exhausted, invoke() returns
    # an error dict; stream_abatch wraps any further exceptions but here the
    # inner invoke already returns dict — verify the result still has 'error'.
    bad = MagicMock()
    bad.models.generate_content.side_effect = ConnectionError("boom")
    patched_genai.return_value = bad

    m = GeminiNativeModel(model="m", max_concurrency=1, rpm=0, max_retries=1)
    results = async_collect(m.stream_abatch(["only"]))

    assert len(results) == 1
    assert "error" in results[0]


@pytest.mark.parametrize(
    "method_name",
    ["batch", "abatch", "stream_abatch"],
    ids=["batch", "abatch", "stream_abatch"],
)
def test_empty_prompts_returns_no_results(model, method_name):
    """All batch-shaped entry points must short-circuit on []."""
    method = getattr(model, method_name)
    if method_name == "batch":
        results = method([])
    elif method_name == "abatch":
        results = asyncio.new_event_loop().run_until_complete(method([]))
    else:  # stream_abatch
        results = async_collect(method([]))

    assert results == []
