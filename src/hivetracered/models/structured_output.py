import json
import logging
from contextlib import aclosing

from hivetracered.models.errors import is_response_format_unsupported

logger = logging.getLogger(__name__)


def object_format(properties):
    return {'type': 'json_schema', 'json_schema': {'name': 'output', 'strict': True,
        'schema': {'type': 'object', 'properties': properties,
                   'required': list(properties), 'additionalProperties': False}}}


def _unique_object(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError('Duplicate JSON key')
        data[key] = value
    return data


def check_response(response):
    if response.get('error'):
        raise RuntimeError(f"Model provider failed ({response.get('error_type', 'provider error')})")
    extra = response.get('additional_kwargs') or {}
    if response.get('refusal') or extra.get('refusal'):
        raise ValueError('Model refused generation')
    finish = (response.get('response_metadata') or {}).get('finish_reason', response.get('finish_reason'))
    if finish in {'length', 'max_tokens', 'content_filter', 'blacklist'}:
        raise ValueError(f'Incomplete model response: {finish}')


def _validate_value(value, field):
    types = {'string': (str,), 'integer': (int,), 'number': (int, float), 'boolean': (bool,)}
    if type(value) not in types[field['type']]:
        raise ValueError('Unexpected structured value type')
    if 'enum' in field and value not in field['enum']:
        raise ValueError('Unexpected structured value')


def parse_object(response, format_):
    check_response(response)
    content = response.get('content', '')
    if not isinstance(content, str):
        raise ValueError('Structured response must contain JSON text')
    data = json.loads(content, object_pairs_hook=_unique_object)
    properties = format_['json_schema']['schema']['properties']
    if not isinstance(data, dict) or set(data) != set(properties):
        raise ValueError('Structured response keys do not match the schema')
    for key, field in properties.items():
        _validate_value(data[key], field)
    return data


class OutputRequest:
    def __init__(self, model, format_=None, **options):
        self.model = model
        self.format = format_
        self.options = options

    def _mode(self):
        capable = bool(getattr(self.model, 'SUPPORTS_RESPONSE_FORMAT', False))
        native = capable and self.format is not None and not getattr(self.model, '_plain_output_only', False)
        options = dict(self.options)
        if capable:
            options['response_format'] = self.format if native else None
        logger.info('structured_requested=%s structured_effective=%s', self.format is not None, native)
        return native, options

    def _rejected(self, response, native):
        if native and response.get('error') and is_response_format_unsupported(response):
            self.model._plain_output_only = True
            logger.warning('fallback=ordinary reason=unsupported_response_format')
            return True
        return False

    def checked(self, response, native, nonempty=()):
        if response.get('error'):
            return response
        try:
            check_response(response)
            if native:
                data = parse_object(response, self.format)
                if any(not data[key].strip() for key in nonempty):
                    raise ValueError('Empty structured text')
                return {**response, 'structured_output': data}
            return response
        except (ValueError, TypeError) as exc:
            return {**response, 'error': str(exc), 'error_type': 'StructuredOutputError'}

    def invoke(self, prompt, ordinary_prompt=None):
        ordinary_prompt = prompt if ordinary_prompt is None else ordinary_prompt
        native, options = self._mode()
        response = self.model.invoke(prompt if native else ordinary_prompt, **options)
        if self._rejected(response, native):
            _, options = self._mode()
            return self.model.invoke(ordinary_prompt, **options), False
        return response, native

    async def _call(self, prompt, options):
        if hasattr(self.model, 'ainvoke'):
            return await self.model.ainvoke(prompt, **options)
        responses = await self.model.abatch([prompt], **options)
        return responses[0] if responses else {}

    async def ainvoke(self, prompt, ordinary_prompt=None):
        ordinary_prompt = prompt if ordinary_prompt is None else ordinary_prompt
        native, options = self._mode()
        response = await self._call(prompt if native else ordinary_prompt, options)
        if self._rejected(response, native):
            _, options = self._mode()
            return await self._call(ordinary_prompt, options), False
        return response, native

    async def _responses(self, prompts, options):
        if hasattr(self.model, 'stream_abatch'):
            async with aclosing(self.model.stream_abatch(prompts, **options)) as responses:
                async for response in responses:
                    yield response
        else:
            for response in await self.model.abatch(prompts, **options):
                yield response

    async def stream(self, prompts, ordinary_prompts=None):
        ordinary_prompts = prompts if ordinary_prompts is None else ordinary_prompts
        native, options = self._mode()
        start = 0
        if native and prompts:
            response, native = await self.ainvoke(prompts[0], ordinary_prompts[0])
            yield response, native
            start = 1
        if start == len(prompts):
            return
        native, options = self._mode()
        selected = prompts if native else ordinary_prompts
        async with aclosing(self._responses(selected[start:], options)) as responses:
            async for index, response in _enumerate(responses, start):
                if self._rejected(response, native):
                    yield await self.ainvoke(prompts[index], ordinary_prompts[index])
                else:
                    yield response, native


async def _enumerate(responses, start):
    async for response in responses:
        yield start, response
        start += 1
