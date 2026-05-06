"""Unit tests for hivetracered.models.rest_model.RestModel.

Tests cover:
- constructor defaults / validation / JSONPath pre-compilation
- placeholder substitution ($INPUT, $KEY)
- prompt text extraction (string vs message list)
- request building (URL, headers, body)
- response parsing with JSONPath (success, no-match, plain text)
- retry/skip-code logic and exponential backoff
- sync invoke() with mocked requests.request
- async ainvoke() with mocked aiohttp.ClientSession
- batch() and abatch() ordering with concurrent execution
- stream_abatch() preserving input order
- HTTP error/timeout/malformed-JSON handling
- get_params() scrubbing of secret-looking headers

All HTTP boundaries are mocked. time.sleep / asyncio.sleep are patched out so
tests run without wall-clock waits. random is seeded deterministically.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import requests

from hivetracered.models.rest_model import RestModel


# ── Helpers ──────────────────────────────────────────────────────────


def _async_collect(async_gen: AsyncGenerator) -> list:
    async def _runner():
        out = []
        async for item in async_gen:
            out.append(item)
        return out

    return asyncio.new_event_loop().run_until_complete(_runner())


def _make_sync_response(status_code: int, text: str = "", json_payload: Any = None) -> MagicMock:
    """Build a mock requests.Response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    if json_payload is not None:
        resp.text = json.dumps(json_payload)
        resp.json = MagicMock(return_value=json_payload)
    else:
        resp.text = text
    if status_code >= 400:
        resp.raise_for_status = MagicMock(
            side_effect=requests.HTTPError(f"HTTP {status_code}")
        )
    else:
        resp.raise_for_status = MagicMock(return_value=None)
    return resp


