"""
Models module providing a unified interface for interacting with various language model providers.
Implements adapters for OpenAI, GigaChat, Yandex GPT, and Gemini models with consistent API.
"""

from hivetracered.models.base_model import Model
from hivetracered.models.gigachat_model import GigaChatModel
from hivetracered.models.openai_model import OpenAIModel
from hivetracered.models.yandex_model import YandexGPTModel
from hivetracered.models.gemini_model import GeminiModel
from hivetracered.models.gemini_native_model import GeminiNativeModel
from hivetracered.models.cloud_ru_model import CloudRuModel
from hivetracered.models.openrouter_model import OpenRouterModel
from hivetracered.models.ollama_model import OllamaModel
from hivetracered.models.llamacpp_model import LlamaCppModel

# Optional web models that require playwright
try:
    from hivetracered.models.web_model import WebModel
    from hivetracered.models.mistral_web_model import MistralWebModel
    _WEB_MODELS_AVAILABLE = True
except ImportError:
    WebModel = None
    MistralWebModel = None
    _WEB_MODELS_AVAILABLE = False

__all__ = [
    "Model",
    "GigaChatModel",
    "OpenAIModel",
    "YandexGPTModel",
    "GeminiModel",
    "GeminiNativeModel",
    "CloudRuModel",
    "OpenRouterModel",
    "OllamaModel",
    "LlamaCppModel",
]

if _WEB_MODELS_AVAILABLE:
    __all__.extend(["WebModel", "MistralWebModel"])
