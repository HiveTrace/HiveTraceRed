"""
Global constants and registry mappings for the pipeline module.
Centralizes model, attack, and evaluator class registrations to enable dynamic loading
and configuration based on string identifiers in configuration files.
"""

from typing import Dict, Any, Callable
import sys
import os


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import model classes
from models import GigaChatModel, OpenAIModel, YandexGPTModel, GeminiModel, GeminiNativeModel

# Import all attack classes and types
from attacks.base_attack import BaseAttack

# Import attack classes from each type directly
from attacks.types.simple_instructions import __all__ as simple_instructions_all
from attacks.types.roleplay import __all__ as roleplay_all
from attacks.types.persuasion import __all__ as persuasion_all
from attacks.types.output_formatting import __all__ as output_formatting_all
from attacks.types.context_switching import __all__ as context_switching_all
from attacks.types.token_smuggling import __all__ as token_smuggling_all
from attacks.types.text_structure_modification import __all__ as text_structure_modification_all
from attacks.types.task_deflection import __all__ as task_deflection_all
from attacks.types.irrelevant_information import __all__ as irrelevant_information_all
from attacks.types.in_context_learning import __all__ as in_context_learning_all
from models.base_model import Model
from attacks import ModelAttack

# Import each attack class directly
from attacks.types import *

# Import evaluators
from evaluators import KeywordEvaluator, WildGuardGPTEvaluator, WildGuardGPTRuEvaluator

# Registry mapping model names to their implementation classes
# Allows dynamic instantiation of models based on configuration strings
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
}

# Categorization of attack types and their corresponding attack classes
# Used for organizing attacks by their strategy/approach
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

# Registry mapping attack names to their implementation classes and types
# Allows dynamic instantiation of attacks based on configuration strings
ATTACK_CLASSES = {}
for attack_type, attack_names in ATTACK_TYPES.items():
    for attack_name in attack_names:
        ATTACK_CLASSES[attack_name] = {"attack_class": globals()[attack_name], "attack_type": attack_type}

# Registry of available evaluator classes for assessing model responses
# Allows dynamic instantiation of evaluators based on configuration strings
EVALUATOR_CLASSES: Dict[str, Any] = {
    "KeywordEvaluator": KeywordEvaluator,
    "WildGuardGPTEvaluator": WildGuardGPTEvaluator,
    "WildGuardGPTRuEvaluator": WildGuardGPTRuEvaluator,
}

