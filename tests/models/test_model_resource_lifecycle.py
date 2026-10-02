"""Real SDK + HTTP keep-alive regression tests; never call production models."""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

import httpx
import pytest

from hivetracered.models.openai_model import OpenAIModel
from hivetracered.models.resources import ModelResources
from hivetracered.pipeline import stream_model_responses


@pytest.fixture
def endpoint():
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self, *args):
            pass
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            with self.server.lock:
                self.server.active += 1
                self.server.peak = max(self.server.peak, self.server.active)
                self.server.requests += 1
            try:
                time.sleep(.02)
                body = json.dumps({
                    'id': 'mock', 'object': 'chat.completion', 'created': 1,
                    'model': request['model'], 'choices': [{'index': 0,
                        'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': '测试回答'}}],
                    'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
                }).encode()
                if getattr(self.server, 'status_code', 200) != 200:
                    body = json.dumps({'error': {'message': 'request failed', 'type': 'invalid_request_error'}}).encode()
                self.send_response(getattr(self.server, 'status_code', 200))
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with self.server.lock:
                    self.server.active -= 1
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    server.active = server.peak = server.requests = 0
    server.lock = threading.Lock()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1', server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def make_model(url, cls=OpenAIModel, **kwargs):
    m = cls(model='mock', api_key='mock', base_url=url, timeout=120,
            max_retries=1, max_concurrency=2, **kwargs)
    m.client.bound.rate_limiter = None
    return m


@pytest.mark.parametrize('adapter', ['openai', 'openrouter', 'cloudru', 'vllm'])
def test_sequential_runs_close_clients_and_preserve_concurrency(endpoint, adapter):
    from hivetracered.models.cloud_ru_model import CloudRuModel
    from hivetracered.models.openrouter_model import OpenRouterModel
    from hivetracered.models.vllm_model import VLLMModel
    cls = {'openai': OpenAIModel, 'openrouter': OpenRouterModel,
           'cloudru': CloudRuModel, 'vllm': VLLMModel}[adapter]
    url, server = endpoint
    created = []
    async def run():
        async with ModelResources():
            attacker, target = make_model(url, cls), make_model(url, cls)
            created.extend((attacker, target))
            assert attacker.client.bound.http_async_client is not target.client.bound.http_async_client
            # Attacker, target, then an evaluator using the same target instance.
            for model in (attacker, target, target):
                rows = [r async for r in stream_model_responses(
                    model, [{'prompt': f'test {i}'} for i in range(6)], consecutive_failures=0)]
                assert len(rows) == 6
                assert all(r['response'] == '测试回答' and not r.get('error') for r in rows)
    for _ in range(3):
        asyncio.run(run())
    assert server.requests == 54
    assert server.peak == 2
    for model in created:
        assert model.client.bound.http_client.is_closed
        assert model.client.bound.http_async_client.is_closed
        assert not model._pending_requests
        asyncio.run(model.aclose())  # idempotent even after its loop has closed


def test_borrowed_transports_are_not_closed(endpoint):
    url, _ = endpoint
    async def run():
        with httpx.Client() as sync:
            async with httpx.AsyncClient() as async_client:
                async with ModelResources():
                    model = make_model(url, http_client=sync, http_async_client=async_client)
                    assert (await model.ainvoke('test'))['content'] == '测试回答'
                assert not sync.is_closed and not async_client.is_closed
    asyncio.run(run())


def test_cross_loop_use_is_rejected_before_network_request(endpoint):
    url, server = endpoint
    model = make_model(url)
    owner = asyncio.new_event_loop()
    try:
        assert owner.run_until_complete(model.ainvoke('first'))['content'] == '测试回答'
        with pytest.raises(RuntimeError, match='another event loop'):
            asyncio.run(model.ainvoke('second'))
        assert server.requests == 1
        owner.run_until_complete(model.aclose())
    finally:
        owner.close()
    with pytest.raises(RuntimeError, match='closed'):
        asyncio.run(model.ainvoke('third'))


def test_constructor_failure_closes_already_created_clients(monkeypatch):
    from hivetracered.models import openai_model
    created = []
    def broken_chat(**kwargs):
        created.extend((kwargs['http_client'], kwargs['http_async_client']))
        raise ValueError('invalid model options')
    monkeypatch.setattr(openai_model, 'ChatOpenAI', broken_chat)
    async def run():
        with pytest.raises(ValueError, match='invalid model options'):
            async with ModelResources():
                OpenAIModel(model='mock', api_key='mock')
        assert all(client.is_closed for client in created)
    asyncio.run(run())


