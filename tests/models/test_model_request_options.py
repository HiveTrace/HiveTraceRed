import asyncio
import json

import httpx
import pytest

from hivetracered.models.errors import is_response_format_unsupported
from hivetracered.models.openai_model import OpenAIModel


FORMAT = {"type": "json_schema", "json_schema": {"name": "prompts", "strict": True,
    "schema": {"type": "object", "properties": {"p1": {"type": "string"}},
               "required": ["p1"], "additionalProperties": False}}}


def answer(request, calls):
    payload = json.loads(request.content)
    calls.append(payload)
    return httpx.Response(200, json={"id": "test", "object": "chat.completion", "model": "test",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": '{"p1":"test"}'}}]})


def test_sync_invoke_and_batch_forward_and_clear_options():
    calls = []
    with httpx.Client(transport=httpx.MockTransport(lambda req: answer(req, calls))) as client:
        model = OpenAIModel("test", api_key="offline", base_url="https://mock.invalid", http_client=client,
            max_retries=1, rpm=600000, model_kwargs={"response_format": {"type": "json_object"}},
            extra_body={"response_format": {"type": "json_object"}, "vendor_option": True})
        model.invoke("native", response_format=FORMAT, temperature=0.7)
        model.batch(["plain", "plain"], response_format=None)
        assert calls[0]["response_format"] == FORMAT and calls[0]["temperature"] == 0.7
        assert all("response_format" not in call for call in calls[1:])
        assert all(call["vendor_option"] is True for call in calls)
        assert model.kwargs["extra_body"]["response_format"] == {"type": "json_object"}
        asyncio.run(model.aclose())


@pytest.mark.parametrize("method", ["ainvoke", "abatch", "stream_abatch"])
def test_async_options_are_request_local_and_client_is_reused(method):
    async def run():
        calls = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: answer(req, calls))) as client:
            async with OpenAIModel("test", api_key="offline", base_url="https://mock.invalid",
                http_async_client=client, max_retries=1, rpm=600000,
                model_kwargs={"response_format": {"type": "json_object"}}, max_concurrency=2) as model:
                original = model.client

                async def call(format_):
                    if method == "ainvoke":
                        return await model.ainvoke("test", response_format=format_)
                    if method == "abatch":
                        return await model.abatch(["test"], response_format=format_)
                    return [r async for r in model.stream_abatch(["test"], response_format=format_)]

                await asyncio.gather(call(FORMAT), call(None))
                assert model.client is original
                assert sum("response_format" in body for body in calls) == 1
                assert next(body for body in calls if "response_format" in body)["response_format"] == FORMAT
                assert model.kwargs["model_kwargs"]["response_format"] == {"type": "json_object"}
    asyncio.run(run())


@pytest.mark.parametrize("body,expected", [
    ({"error": {"message": "json_schema is unsupported", "code": "invalid_json_schema", "param": "response_format.json_schema.schema"}}, False),
    ({"error": {"message": "json_schema is unsupported", "code": "insufficient_quota"}}, False),
    ({"error": {"message": "response_format is not supported by this model", "param": "response_format"}}, True),
    ({"error": "Invalid request parameters", "details": {"_errors": ["response_format is not supported by this model"]}}, True),
])
def test_error_metadata_reaches_consumers_without_parsing_error_strings(body, expected):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(400, json=body))) as client:
            async with OpenAIModel("test", api_key="offline", base_url="https://mock.invalid",
                http_async_client=client, max_retries=1, rpm=600000) as model:
                result = await model.ainvoke("test", response_format=FORMAT)
                assert result["status_code"] == 400
                assert result["error_body"] == body
                assert is_response_format_unsupported(result) is expected
    asyncio.run(run())


@pytest.mark.parametrize("message", [
    "response_format.json_schema.schema: unsupported keyword 'patternProperties'",
    "Unknown parameter 'temperature' when response_format is json_schema",
    "Unsupported value 'high' for reasoning_effort with response_format=json_schema",
    "response_format.json_schema: unsupported type 'integer' for property p1",
    "insufficient_quota: response_format not available until balance is replenished",
    "response_format not available: maximum number of tokens exceeded",
    "json_schema is not supported for properties of type integer",
    "response_format is not supported when schema contains patternProperties",
    "response_format is not available because the account balance is zero",
    "response_format is not allowed because the prompt exceeds the maximum token limit",
])
def test_other_request_failures_are_not_capability_rejection(message):
    assert not is_response_format_unsupported({"error_type": "BadRequestError", "error": message})