class _FakeAiohttpResponse:
    """Mimics aiohttp ClientResponse for async-context-manager use."""

    def __init__(self, status: int, text: str = ""):
        self.status = status
        self._text = text
        self.request_info = MagicMock()
        self.history = ()

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAiohttpSession:
    """Mimics aiohttp ClientSession context manager.

    `responder` is a callable (method, url, headers, data, proxy) -> _FakeAiohttpResponse
    or a list of such responses to pop from in order.
    """

    def __init__(self, responder):
        self._responder = responder
        self.requests_made = []

    def request(self, method, url, headers=None, data=None, proxy=None):
        self.requests_made.append(
            {"method": method, "url": url, "headers": headers, "data": data, "proxy": proxy}
        )
        if callable(self._responder):
            return self._responder(method, url, headers, data, proxy)
        # treat as list/iterator: pop next
        return self._responder.pop(0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


# ── Autouse: kill any wall-clock waits and seed randomness ──────────


@pytest.fixture(autouse=True)
def _no_sleep_no_random(monkeypatch):
    # Replace time.sleep used inside rest_model with a no-op.
    monkeypatch.setattr("hivetracered.models.rest_model.time.sleep", lambda *_a, **_k: None)
    # asyncio.sleep is awaited; replace with an awaitable no-op.
    async def _async_noop(*_a, **_k):
        return None

    monkeypatch.setattr("hivetracered.models.rest_model.asyncio.sleep", _async_noop)
    # Make jittered backoff deterministic.
    monkeypatch.setattr(
        "hivetracered.models.rest_model.random.uniform", lambda lo, hi: 0.0
    )


# ── Constructor / get_params ────────────────────────────────────────


def test_init_sets_defaults_when_optional_args_omitted():
    model = RestModel(uri="http://example.com/api")

    assert model.uri == "http://example.com/api"
    assert model.method == "POST"
    assert model.model_name == "rest"
    assert model.headers == {"Content-Type": "application/json"}
    assert model.ratelimit_codes == [429]
    assert model.skip_codes == []
    assert model.retry_5xx is True
    assert model.max_retries == 3
    assert model.max_concurrency == 10
    assert model.request_timeout == 20
    assert model.verify_ssl is True
    assert model.proxies is None


def test_init_uppercases_method():
    model = RestModel(uri="http://x/y", method="get")

    assert model.method == "GET"


def test_init_max_concurrency_zero_falls_back_to_ten():
    # `max_concurrency or 10` — 0 is falsy, defaults to 10. [INFERRED FROM CODE]
    model = RestModel(uri="http://x/y", max_concurrency=0)

    assert model.max_concurrency == 10


def test_init_invalid_jsonpath_raises():
    from jsonpath_ng.exceptions import JsonPathParserError

    with pytest.raises(JsonPathParserError):
        RestModel(uri="http://x/y", response_json_field="$..[invalid syntax")


def test_get_params_scrubs_headers_containing_key_or_auth():
    model = RestModel(
        uri="http://x/y",
        headers={
            "Authorization": "Bearer secret123",
            "X-Api-Key": "k",
            "Content-Type": "application/json",
            "User-Agent": "test/1.0",
        },
    )

    params = model.get_params()

    assert params["headers"]["Authorization"] == "***"
    assert params["headers"]["X-Api-Key"] == "***"
    assert params["headers"]["Content-Type"] == "application/json"
    assert params["headers"]["User-Agent"] == "test/1.0"


def test_get_params_returns_uri_method_and_extra_kwargs():
    model = RestModel(uri="http://x/y", method="PUT", custom="abc")

    params = model.get_params()

    assert params["uri"] == "http://x/y"
    assert params["method"] == "PUT"
    assert params["custom"] == "abc"
    assert params["model_name"] == "rest"


# ── _substitute_in_obj ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("template", "input_val", "key_val", "expected"),
    [
        ("hello $INPUT", "world", "", "hello world"),
        (
            {"q": "$INPUT", "auth": {"token": "$KEY"}},
            "P",
            "K",
            {"q": "P", "auth": {"token": "K"}},
        ),
        (["a", "$INPUT", {"k": "$INPUT"}], "X", "", ["a", "X", {"k": "X"}]),
        (
            {"n": 1, "b": True, "f": 1.5, "z": None},
            "P",
            "K",
            {"n": 1, "b": True, "f": 1.5, "z": None},
        ),
    ],
    ids=["string-input", "nested-dict-input-and-key", "list-walked", "non-str-leaves-preserved"],
)
def test_substitute_in_obj_recurses_and_replaces_placeholders(template, input_val, key_val, expected):
    """$INPUT/$KEY substitution walks dicts+lists, leaves non-str values alone."""
    model = RestModel(uri="http://x/y")

    assert model._substitute_in_obj(template, input_val, key_val) == expected


# ── _extract_prompt_text ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("hi", "hi"),  # str returned as-is
        (
            [
                {"role": "system", "content": "be helpful"},
                {"role": "user", "content": "hi"},
            ],
            "system: be helpful\nuser: hi",
        ),
        (
            [{"content": "no-role"}, {"role": "user", "content": "hi"}],
            "no-role\nuser: hi",
        ),
    ],
    ids=["string-passthrough", "joined-role-content", "empty-role-omits-prefix"],
)
def test_extract_prompt_text_resolution(prompt, expected):
    assert RestModel._extract_prompt_text(prompt) == expected


# ── _build_request ──────────────────────────────────────────────────


def test_build_request_substitutes_input_in_uri_headers_and_body():
    model = RestModel(
        uri="http://x/y?q=$INPUT",
        api_key="SECRET",
        headers={"Authorization": "Bearer $KEY"},
        req_template={"prompt": "$INPUT", "key": "$KEY"},
    )

    url, headers, body = model._build_request("hello")

    assert url == "http://x/y?q=hello"
    assert headers == {"Authorization": "Bearer SECRET"}
    assert json.loads(body.decode("utf-8")) == {"prompt": "hello", "key": "SECRET"}


def test_build_request_returns_none_body_when_no_template():
    model = RestModel(uri="http://x/y")

    _, _, body = model._build_request("hi")

    assert body is None


