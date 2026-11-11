import asyncio
import json

import pytest

from hivetracered.attacks.model_attack import ModelAttack
from hivetracered.evaluators.scoring_judge_evaluator import ScoringJudgeEvaluator
from hivetracered.evaluators.wild_guard_ru_hal_evaluator import WildGuardGPTRuHalEvaluator


class Model:
    SUPPORTS_RESPONSE_FORMAT = True
    model_name = 'offline'
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
    def get_params(self):
        return {}


@pytest.mark.parametrize('method', ['apply', 'batch', 'stream'])
def test_model_attack_unwraps_native_prompt_and_preserves_chat(method):
    model = Model([{'content': '{"prompt":"rewritten"}'}])
    attack = ModelAttack(model, 'Rewrite: {prompt}')
    prompt = [{'role': 'system', 'content': 'context'}, {'role': 'human', 'content': 'original'}]
    async def run():
        if method == 'batch':
            return (await attack.batch([prompt]))[0]
        return [v async for v in attack.stream_abatch([prompt])][0]
    value = attack.apply(prompt) if method == 'apply' else asyncio.run(run())
    assert value == [prompt[0], {'role': 'human', 'content': 'rewritten'}]
    assert prompt[-1]['content'] == 'original'
    assert model.calls[0][1]['response_format']['type'] == 'json_schema'


@pytest.mark.parametrize('kind', ['attack', 'judge'])
def test_manual_mode_does_not_send_schema(kind):
    model = Model([{'content': 'plain' if kind == 'attack' else '{"rating":8}'}])
    if kind == 'attack':
        result = ModelAttack(model, '{prompt}', structured_output=False).apply('input')
        assert result == 'plain'
    else:
        result = ScoringJudgeEvaluator(model, structured_output=False).evaluate('input', 'response')
        assert result['score'] == 0.8
    assert model.calls[0][1]['response_format'] is None


def test_judge_validates_native_verdict_and_keeps_raw_response():
    response = {'content': json.dumps(dict(should_block='да', did_answer='отвечает', is_harmful='да', relevant='да'))}
    model = Model([response])
    result = WildGuardGPTRuHalEvaluator(model).evaluate('question', 'answer')
    assert result['success'] is True
    assert result['raw_evaluation'] is response
    assert model.calls[0][1]['response_format']['json_schema']['schema']['properties']['did_answer']['enum'] == ['отвечает', 'отказывается']


@pytest.mark.parametrize('content', ['{"rating":11}', '{"rating":"8"}', '{}', '{"rating":8,"extra":0}', '{"rating":8} trailing'])
def test_invalid_native_judge_result_is_an_error(content):
    model = Model([{'content': content}])
    result = ScoringJudgeEvaluator(model).evaluate('question', 'answer')
    assert result['success'] is False
    assert result['evaluation_error']
    assert len(model.calls) == 1


class Judge:
    def evaluate(self, prompt, response):
        return {'success': True, 'score': 1.0}
    async def stream_abatch(self, prompts, responses):
        for prompt in prompts:
            yield self.evaluate(prompt, responses[0])
    def get_name(self):
        return 'offline'


@pytest.mark.parametrize('kind', ['pair', 'tap', 'crescendo'])
@pytest.mark.parametrize('mode', ['native', 'manual', 'fallback'])
def test_iterative_and_conversational_attacks_only_format_attacker_requests(kind, mode):
    from hivetracered.attacks.types.single_turn.iterative.pair_attack import PAIRAttack
    from hivetracered.attacks.types.single_turn.iterative.tap_attack import TAPAttack
    from hivetracered.attacks.types.multi_turn.conversational.crescendo_attack import CrescendoAttack
    data = {'q': 'rewritten', 'summary': 'first'} if kind == 'crescendo' else {'improvement': '', 'prompt': 'rewritten'}
    replies = [{'content': json.dumps(data)}]
    if mode == 'fallback':
        replies.insert(0, {'error': 'response_format is not supported by this model', 'status_code': 400, 'error_type': 'BadRequestError'})
    attacker, target = Model(replies), Model([{'content': 'completed'}])
    params = dict(attacker_model=attacker, target_model=target, max_iterations=1, structured_output=mode != 'manual')
    if kind == 'crescendo':
        attack = CrescendoAttack(**params, success_judge=Judge(), max_rounds=1)
    else:
        cls = PAIRAttack if kind == 'pair' else TAPAttack
        attack = cls(**params, evaluator=Judge(), **({'max_depth': 0} if kind == 'tap' else {}))
    result = asyncio.run(attack.run_attack_async('goal'))
    assert result.success
    assert len(target.calls) == 1
    assert target.calls[0][1] == {}
    assert 'rewritten' in str(target.calls[0][0])
    assert bool(attacker.calls[0][1]['response_format']) is (mode != 'manual')
    if mode == 'fallback':
        assert len(attacker.calls) == 2
        assert attacker.calls[1][1] == {'response_format': None}


@pytest.mark.parametrize('error', [
    {'error': 'unauthorized', 'status_code': 401, 'error_type': 'AuthenticationError'},
    {'error': 'invalid schema', 'status_code': 400, 'error_type': 'BadRequestError'},
    {'error': 'rate limited', 'status_code': 429, 'error_type': 'RateLimitError'},
])
def test_component_provider_errors_do_not_switch_modes(error):
    attacker, judge = Model([error]), Model([error])
    async def run():
        return [v async for v in ModelAttack(attacker, '{prompt}').stream_abatch(['input'])][0]
    assert asyncio.run(run())[1]['attack_error'] == error['error']
    result = ScoringJudgeEvaluator(judge).evaluate('input', 'response')
    assert result['evaluation_error'] == error['error']
    assert result['success'] is False
    assert len(attacker.calls) == len(judge.calls) == 1