@pytest.mark.parametrize("code,param", [
    ("invalid_json_schema", "response_format.json_schema.schema"),
    ("insufficient_quota", None), ("context_length_exceeded", None),
    ("invalid_request_error", "temperature"),
])
def test_metadata_overrides_generic_error_message(code, param):
    body = {"message": "json_schema is unsupported", "code": code, "param": param}
    assert not is_response_format_unsupported({"error_type": "BadRequestError", "error_body": body, "error": body["message"]})


def test_exception_classifier_preserves_sibling_http_metadata():
    import openai
    message = {"message": "json_schema is unsupported"}
    body = {"error": message, "details": {"issues": [{"code": "invalid_json_schema",
        "path": ["response_format", "json_schema", "schema"], "message": message["message"]}]}}
    exc = openai.BadRequestError(message["message"], body=message,
        response=httpx.Response(400, json=body, request=httpx.Request("POST", "https://mock.invalid")))
    assert not is_response_format_unsupported(exc)


@pytest.mark.parametrize("class_name", ["OpenAIModel", "OpenRouterModel", "VLLMModel", "CloudRuModel"])
@pytest.mark.parametrize("vendor_option", [False, True])
def test_nested_static_extra_body_cannot_override_per_call_format(class_name, vendor_option):
    import importlib
    import copy
    modules = {"OpenAIModel": "openai_model", "OpenRouterModel": "openrouter_model",
               "VLLMModel": "vllm_model", "CloudRuModel": "cloud_ru_model"}
    cls = getattr(importlib.import_module("hivetracered.models." + modules[class_name]), class_name)
    static = {"extra_body": {"response_format": {"type": "json_object"}}}
    if vendor_option:
        static["extra_body"]["vendor_option"] = True
    before = copy.deepcopy(static)

    async def run():
        calls = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: answer(req, calls))) as client:
            kwargs = {"rpm": 600000} if class_name != "VLLMModel" else {}
            async with cls(model="test", api_key="offline", base_url="https://mock.invalid",
                http_async_client=client, max_retries=1, model_kwargs=static, **kwargs) as model:
                original = model.client
                await model.ainvoke("native", response_format=FORMAT)
                await model.ainvoke("ordinary", response_format=None)
                assert model.client is original
        assert calls[0]["response_format"] == FORMAT
        assert "response_format" not in calls[1]
        assert static == before
        if vendor_option:
            assert all(body["vendor_option"] is True for body in calls)

    asyncio.run(run())


@pytest.mark.parametrize('message', [
    "response_format is not supported by this model",
    "Invalid parameter: 'response_format' of type 'json_schema' is not supported with this model.",
    "This model does not support structured outputs",
    "model vendor/test doesn't support json_schema",
    "Unknown parameter: response_format",
    "Unsupported response_format type: json_schema",
])
def test_explicit_capability_messages(message):
    assert is_response_format_unsupported({'error_type': 'BadRequestError', 'status_code': 400, 'error': message})


@pytest.mark.parametrize('status,kind', [(401, 'BadRequestError'), (500, 'BadRequestError'),
                                         (400, 'AuthenticationError'), (429, 'RateLimitError')])
def test_non_capability_failures_never_fallback(status, kind):
    assert not is_response_format_unsupported({'error_type': kind, 'status_code': status,
        'error': 'response_format is not supported by this model'})


def test_empty_metadata_path_does_not_hide_unrelated_parameter():
    assert not is_response_format_unsupported({'error_type': 'BadRequestError',
        'error_body': {'param': 'temperature', 'path': [], 'message': 'json_schema is unsupported'}})


def test_non_openai_transport_keeps_its_own_format_semantics():
    from hivetracered.models.langchain_model import LangchainModel
    class Client:
        received = None
        async def ainvoke(self, prompt, **options):
            self.received = options
            return {'content': 'custom'}
    class Custom(LangchainModel):
        def __init__(self):
            self.client = Client()
            self.model_name = 'custom'
    async def run():
        async with Custom() as model:
            assert await model.ainvoke('test', response_format=None) == {'content': 'custom'}
            assert model.client.received == {'response_format': None}
    asyncio.run(run())