# ── _parse_response ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("response_json_field", "text", "expected"),
    [
        (None, "raw text", {"content": "raw text"}),  # no jsonpath → text passthrough
        ("$.x", "", {"content": ""}),  # empty text short-circuits before jsonpath
        (
            "$.choices[0].message.content",
            json.dumps({"choices": [{"message": {"content": "hello"}}]}),
            {"content": "hello"},
        ),  # jsonpath match
    ],
    ids=["no-jsonpath-text-passthrough", "empty-text-shortcircuit", "jsonpath-match"],
)
def test_parse_response_happy_paths(response_json_field, text, expected):
    kwargs = {"uri": "http://x/y"}
    if response_json_field is not None:
        kwargs["response_json_field"] = response_json_field
    model = RestModel(**kwargs)

    assert model._parse_response(200, text) == expected


def test_parse_response_raises_when_jsonpath_matches_nothing():
    model = RestModel(uri="http://x/y", response_json_field="$.missing")
    payload = json.dumps({"other": 1})

    with pytest.raises(ValueError, match=r"matched nothing"):
        model._parse_response(200, payload)


def test_parse_response_raises_on_malformed_json():
    model = RestModel(uri="http://x/y", response_json_field="$.x")

    with pytest.raises(json.JSONDecodeError):
        model._parse_response(200, "{not json")


# ── _should_retry / _retry_delay / _get_aiohttp_proxy ──────────────


@pytest.mark.parametrize(
    ("status", "expected"),
    [(200, False), (400, False), (429, True), (500, True), (503, True), (599, True), (600, False)],
    ids=["200-ok", "400-client", "429-rl", "500-server", "503-server", "599-edge", "600-out-of-range"],
)
def test_should_retry_table(status, expected):
    model = RestModel(uri="http://x/y")

    assert model._should_retry(status) is expected


def test_should_retry_respects_config_overrides():
    """retry_5xx=False disables 5xx retry but keeps ratelimit; custom ratelimit_codes honored."""
    no_5xx = RestModel(uri="http://x/y", retry_5xx=False)
    assert no_5xx._should_retry(500) is False
    assert no_5xx._should_retry(429) is True

    custom_rl = RestModel(uri="http://x/y", ratelimit_codes=[418, 429])
    assert custom_rl._should_retry(418) is True


def test_retry_delay_uses_exponential_base_capped_at_60(monkeypatch):
    """_retry_delay computes uniform(0, min(60, 2**n))."""
    captured = []
    monkeypatch.setattr(
        "hivetracered.models.rest_model.random.uniform",
        lambda lo, hi: captured.append((lo, hi)) or 0.0,
    )

    for n in [0, 1, 2, 3, 20]:
        RestModel._retry_delay(n)

    # 2**0..2**3 grows exponentially; 2**20 caps at 60.
    assert captured == [(0, 1), (0, 2), (0, 4), (0, 8), (0, 60)]


@pytest.mark.parametrize(
    ("proxies", "expected"),
    [
        ({"http": "http://h", "https": "https://s"}, "https://s"),  # https wins
        (None, None),  # no proxies configured
        ({"http": "http://h"}, "http://h"),  # falls back to http
    ],
    ids=["https-preferred", "no-proxies", "http-fallback"],
)
def test_get_aiohttp_proxy_resolution(proxies, expected):
    """Proxy preference order: https → http → None."""
    model = RestModel(uri="http://x/y", proxies=proxies) if proxies else RestModel(uri="http://x/y")

    assert model._get_aiohttp_proxy() == expected


# ── invoke (sync) ───────────────────────────────────────────────────


def test_invoke_success_extracts_jsonpath_field():
    model = RestModel(
        uri="http://x/y",
        req_template={"prompt": "$INPUT"},
        response_json_field="$.text",
    )
    fake_resp = _make_sync_response(200, json_payload={"text": "answer"})

    with patch(
        "hivetracered.models.rest_model.requests.request", return_value=fake_resp
    ) as mock_req:
        out = model.invoke("hi")

    assert out == {"content": "answer"}
    # Verify the HTTP boundary received the substituted body.
    call_kwargs = mock_req.call_args.kwargs
    assert json.loads(call_kwargs["data"].decode("utf-8")) == {"prompt": "hi"}
    assert mock_req.call_args.args[0] == "POST"


