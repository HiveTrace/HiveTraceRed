import asyncio
import json

import pytest

from hivetracered.models.structured_output import OutputRequest, object_format, parse_object


class Model:
    SUPPORTS_RESPONSE_FORMAT = True
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []
    def invoke(self, prompt, **options):
        self.calls.append((prompt, options))
        return next(self.replies)
    async def ainvoke(self, prompt, **options):
        return self.invoke(prompt, **options)
    async def stream_abatch(self, prompts, **options):
        for prompt in prompts:
            yield self.invoke(prompt, **options)


FORMAT = object_format({'prompt': {'type': 'string'}})
REJECT = {'error': 'response_format is not supported by this model', 'error_type': 'BadRequestError', 'status_code': 400}


@pytest.mark.parametrize('method', ['sync', 'async', 'stream'])
def test_fallback_is_shared_by_requests_and_preserves_options(method):
    model = Model([REJECT, {'content': 'plain'}, {'content': 'again'}])
    request = OutputRequest(model, FORMAT, temperature=0.7)
    if method == 'sync':
        response, native = request.invoke('native', 'ordinary')
    elif method == 'async':
        response, native = asyncio.run(request.ainvoke('native', 'ordinary'))
    else:
        async def run():
            return [r async for r in request.stream(['native'], ['ordinary'])]
        response, native = asyncio.run(run())[0]
    assert response['content'] == 'plain' and native is False
    assert OutputRequest(model, FORMAT).invoke('native', 'ordinary')[0]['content'] == 'again'
    assert model.calls[0][1] == {'response_format': FORMAT, 'temperature': 0.7}
    assert model.calls[1][1] == {'response_format': None, 'temperature': 0.7}
    assert model.calls[2][1] == {'response_format': None}


@pytest.mark.parametrize('content', ['{"prompt": "a", "prompt": "b"}', '{"extra":"x"}', '{"prompt":12}', 'text {"prompt":"a"}'])
def test_strict_object_validation(content):
    with pytest.raises(ValueError):
        parse_object({'content': content}, FORMAT)


def test_enum_validation_rejects_wrong_type_and_unknown_value():
    format_ = object_format({'rating': {'type': 'integer', 'enum': list(range(1, 11))}})
    for value in [True, 0, 11, '7']:
        with pytest.raises(ValueError):
            parse_object({'content': json.dumps({'rating': value})}, format_)
    assert parse_object({'content': '{"rating":7}'}, format_) == {'rating': 7}