def test_registered_model_attacks_accept_manual_mode():
    from hivetracered.pipeline.constants import ATTACK_CLASSES
    for name in ['PastTenseAttack', 'TranslationAttack', 'TextContinuingAttack', 'UnsafeWordVariableFullAttack', 'AffirmationAttack']:
        attack = ATTACK_CLASSES[name]['attack_class'](model=Model([]), structured_output=False)
        assert attack.structured_output is False


@pytest.mark.parametrize('kind', ['en', 'ru', 'hal'])
def test_wildguard_native_fields_keep_original_success_rules(kind):
    from hivetracered.evaluators.wild_guard_evaluator import WildGuardGPTEvaluator
    from hivetracered.evaluators.wild_guard_ru_evaluator import WildGuardGPTRuEvaluator
    cls = {'en': WildGuardGPTEvaluator, 'ru': WildGuardGPTRuEvaluator, 'hal': WildGuardGPTRuHalEvaluator}[kind]
    for success in [True, False]:
        data = {key: field['enum'][0] for key, field in cls.OUTPUT_FIELDS.items()}
        data['is_harmful'] = ('yes' if success else 'no') if kind == 'en' else ('да' if success else 'нет')
        model = Model([{'content': json.dumps(data)}])
        judge = cls(model, 'custom name', 'custom description')
        assert judge.get_name() == 'custom name'
        assert judge.get_description() == 'custom description'
        assert judge.evaluate('question', 'answer')['success'] is success


@pytest.mark.parametrize('content,success', [('prefix {"answer":"YES"} suffix', True), ('not json', False)])
def test_custom_json_choice_evaluator_preserves_plain_mode(content, success):
    from hivetracered.evaluators.model_evaluator import ChoiceEvaluator
    class Judge(ChoiceEvaluator):
        OUTPUT_FIELDS = {'answer': {'type': 'string', 'enum': ['yes', 'no']}}
        PLAIN_FORMAT = 'json'
        SUCCESS_WHEN = {'answer': 'yes'}
    result = Judge(Model([{'content': content}]), structured_output=False).evaluate('question', 'answer')
    assert result['success'] is success
    if not success:
        assert result['evaluation_error']


@pytest.mark.parametrize('allowed,data,unsafe', [('yes', 'yes', 'no'), ('yes', 'no', 'yes'), ('yes', 'no', 'no'), ('no', 'yes', 'yes')])
def test_choice_evaluator_combines_required_and_alternative_conditions(allowed, data, unsafe):
    from hivetracered.evaluators.model_evaluator import ChoiceEvaluator
    class Judge(ChoiceEvaluator):
        OUTPUT_FIELDS = {key: {'type': 'string', 'enum': ['yes', 'no']} for key in ['allowed', 'data', 'unsafe']}
        SUCCESS_WHEN = {'allowed': 'yes'}
        ANY_SUCCESS = {'data': 'yes', 'unsafe': 'yes'}
    response = json.dumps({'allowed': allowed, 'data': data, 'unsafe': unsafe})
    result = Judge(Model([{'content': response}])).evaluate('question', 'answer')
    assert result['success'] is (allowed == 'yes' and 'yes' in [data, unsafe])


def test_custom_evaluator_can_default_an_absent_optional_answer():
    from hivetracered.evaluators.model_evaluator import ModelEvaluator
    class Judge(ModelEvaluator):
        def _parse_evaluation_response(self, response):
            answer = self._extract_answer(response['content'], r'Answer: (yes|no)?', 'missing')
            return {'answer': answer, 'success': answer == 'yes'}
    result = Judge(Model([{'content': 'Answer: '}]), '{response}').evaluate('question', 'answer')
    assert result == {'answer': 'missing', 'success': False}


def test_failed_first_native_request_does_not_drop_remaining_batch_records():
    error = {'error': 'context too long', 'error_type': 'BadRequestError', 'status_code': 400}
    attacker = Model([error, {'content': '{"prompt":"valid"}'}])
    judge = Model([error, {'content': '{"rating":8}'}])
    async def run():
        attacks = [v async for v in ModelAttack(attacker, '{prompt}').stream_abatch(['long input', 'short input'])]
        verdicts = [v async for v in ScoringJudgeEvaluator(judge).stream_abatch(['long input', 'short input'], ['answer', 'answer'])]
        return attacks, verdicts
    attacks, verdicts = asyncio.run(run())
    assert len(attacks) == len(verdicts) == 2
    assert attacks[0][1]['attack_error'] == error['error']
    assert attacks[1] == 'valid'
    assert verdicts[0]['evaluation_error'] == error['error']
    assert verdicts[1]['rating'] == 8


def test_custom_model_evaluator_declared_schema_is_enabled_by_default():
    from hivetracered.evaluators.model_evaluator import ModelEvaluator
    class Judge(ModelEvaluator):
        OUTPUT_FIELDS = {'rating': {'type': 'integer', 'enum': list(range(1, 11))}}
        def _parse_evaluation_response(self, response):
            rating = json.loads(response['content'])['rating']
            return {'rating': rating, 'success': rating >= 7}
    model = Model([{'content': '{"rating":8}'}])
    result = Judge(model, '{prompt} {response}').evaluate('question', 'answer')
    assert result['success'] is True
    assert model.calls[0][1]['response_format']['type'] == 'json_schema'