def test_invoke_skip_code_returns_empty_content_without_raising():
    model = RestModel(uri="http://x/y", skip_codes=[404], max_retries=0)
    fake_resp = _make_sync_response(404, "not found")

    with patch(
        "hivetracered.models.rest_model.requests.request", return_value=fake_resp
    ):
        out = model.invoke("hi")

    assert out == {"content": ""}


def test_invoke_retries_on_429_then_succeeds():
    model = RestModel(uri="http://x/y", max_retries=2)
    rl = _make_sync_response(429, "rate-limited")
    ok = _make_sync_response(200, "yo")
    seq = [rl, ok]

    with patch(
        "hivetracered.models.rest_model.requests.request",
        side_effect=lambda *a, **k: seq.pop(0),
    ) as mock_req:
        out = model.invoke("hi")

    assert out == {"content": "yo"}
    assert mock_req.call_count == 2  # 1 retry + 1 success


def test_invoke_retries_on_5xx_when_retry_5xx_true():
    model = RestModel(uri="http://x/y", max_retries=2)
    seq = [_make_sync_response(500), _make_sync_response(503), _make_sync_response(200, "k")]

    with patch(
        "hivetracered.models.rest_model.requests.request",
        side_effect=lambda *a, **k: seq.pop(0),
    ) as mock_req:
        out = model.invoke("hi")

    assert out == {"content": "k"}
    assert mock_req.call_count == 3


def test_invoke_returns_error_dict_after_exhausting_retries_on_persistent_5xx():
    model = RestModel(uri="http://x/y", max_retries=1)
    bad = _make_sync_response(500)

    with patch(
        "hivetracered.models.rest_model.requests.request", return_value=bad
    ):
        out = model.invoke("hi")

    assert out["content"] == ""
    assert "error" in out
    assert "error_type" in out


@pytest.mark.parametrize(
    ("exc", "expected_type", "expected_msg_fragment"),
    [
        (requests.ConnectionError("conn refused"), "ConnectionError", "conn refused"),
        (requests.Timeout("read timed out"), "Timeout", "read timed out"),
    ],
    ids=["connection-error", "timeout"],
)
def test_invoke_returns_error_dict_on_request_exception(exc, expected_type, expected_msg_fragment):
    model = RestModel(uri="http://x/y", max_retries=1)

    with patch(
        "hivetracered.models.rest_model.requests.request",
        side_effect=exc,
    ):
        out = model.invoke("hi")

    assert out["content"] == ""
    assert out["error_type"] == expected_type
    assert expected_msg_fragment in out["error"]


def test_invoke_passes_through_4xx_as_exception_then_error_dict():
    # 4xx (not in skip_codes, not in ratelimit_codes) -> raise_for_status
    # raises -> except branch returns error dict after retries exhausted.
    model = RestModel(uri="http://x/y", max_retries=0)
    bad = _make_sync_response(400)

    with patch(
        "hivetracered.models.rest_model.requests.request", return_value=bad
    ):
        out = model.invoke("hi")

    assert out["content"] == ""
    assert out["error_type"] == "HTTPError"


def test_invoke_passes_method_url_headers_timeout_verify_ssl_proxies():
    model = RestModel(
        uri="http://x/y",
        method="PUT",
        headers={"X-Custom": "v"},
        request_timeout=7,
        verify_ssl=False,
        proxies={"https": "https://p"},
        max_retries=0,
    )
    ok = _make_sync_response(200, "k")

    with patch(
        "hivetracered.models.rest_model.requests.request", return_value=ok
    ) as mock_req:
        model.invoke("hi")

    args, kwargs = mock_req.call_args
    assert args[0] == "PUT"
    assert args[1] == "http://x/y"
    assert kwargs["headers"] == {"X-Custom": "v"}
    assert kwargs["timeout"] == 7
    assert kwargs["verify"] is False
    assert kwargs["proxies"] == {"https": "https://p"}