@pytest.mark.parametrize('reject', [False, True])
def test_attack_and_judge_share_real_transport_without_leaking_format(reject):
    import httpx
    from hivetracered.attacks.model_attack import ModelAttack
    from hivetracered.evaluators.scoring_judge_evaluator import ScoringJudgeEvaluator
    from hivetracered.models.openai_model import OpenAIModel
    calls = []
    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if reject and 'response_format' in body:
            return httpx.Response(400, json={'error': {'message': REJECT['error']}})
        judge = 'rating' in body['messages'][0]['content']
        content = json.dumps({'rating': 8}) if judge else 'rewritten'
        if not judge and 'response_format' in body:
            content = '{"prompt":"rewritten"}'
        return httpx.Response(200, json={'id': 'offline', 'object': 'chat.completion', 'model': 'offline',
            'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': content}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            async with OpenAIModel('offline', api_key='offline', base_url='https://mock.invalid',
                http_async_client=client, max_retries=1, rpm=600000,
                model_kwargs={'response_format': {'type': 'json_object'}}) as model:
                original = model.client
                transformed = [v async for v in ModelAttack(model, 'Rewrite {prompt}').stream_abatch(['hello'])]
                assert transformed == ['rewritten']
                result = [v async for v in ScoringJudgeEvaluator(model).stream_abatch(['hello'], transformed)][0]
                assert result['success'] and result['rating'] == 8
                result = ScoringJudgeEvaluator(model, structured_output=False)
                ordinary = [v async for v in result.stream_abatch(['hello'], transformed)][0]
                assert ordinary['rating'] == 8
                assert model.client is original
    asyncio.run(run())
    assert len(calls) == (4 if reject else 3)
    assert sum('response_format' in call for call in calls) == (1 if reject else 2)
    assert 'response_format' not in calls[-1]


@pytest.mark.parametrize('method', ['sync', 'async', 'stream'])
@pytest.mark.parametrize('status,kind', [(401, 'AuthenticationError'), (429, 'RateLimitError'), (500, 'InternalServerError'), (400, 'BadRequestError')])
def test_request_failures_do_not_trigger_fallback(method, status, kind):
    error = {'error': 'invalid request', 'status_code': status, 'error_type': kind}
    model = Model([error])
    request = OutputRequest(model, FORMAT)
    if method == 'sync':
        result = request.invoke('native', 'ordinary')
    elif method == 'async':
        result = asyncio.run(request.ainvoke('native', 'ordinary'))
    else:
        async def run():
            return [r async for r in request.stream(['native'], ['ordinary'])][0]
        result = asyncio.run(run())
    assert result == (error, True)
    assert len(model.calls) == 1


@pytest.mark.parametrize('extra', [{'refusal': 'no'}, {'additional_kwargs': {'refusal': 'no'}},
    {'finish_reason': 'length'}, {'response_metadata': {'finish_reason': 'content_filter'}}])
def test_incomplete_or_refused_structured_content_is_not_usable(extra):
    request = OutputRequest(Model([]), FORMAT)
    result = request.checked({'content': '{"prompt":"looks valid"}', **extra}, True, ('prompt',))
    assert result['error_type'] == 'StructuredOutputError'


def test_empty_native_attack_is_an_error():
    request = OutputRequest(Model([]), FORMAT)
    assert request.checked({'content': '{"prompt":"  "}'}, True, ('prompt',))['error']


@pytest.mark.parametrize('native', [False, True])
def test_closing_output_stream_closes_provider_stream(native):
    class Streaming(Model):
        closed = False
        async def stream_abatch(self, prompts, **options):
            try:
                for prompt in prompts:
                    yield {'content': '{"prompt":"next"}'}
            finally:
                self.closed = True
    model = Streaming([{'content': '{"prompt":"first"}'}])
    async def run():
        stream = OutputRequest(model, FORMAT if native else None).stream(['one', 'two', 'three'])
        await anext(stream)
        if native:
            await anext(stream)
        await stream.aclose()
        assert model.closed
    asyncio.run(run())


def test_format_requires_all_fields_and_disallows_extra_fields():
    format_ = object_format({'a': {'type': 'string'}, 'b': {'type': 'integer'}})['json_schema']
    assert format_['strict'] is True
    assert format_['schema']['required'] == ['a', 'b']
    assert format_['schema']['additionalProperties'] is False


def test_legacy_model_without_capability_or_single_call_protocol():
    class Legacy:
        def __init__(self):
            self.calls = []
        async def abatch(self, prompts):
            self.calls.extend(prompts)
            return [{'content': prompt} for prompt in prompts]
    model = Legacy()
    async def run():
        request = OutputRequest(model, FORMAT)
        assert await request.ainvoke('native', 'plain') == ({'content': 'plain'}, False)
        assert [r async for r in request.stream(['native'], ['ordinary'])] == [({'content': 'ordinary'}, False)]
    asyncio.run(run())
    assert model.calls == ['plain', 'ordinary']


def test_late_fallback_preserves_each_logical_request():
    model = Model([{'content': 'first'}, REJECT, {'content': 'second'}, REJECT, {'content': 'third'}])
    async def run():
        return [r async for r in OutputRequest(model, FORMAT).stream(
            ['native-one', 'native-two', 'native-three'], ['plain-one', 'plain-two', 'plain-three'])]
    assert [response['content'] for response, _ in asyncio.run(run())] == ['first', 'second', 'third']
    assert [prompt for prompt, _ in model.calls] == ['native-one', 'native-two', 'plain-two', 'native-three', 'plain-three']
