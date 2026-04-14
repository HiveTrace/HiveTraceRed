"""
Global constants and registry mappings for the pipeline module.

Populates backward-compatible dicts (MODEL_CLASSES, ATTACK_CLASSES,
ATTACK_TYPES, EVALUATOR_CLASSES) by auto-discovering decorated classes
via the Registry.
"""

from typing import Dict, Any, List

from hivetracered.registry import Registry

# Trigger discovery — importing these packages fires the @Registry decorators.
Registry.discover("hivetracered.models")
Registry.discover("hivetracered.attacks.types")
Registry.discover("hivetracered.evaluators")

# Re-export base classes for existing downstream imports.
from hivetracered.attacks.base_attack import BaseAttack
from hivetracered.models.base_model import Model
from hivetracered.attacks import ModelAttack
from hivetracered.attacks.iterative_attack import IterativeAttack

MODEL_CLASSES: Dict[str, Any] = dict(Registry.all_models())
"""Registry mapping model class names to their implementation classes.
Pipeline configs specify the class plus the model name separately."""

ATTACK_CLASSES: Dict[str, Dict[str, Any]] = {
    name: {"attack_class": info["class"], "attack_type": info["category"]}
    for name, info in Registry.all_attacks().items()
}
"""Registry mapping attack names to their implementation classes and types.
Allows dynamic instantiation of attacks based on configuration strings."""

ATTACK_TYPES: Dict[str, List[str]] = Registry.attack_categories()
"""Categorization of attack types and their corresponding attack classes.
Used for organizing attacks by their strategy/approach."""

EVALUATOR_CLASSES: Dict[str, Any] = dict(Registry.all_evaluators())
"""Registry of available evaluator classes for assessing model responses.
Allows dynamic instantiation of evaluators based on configuration strings."""