# ── ainvoke (async) ─────────────────────────────────────────────────


def test_ainvoke_success_extracts_jsonpath_field(monkeypatch):
    model = RestModel(
        uri="http://x/y",
        req_template={"prompt": "$INPUT"},
        response_json_field="$.text",
    )
    fake_resp = _FakeAiohttpResponse(200, json.dumps({"text": "async-ok"}))
    fake_session = _FakeAiohttpSession(lambda *a, **k: fake_resp)

    monkeypatch.setattr(
        "hivetracered.models.rest_model.aiohttp.ClientSession",
        lambda *a, **k: fake_session,
    )

    out = asyncio.new_event_loop().run_until_complete(model.ainvoke("hi"))

    assert out == {"content": "async-ok"}
    assert fake_session.requests_made[0]["method"] == "POST"
    assert fake_session.requests_made[0]["url"] == "http://x/y"


def test_ainvoke_skip_code_returns_empty_content(monkeypatch):
    model = RestModel(uri="http://x/y", skip_codes=[404], max_retries=0)
    fake_resp = _FakeAiohttpResponse(404, "not found")
    fake_session = _FakeAiohttpSession(lambda *a, **k: fake_resp)
    monkeypatch.setattr(
        "hivetracered.models.rest_model.aiohttp.ClientSession",
        lambda *a, **k: fake_session,
    )

    out = asyncio.new_event_loop().run_until_complete(model.ainvoke("hi"))

    assert out == {"content": ""}


def test_ainvoke_retries_on_429_then_succeeds(monkeypatch):
    model = RestModel(uri="http://x/y", max_retries=2)
    seq = [
        _FakeAiohttpResponse(429, "rl"),
        _FakeAiohttpResponse(200, "ok"),
    ]
    sessions_built = []

    def session_factory(*a, **k):
        # Fresh session each iteration, but they all share the same `seq`.
        s = _FakeAiohttpSession(lambda *a, **k: seq.pop(0))
        sessions_built.append(s)
        return s

    monkeypatch.setattr(
        "hivetracered.models.rest_model.aiohttp.ClientSession", session_factory
    )

    out = asyncio.new_event_loop().run_until_complete(model.ainvoke("hi"))

    assert out == {"content": "ok"}
    assert len(sessions_built) == 2  # one per attempt


def test_ainvoke_returns_error_dict_on_persistent_5xx(monkeypatch):
    model = RestModel(uri="http://x/y", max_retries=1)

    def session_factory(*a, **k):
        return _FakeAiohttpSession(lambda *aa, **kk: _FakeAiohttpResponse(500, "boom"))

    monkeypatch.setattr(
        "hivetracered.models.rest_model.aiohttp.ClientSession", session_factory
    )

    out = asyncio.new_event_loop().run_until_complete(model.ainvoke("hi"))

    assert out["content"] == ""
    assert "error" in out
    assert "error_type" in out


def test_ainvoke_returns_error_dict_on_aiohttp_exception(monkeypatch):
    model = RestModel(uri="http://x/y", max_retries=1)

    class _Boom:
        def __init__(self, *a, **k): ...

        async def __aenter__(self):
            raise aiohttp.ClientError("net down")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(
        "hivetracered.models.rest_model.aiohttp.ClientSession",
        lambda *a, **k: _Boom(),
    )

    out = asyncio.new_event_loop().run_until_complete(model.ainvoke("hi"))

    assert out["content"] == ""
    assert out["error_type"] == "ClientError"


# ── batch / abatch ──────────────────────────────────────────────────


def test_batch_preserves_input_order():
    model = RestModel(uri="http://x/y", max_concurrency=4)
    prompts = [f"p{i}" for i in range(8)]

    # Have invoke return a content tied to its input prompt so we can verify order.
    def fake_invoke(prompt):
        return {"content": f"r:{prompt}"}

    with patch.object(model, "invoke", side_effect=fake_invoke):
        out = model.batch(prompts)

    assert [r["content"] for r in out] == [f"r:{p}" for p in prompts]