def test_cancellation_drains_active_and_queued_requests(endpoint):
    url, _ = endpoint
    models = []
    async def pipeline():
        async with ModelResources():
            model = make_model(url)
            models.append(model)
            # More requests than slots: cleanup must also cancel semaphore waiters.
            await model.abatch(['test'] * 100)
    async def run():
        task = asyncio.create_task(pipeline())
        while not models or len(models[0]._pending_requests) < 100:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        model = models[0]
        assert not model._pending_requests
        assert model.client.bound.http_async_client.is_closed
        assert model.client.bound.http_client.is_closed
    asyncio.run(run())


def test_scope_closes_remaining_models_if_one_cleanup_fails():
    closed = []
    async def run():
        with pytest.raises(ValueError, match='cleanup failed'):
            async with ModelResources():
                first = OpenAIModel(model='mock', api_key='mock')
                second = OpenAIModel(model='mock', api_key='mock')
                def record():
                    closed.append('first')
                def fail():
                    raise ValueError('cleanup failed')
                first._add_cleanup(record)
                second._add_cleanup(fail)
        assert closed == ['first']
        assert first.client.bound.http_async_client.is_closed
        assert second.client.bound.http_async_client.is_closed
    asyncio.run(run())


@pytest.mark.parametrize('adapter', ['ollama', 'gigachat', 'gemini'])
def test_native_sdk_clients_are_closed_without_network_calls(adapter):
    async def run():
        async with ModelResources():
            if adapter == 'ollama':
                from hivetracered.models.ollama_model import OllamaModel
                model = OllamaModel()
                raw = model.client.bound
                sync, async_client = raw._client._client, raw._async_client._client
            elif adapter == 'gigachat':
                from hivetracered.models.gigachat_model import GigaChatModel
                model = GigaChatModel(credentials='test')
                sdk = model.client.bound._client
                sync, async_client = sdk._client, sdk._aclient
            else:
                from hivetracered.models.gemini_model import GeminiModel
                model = GeminiModel(google_api_key='test')
                raw = model.client.bound
                sdk = raw.client
        if adapter == 'gemini':
            assert sdk._api_client._httpx_client.is_closed
            if sdk._api_client._async_httpx_client is not None:
                assert sdk._api_client._async_httpx_client.is_closed
            if hasattr(raw, '_client_cleanup'):
                assert raw._client_cleanup._closed
            else:
                assert raw.client is None  # Prevent late destructor cleanup on a new loop.
        else:
            assert sync.is_closed and async_client.is_closed
    asyncio.run(run())


def test_openai_proxy_is_compatible_with_owned_transports():
    async def run():
        async with OpenAIModel(model='mock', api_key='test', openai_proxy='http://127.0.0.1:12345') as model:
            assert model.client.bound.openai_proxy is None
            assert model.client.bound.http_client is not None
    asyncio.run(run())


