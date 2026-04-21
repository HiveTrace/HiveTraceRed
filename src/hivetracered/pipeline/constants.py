"""
Global constants and registry mappings for the pipeline module.

Exposes backward-compatible mappings (MODEL_CLASSES, ATTACK_CLASSES,
ATTACK_TYPES, EVALUATOR_CLASSES) as live views over the Registry, so
classes registered after this module is imported are still visible.
"""

from collections.abc import Mapping
from typing import Any, Dict, Iterator, List

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


class _RegistryView(Mapping):
    """Read-only Mapping that reflects the current Registry state on every access."""

    def __init__(self, fetch):
        self._fetch = fetch

    def __getitem__(self, key):
        return self._fetch()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._fetch())

    def __len__(self) -> int:
        return len(self._fetch())

    def __contains__(self, key) -> bool:
        return key in self._fetch()

    def __repr__(self) -> str:
        return repr(self._fetch())


def _attack_classes_view() -> Dict[str, Dict[str, Any]]:
    return {
        name: {"attack_class": info["class"], "attack_type": info["category"]}
        for name, info in Registry.all_attacks().items()
    }


MODEL_CLASSES: Mapping[str, Any] = _RegistryView(Registry.all_models)
"""Live view mapping model class names to their implementation classes.
Pipeline configs specify the class plus the model name separately."""

ATTACK_CLASSES: Mapping[str, Dict[str, Any]] = _RegistryView(_attack_classes_view)
"""Live view mapping attack names to their implementation classes and types.
Allows dynamic instantiation of attacks based on configuration strings."""

ATTACK_TYPES: Mapping[str, List[str]] = _RegistryView(Registry.attack_categories)
"""Live view of category -> [attack_names]. Used for organizing attacks by strategy."""

EVALUATOR_CLASSES: Mapping[str, Any] = _RegistryView(Registry.all_evaluators)
"""Live view of available evaluator classes for assessing model responses."""