def test_batch_sequential_path_when_max_concurrency_zero(monkeypatch):
    # max_concurrency=0 hits the sequential branch (lines 277-280).
    # __init__ falls back to 10 if 0 passed; force the attribute after construction.
    model = RestModel(uri="http://x/y")
    model.max_concurrency = 0
    prompts = ["a", "b", "c"]

    def fake_invoke(prompt):
        return {"content": f"r:{prompt}"}

    with patch.object(model, "invoke", side_effect=fake_invoke):
        out = model.batch(prompts)

    assert [r["content"] for r in out] == ["r:a", "r:b", "r:c"]


def test_abatch_preserves_input_order_under_concurrency():
    model = RestModel(uri="http://x/y", max_concurrency=4)
    prompts = [f"p{i}" for i in range(6)]

    async def fake_ainvoke(prompt):
        # Yield control to interleave tasks; ensures order preservation isn't
        # accidental (results returned by index, not as_completed order).
        await asyncio.sleep(0)
        return {"content": f"r:{prompt}"}

    with patch.object(model, "ainvoke", side_effect=fake_ainvoke):
        out = asyncio.new_event_loop().run_until_complete(model.abatch(prompts))

    assert [r["content"] for r in out] == [f"r:{p}" for p in prompts]


# ── stream_abatch ───────────────────────────────────────────────────


def test_stream_abatch_yields_results_in_input_order():
    model = RestModel(uri="http://x/y", max_concurrency=3)
    prompts = [f"p{i}" for i in range(5)]

    async def fake_ainvoke(prompt):
        await asyncio.sleep(0)
        return {"content": f"r:{prompt}"}

    with patch.object(model, "ainvoke", side_effect=fake_ainvoke):
        out = _async_collect(model.stream_abatch(prompts))

    assert len(out) == 5
    assert [r["content"] for r in out] == [f"r:{p}" for p in prompts]


def test_stream_abatch_yields_error_dict_for_failing_prompt():
    model = RestModel(uri="http://x/y", max_concurrency=2)
    prompts = ["good", "bad", "good2"]

    async def fake_ainvoke(prompt):
        if prompt == "bad":
            raise RuntimeError("boom")
        return {"content": f"r:{prompt}"}

    with patch.object(model, "ainvoke", side_effect=fake_ainvoke):
        out = _async_collect(model.stream_abatch(prompts))

    assert len(out) == 3
    assert out[0]["content"] == "r:good"
    assert out[1]["content"] == ""
    assert out[1]["error_type"] == "RuntimeError"
    assert "boom" in out[1]["error"]
    assert out[2]["content"] == "r:good2"


@pytest.mark.parametrize(
    "method_name",
    ["batch", "abatch", "stream_abatch"],
    ids=["batch", "abatch", "stream_abatch"],
)
def test_batch_methods_handle_empty_prompts_list(method_name):
    """All batch entry points must short-circuit on []."""
    model = RestModel(uri="http://x/y", max_concurrency=2)

    if method_name == "batch":
        with patch.object(model, "invoke", return_value={"content": "x"}):
            out = model.batch([])
    elif method_name == "abatch":
        with patch.object(model, "ainvoke", return_value={"content": "x"}):
            out = asyncio.new_event_loop().run_until_complete(model.abatch([]))
    else:
        out = _async_collect(model.stream_abatch([]))

    assert out == []


# ── invoke through prompt_text extraction (integration with build_request) ──


def test_invoke_with_message_list_substitutes_joined_role_content():
    model = RestModel(
        uri="http://x/y",
        req_template={"prompt": "$INPUT"},
        max_retries=0,
    )
    ok = _make_sync_response(200, "k")

    with patch(
        "hivetracered.models.rest_model.requests.request", return_value=ok
    ) as mock_req:
        model.invoke([{"role": "user", "content": "hello"}])

    sent = json.loads(mock_req.call_args.kwargs["data"].decode("utf-8"))
    assert sent == {"prompt": "user: hello"}
