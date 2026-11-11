import asyncio
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from hivetracered.attacks.model_attack import ModelAttack
from hivetracered.pipeline.constants import ATTACK_CLASSES


ROOT = Path(__file__).resolve().parents[3]
INPUT = 'INPUT_SENTINEL_71'


def cases():
    result = []
    for path in sorted((ROOT / 'src/hivetracered/attacks/types').rglob('*.yaml')):
        spec = yaml.safe_load(path.read_text())
        if spec['base'] == 'model':
            result.append((spec['class_name'], spec['class_name'], {}))
    result.extend((name, name, {}) for name in ['PastTenseAttack', 'TranslationAttack', 'TextContinuingAttack', 'UnsafeWordVariableFullAttack'])
    result.append(('TranslationAttackEnglish', 'TranslationAttack', {'source_language': 'english', 'target_language': 'french'}))
    return result


CASES = cases()


class Model:
    SUPPORTS_RESPONSE_FORMAT = True
    def __init__(self, reject=False):
        self.calls = []
        self.reject = reject
    def invoke(self, prompt, **options):
        self.calls.append((prompt, options))
        if self.reject and options.get('response_format'):
            return {'error': 'response_format is not supported by this model', 'status_code': 400, 'error_type': 'BadRequestError'}
        content = json.dumps({'prompt': 'RESULT'}) if options.get('response_format') else 'RESULT'
        return {'content': content}
    async def ainvoke(self, prompt, **options):
        return self.invoke(prompt, **options)
    async def stream_abatch(self, prompts, **options):
        for prompt in prompts:
            yield self.invoke(prompt, **options)


def attack(name, model, params, **overrides):
    return ATTACK_CLASSES[name]['attack_class'](model=model, **params, **overrides)


@pytest.mark.parametrize('case,name,params', CASES)
@pytest.mark.parametrize('mode', ['manual', 'unsupported', 'fallback'])
def test_ordinary_prompts_are_unchanged(case, name, params, mode):
    snapshots = json.loads((ROOT / 'tests/fixtures/ordinary_attack_prompts.json').read_text())
    model = Model(reject=mode == 'fallback')
    if mode == 'unsupported':
        model.SUPPORTS_RESPONSE_FORMAT = False
    instance = attack(name, model, params, structured_output=mode != 'manual')
    instance.apply(INPUT)
    actual = model.calls[-1][0]
    assert hashlib.sha256(actual.encode()).hexdigest() == snapshots[case]
    if mode == 'fallback':
        assert len(model.calls) == 2
        assert model.calls[0][0] != model.calls[1][0]


@pytest.mark.parametrize('case,name,params', CASES)
@pytest.mark.parametrize('method', ['apply', 'batch', 'stream'])
def test_native_prompt_has_no_plain_output_directives(case, name, params, method):
    model = Model()
    instance = attack(name, model, params)
    async def run():
        if method == 'batch':
            return await instance.batch([INPUT])
        return [result async for result in instance.stream_abatch([INPUT])]
    instance.apply(INPUT) if method == 'apply' else asyncio.run(run())
    prompt, options = model.calls[0]
    assert options['response_format']['json_schema']['strict'] is True
    assert 'начни ответ с' not in prompt.lower()
    assert 'Начни с "Переведенный текст:"' not in prompt
    assert 'Begin with "Translated text:"' not in prompt
    assert 'Начни с "Вот преобразованный запрос:"' not in prompt
    assert 'ответь ТОЛЬКО первым найденным небезопасным словом' not in prompt
    assert 'response schema' in prompt
    assert not any(token in prompt for token in ['{output_instruction}', '{output_prefix}'])
    trailing = prompt.split(INPUT)[-1]
    for prefix in ['Преобразованный промпт:', 'Преобразованный запрос:', 'Запрос в прошедшем времени:',
                   'Переведенный текст:', 'Translated text:', 'Небезопасное слово:',
                   'Изменённый запрос с неуместной информацией:']:
        assert prefix not in trailing


def test_native_result_is_preserved_verbatim():
    value = 'Начало\nИсходное намерение: это часть текста\nПреобразованный промпт: оставить внутри.'
    class Native(Model):
        def invoke(self, prompt, **options):
            return {'content': json.dumps({'prompt': value})}
    assert ModelAttack(Native(), '{prompt}').apply(INPUT) == value


@pytest.mark.parametrize('value', ['  Текст с форматированием\n', 'Цитата «Вот преобразованный запрос:» — часть результата.'])
def test_text_continuing_preserves_native_result_text(value):
    class Native(Model):
        def invoke(self, prompt, **options):
            return {'content': json.dumps({'prompt': value})}
    instance = attack('TextContinuingAttack', Native(), {'raw_prompt': True})
    assert instance.apply(INPUT) == value


def test_unsafe_word_native_prompt_preserves_first_word_and_no_match_rules():
    model = Model()
    attack('UnsafeWordVariableFullAttack', model, {}).apply(INPUT)
    prompt = model.calls[0][0]
    assert 'результат — первое найденное небезопасное слово в исходном виде' in prompt
    assert 'результат — строка "НИ ОДНОГО"' in prompt


def test_custom_attack_can_separate_semantics_and_plain_format():
    model = Model(reject=True)
    instance = ModelAttack(model, 'Rewrite {prompt}.{output_instruction}\n{output_prefix}',
        output_instruction=' Start with Result:', output_prefix='Result: ')
    instance.apply(INPUT)
    assert model.calls[0][0].startswith(f'Rewrite {INPUT}.\n')
    assert 'Start with Result:' not in model.calls[0][0]
    assert model.calls[1][0] == f'Rewrite {INPUT}. Start with Result:\nResult: '
