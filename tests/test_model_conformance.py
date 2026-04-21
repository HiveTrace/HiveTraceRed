"""Auto-discovery conformance tests for all registered models.

Two modes:
- Default (--all): registry checks + MockModel contract tests (free, no tokens)
- Specific (--model OpenAIModel): real API calls with the cheapest model (uses tokens)
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from hivetracered.models.base_model import Model
from hivetracered.pipeline.constants import MODEL_CLASSES
from tests.conftest import MockModel, async_collect


# ── Deduplicate model classes (many names map to same class) ────────

UNIQUE_MODEL_CLASSES = list({
    cls.__name__: cls
    for cls in MODEL_CLASSES.values()
    if inspect.isclass(cls) and issubclass(cls, Model)
}.items())

REQUIRED_METHODS = ["invoke", "ainvoke", "batch", "abatch", "stream_abatch", "get_params"]

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


# ── Registry & interface checks (no tokens) ────────────────────────


@pytest.mark.parametrize(
    "class_name,model_class",
    UNIQUE_MODEL_CLASSES,
    ids=[c[0] for c in UNIQUE_MODEL_CLASSES],
)
class TestModelRegistry:
    """Checks applied to every registered model class."""

    def test_is_model_subclass(self, class_name, model_class):
        assert issubclass(model_class, Model)

    def test_registration(self, class_name, model_class):
        assert class_name in MODEL_CLASSES

    def test_has_required_methods(self, class_name, model_class):
        for method in REQUIRED_METHODS:
            assert hasattr(model_class, method), (
                f"{class_name} missing required method '{method}'"
            )


# ── Model contract via MockModel (no tokens) ───────────────────────


class TestModelContract:
    """Tests the Model interface contract using MockModel."""

    def test_invoke_string(self):
        model = MockModel(response={"content": "hello"})
        result = model.invoke("test prompt")
        assert isinstance(result, dict)
        assert "content" in result
        assert result["content"] == "hello"

    def test_invoke_message_list(self):
        model = MockModel(response={"content": "hello"})
        result = model.invoke([{"role": "human", "content": "test"}])
        assert isinstance(result, dict)
        assert "content" in result

    def test_batch(self):
        model = MockModel(response={"content": "r"})
        results = model.batch(["a", "b"])
        assert isinstance(results, list)
        assert len(results) == 2
        assert all("content" in r for r in results)

    def test_abatch(self):
        model = MockModel(response={"content": "r"})
        results = asyncio.get_event_loop().run_until_complete(model.abatch(["a", "b"]))
        assert isinstance(results, list)
        assert len(results) == 2
        assert all("content" in r for r in results)

    def test_stream_abatch(self):
        model = MockModel(response={"content": "r"})
        results = async_collect(model.stream_abatch([f"p{i}" for i in range(5)]))
        assert len(results) == 5

    def test_stream_abatch_order(self):
        responses = [{"content": f"response {i}"} for i in range(5)]
        model = MockModel(side_effect=list(responses))
        results = async_collect(model.stream_abatch([f"p{i}" for i in range(5)]))
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result["content"] == f"response {i}"

    def test_get_params(self):
        model = MockModel()
        params = model.get_params()
        assert isinstance(params, dict)

    def test_is_answer_blocked(self):
        model = MockModel()
        result = model.is_answer_blocked({"content": "test"})
        assert isinstance(result, bool)


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
