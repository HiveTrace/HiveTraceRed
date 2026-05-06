"""Auto-discovery conformance tests for all registered models.

Two modes:
- Default (--all): registry checks + MockModel contract tests (free, no tokens)
- Specific (--model OpenAIModel): real API calls with the cheapest model (uses tokens)
"""

from __future__ import annotations

import inspect

import pytest

from hivetracered.models.base_model import Model
from hivetracered.pipeline.constants import MODEL_CLASSES
from tests.conftest import async_collect


# ── Deduplicate model classes (many names map to same class) ────────

UNIQUE_MODEL_CLASSES = list({
    cls.__name__: cls
    for cls in MODEL_CLASSES.values()
    if inspect.isclass(cls) and issubclass(cls, Model)
}.items())

# Cheapest model name per class for real API tests
DEFAULT_MODEL_NAMES = {
    "GigaChatModel": "gigachat",
    "OpenAIModel": "gpt-4.1-nano",
    "YandexGPTModel": "yandexgpt-lite",
    "GeminiNativeModel": "gemini-2.5-flash-preview-04-17",
    "GeminiModel": "gemini-1.5-flash",
    "CloudRuModel": "GigaChat/GigaChat-2-Max",
    "OpenRouterModel": "nvidia/nemotron-nano-9b-v2:free",
    "OllamaModel": "qwen3:0.6b",
    "VLLMModel": "vllm",
    "RestModel": None,
    "LlamaCppModel": None,
}


# ── Real model tests (uses tokens) ─────────────────────────────────

REAL_MODEL_CLASSES = [
    (name, cls)
    for name, cls in UNIQUE_MODEL_CLASSES
    if DEFAULT_MODEL_NAMES.get(name) is not None
]


@pytest.mark.real_model
@pytest.mark.parametrize(
    "class_name,model_class",
    REAL_MODEL_CLASSES,
    ids=[c[0] for c in REAL_MODEL_CLASSES],
)
class TestRealModelContract:
    """Tests real model classes with actual API calls. Uses tokens."""

    def _make_model(self, class_name, model_class):
        model_name = DEFAULT_MODEL_NAMES[class_name]
        return model_class(model=model_name)

    def _assert_successful_response(self, result, context=""):
        assert isinstance(result, dict), f"{context} expected dict, got {type(result).__name__}"
        assert "content" in result, f"{context} missing 'content' key"
        assert "error" not in result, f"{context} returned error: {result.get('error')}"
        assert len(result["content"]) > 0, f"{context} returned empty content"

    def test_invoke(self, class_name, model_class):
        model = self._make_model(class_name, model_class)
        result = model.invoke("Say hello")
        self._assert_successful_response(result, f"{class_name}.invoke")

    def test_invoke_message_list(self, class_name, model_class):
        model = self._make_model(class_name, model_class)
        result = model.invoke([{"role": "human", "content": "Say hello"}])
        self._assert_successful_response(result, f"{class_name}.invoke(message_list)")

    def test_stream_abatch(self, class_name, model_class):
        model = self._make_model(class_name, model_class)
        prompts = ["Say hi", "Say bye", "Say ok"]
        results = async_collect(model.stream_abatch(prompts))
        assert len(results) == 3
        for i, r in enumerate(results):
            self._assert_successful_response(r, f"{class_name}.stream_abatch[{i}]")

    def test_get_params(self, class_name, model_class):
        model = self._make_model(class_name, model_class)
        params = model.get_params()
        assert isinstance(params, dict)