def test_yandex_channels_close_on_sdk_loop(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from hivetracered.models import yandex_model
    sdk_loop = asyncio.new_event_loop()
    ready = threading.Event()
    def run_sdk():
        asyncio.set_event_loop(sdk_loop)
        sdk_loop.call_soon(ready.set)
        sdk_loop.run_forever()
    thread = threading.Thread(target=run_sdk)
    thread.start()
    ready.wait()
    closed_on = []
    class Channel:
        async def close(self):
            closed_on.append(asyncio.get_running_loop())
    channels = {'mock': Channel()}
    sdk = MagicMock()
    sdk._client = SimpleNamespace(_channels=channels)
    sdk._get_event_loop.return_value = sdk_loop
    monkeypatch.setattr(yandex_model, 'AIStudio', lambda **kwargs: sdk)
    async def run():
        async with ModelResources():
            yandex_model.YandexGPTModel(api_key='mock', folder_id='mock')
        assert closed_on == [sdk_loop]
        assert channels == {}
    try:
        asyncio.run(run())
        assert sdk_loop.is_running()  # Other SDK instances still own this loop.
    finally:
        sdk_loop.call_soon_threadsafe(sdk_loop.stop)
        thread.join()
        sdk_loop.close()


@pytest.mark.parametrize('kind', ['pair', 'tap'])
@pytest.mark.parametrize('shared', [False, True])
def test_sync_iterative_attack_reuses_loop_for_two_goals(endpoint, kind, shared):
    from hivetracered.attacks.types.single_turn.iterative.pair_attack import PAIRAttack
    from hivetracered.attacks.types.single_turn.iterative.tap_attack import TAPAttack
    from hivetracered.evaluators.model_evaluator import ModelEvaluator
    class Judge(ModelEvaluator):
        def _parse_evaluation_response(self, response):
            return {'success': True, 'score': 1.0}
    url, server = endpoint
    attacker = make_model(url)
    target = attacker if shared else make_model(url)
    judge_model = attacker if shared else make_model(url)
    evaluator = Judge(model=judge_model, evaluation_prompt_template='{prompt}\n{response}')
    cls = PAIRAttack if kind == 'pair' else TAPAttack
    kwargs = {'max_depth': 0} if kind == 'tap' else {}
    attack = cls(attacker_model=attacker, target_model=target,
                 evaluator=evaluator, max_iterations=1, **kwargs)
    try:
        assert attack.apply('goal one') == '测试回答'
        owner = attacker._request_loop
        assert attack.apply('goal two') == '测试回答'
        assert attacker._request_loop is owner and target._request_loop is owner
        assert judge_model._request_loop is owner
        assert server.requests == 6
    finally:
        if hasattr(attack, 'close'):
            attack.close()
    assert owner.is_closed()
    assert attacker.client.bound.http_async_client.is_closed
    assert target.client.bound.http_async_client.is_closed
    assert judge_model.client.bound.http_async_client.is_closed
    attack.close()  # closing twice is safe


@pytest.mark.parametrize('method', ['invoke', 'ainvoke', 'abatch'])
def test_closed_model_lifecycle_errors_propagate_before_requests(endpoint, method):
    url, server = endpoint
    model = make_model(url)
    asyncio.run(model.aclose())
    with pytest.raises(RuntimeError, match='closed'):
        if method == 'invoke':
            model.invoke('test')
        elif method == 'ainvoke':
            asyncio.run(model.ainvoke('test'))
        else:
            asyncio.run(model.abatch(['first', 'second']))
    assert server.requests == 0


def test_wrong_loop_batch_error_propagates_without_requests(endpoint):
    url, server = endpoint
    model = make_model(url)
    owner = asyncio.new_event_loop()
    try:
        owner.run_until_complete(model.ainvoke('first'))
        with pytest.raises(RuntimeError, match='another event loop'):
            asyncio.run(model.abatch(['second', 'third']))
        assert server.requests == 1
        owner.run_until_complete(model.aclose())
    finally:
        owner.close()


def test_sync_attack_context_closes_clients_after_failure(endpoint):
    from hivetracered.attacks.base_attack import AttackModelError
    from hivetracered.attacks.types.single_turn.iterative.pair_attack import PAIRAttack
    from hivetracered.evaluators.keyword_evaluator import KeywordEvaluator
    url, server = endpoint
    attacker, target = make_model(url), make_model(url)
    server.status_code = 400
    attack = PAIRAttack(attacker_model=attacker, target_model=target,
                        evaluator=KeywordEvaluator(keywords=['test']), max_iterations=1)
    with pytest.raises(AttackModelError, match='request failed'):
        with attack:
            attack.apply('goal')
    assert attack._sync_loop.is_closed()
    assert attacker.client.bound.http_async_client.is_closed
    assert target.client.bound.http_async_client.is_closed
    assert server.requests == 1
    with pytest.raises(RuntimeError, match='closed'):
        attack.apply('another goal')


def test_sync_attack_in_running_loop_fails_without_creating_private_loop(endpoint):
    from hivetracered.attacks.types.single_turn.iterative.pair_attack import PAIRAttack
    from hivetracered.evaluators.keyword_evaluator import KeywordEvaluator
    url, server = endpoint
    async def run():
        async with ModelResources():
            model = make_model(url)
            attack = PAIRAttack(attacker_model=model, target_model=model,
                evaluator=KeywordEvaluator(keywords=['test']), max_iterations=1)
            with pytest.raises(RuntimeError, match='run_attack_async'):
                attack.apply('goal')
            assert attack._sync_loop is None
            attack.close()
    asyncio.run(run())
    assert server.requests == 0
