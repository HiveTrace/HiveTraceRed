"""
Global constants and registry mappings for the pipeline module.
Centralizes model, attack, and evaluator class registrations to enable dynamic loading
and configuration based on string identifiers in configuration files.
"""

from typing import Dict, Any, Callable

# Import model classes
from hivetracered.models import GigaChatModel, OpenAIModel, YandexGPTModel, GeminiModel, GeminiNativeModel, CloudRuModel, OpenRouterModel, OllamaModel, LlamaCppModel
# Import all attack classes and types
from hivetracered.attacks.base_attack import BaseAttack

# Import attack classes from each type directly
from hivetracered.attacks.types.simple_instructions import __all__ as simple_instructions_all
from hivetracered.attacks.types.roleplay import __all__ as roleplay_all
from hivetracered.attacks.types.persuasion import __all__ as persuasion_all
from hivetracered.attacks.types.output_formatting import __all__ as output_formatting_all
from hivetracered.attacks.types.context_switching import __all__ as context_switching_all
from hivetracered.attacks.types.token_smuggling import __all__ as token_smuggling_all
from hivetracered.attacks.types.text_structure_modification import __all__ as text_structure_modification_all
from hivetracered.attacks.types.task_deflection import __all__ as task_deflection_all
from hivetracered.attacks.types.irrelevant_information import __all__ as irrelevant_information_all
from hivetracered.attacks.types.in_context_learning import __all__ as in_context_learning_all
from hivetracered.models.base_model import Model
from hivetracered.attacks import ModelAttack

# Import each attack class directly
from hivetracered.attacks.types import *

# Import evaluators
from hivetracered.evaluators import KeywordEvaluator, WildGuardGPTEvaluator, WildGuardGPTRuEvaluator, WildGuardGPTRuHalEvaluator, SystemPromptDetectionEvaluator

MODEL_CLASSES = {
    "gigachat": GigaChatModel,
    "gigachat-pro": GigaChatModel,
    "gigachat-max": GigaChatModel,
    "gigachat-2-pro": GigaChatModel,
    "gigachat-2-max": GigaChatModel,
    "gpt-3.5-turbo": OpenAIModel,
    "gpt-4": OpenAIModel,
    "gpt-4-turbo": OpenAIModel,
    "gpt-4.1-nano": OpenAIModel,
    "gpt-4.1-mini": OpenAIModel,
    "gpt-4.1": OpenAIModel,
    "yandexgpt": YandexGPTModel,
    "yandexgpt-lite": YandexGPTModel,
    "gemini-2.5-flash-preview-04-17": GeminiNativeModel,
    "gemini-1.5-pro": GeminiModel,
    "gemini-1.5-flash": GeminiModel,
    "gemini-2.5-pro-preview-03-25": GeminiModel,
    # SberCloud models
    "GigaChat/GigaChat-2-Max": CloudRuModel,
    "openai/gpt-oss-120b": CloudRuModel,
    "Qwen/Qwen3-Next-80B-A3B-Instruct": CloudRuModel,
    "meta-llama/Llama-3.3-70B-Instruct": CloudRuModel,
    "t-tech/T-pro-it-2.0": CloudRuModel,
    # OpenRouter models
    "x-ai/grok-4-fast:free": OpenRouterModel,
    "nvidia/nemotron-nano-9b-v2:free": OpenRouterModel,
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free": OpenRouterModel,
    "deepseek/deepseek-chat-v3.1:free": OpenRouterModel,
    "openai/gpt-oss-20b:free": OpenRouterModel,
    "qwen3:0.6b": OllamaModel,

    #Model classes
    "GigaChatModel": GigaChatModel,
    "OpenAIModel": OpenAIModel,
    "YandexGPTModel": YandexGPTModel,
    "GeminiNativeModel": GeminiNativeModel,
    "GeminiModel": GeminiModel,
    "CloudRuModel": CloudRuModel,
    "OpenRouterModel": OpenRouterModel,
    "OllamaModel": OllamaModel,
    "LlamaCppModel": LlamaCppModel,
}
"""Registry mapping model names to their implementation classes.
Allows dynamic instantiation of models based on configuration strings."""

ATTACK_TYPES = {
    "simple_instructions": simple_instructions_all,
    "roleplay": roleplay_all,
    "persuasion": persuasion_all,
    "output_formatting": output_formatting_all,
    "context_switching": context_switching_all,
    "token_smuggling": token_smuggling_all,
    "text_structure_modification": text_structure_modification_all,
    "task_deflection": task_deflection_all,
    "irrelevant_information": irrelevant_information_all,
    "in_context_learning": in_context_learning_all
}
"""Categorization of attack types and their corresponding attack classes.
Used for organizing attacks by their strategy/approach."""

ATTACK_CLASSES = {}
for attack_type, attack_names in ATTACK_TYPES.items():
    for attack_name in attack_names:
        ATTACK_CLASSES[attack_name] = {"attack_class": globals()[attack_name], "attack_type": attack_type}
"""Registry mapping attack names to their implementation classes and types.
Allows dynamic instantiation of attacks based on configuration strings."""

EVALUATOR_CLASSES: Dict[str, Any] = {
    "KeywordEvaluator": KeywordEvaluator,
    "WildGuardGPTEvaluator": WildGuardGPTEvaluator,
    "WildGuardGPTRuEvaluator": WildGuardGPTRuEvaluator,
    "WildGuardGPTRuHalEvaluator": WildGuardGPTRuHalEvaluator,
    "SystemPromptDetectionEvaluator": SystemPromptDetectionEvaluator,
}
"""Registry of available evaluator classes for assessing model responses.
Allows dynamic instantiation of evaluators based on configuration strings."""
