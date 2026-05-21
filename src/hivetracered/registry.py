"""
Central registry for attacks, models, and evaluators.

Uses decorators for registration and pkgutil for auto-discovery,
eliminating the need for manual registry mappings in constants.py.

Usage::

    from hivetracered.registry import Registry

    @Registry.attack(category="roleplay")
    class DANAttack(TemplateAttack):
        ...

    @Registry.model()
    class OpenAIModel(LangchainModel):
        ...

    @Registry.evaluator()
    class KeywordEvaluator(BaseEvaluator):
        ...

    # At startup:
    Registry.discover("hivetracered.attacks.types")
    Registry.discover("hivetracered.models")
    Registry.discover("hivetracered.evaluators")
"""

import importlib
import logging
import pkgutil
from typing import Any

logger = logging.getLogger(__name__)


class Registry:
    """Central registry for attacks, models, and evaluators."""

    _attacks: dict[str, dict[str, Any]] = {}   # name -> {"class": cls, "category": str}
    _models: dict[str, type] = {}              # class_name -> cls
    _evaluators: dict[str, type] = {}          # class_name -> cls
    _discovered: set[str] = set()

    # ── decorators ────────────────────────────────────────────────────

    @classmethod
    def attack(cls, category: str, name: str | None = None):
        """Register an attack class under the given category.

        Args:
            category: Attack category (e.g. "roleplay", "persuasion").
            name: Override registration name (defaults to class name).
        """
        def decorator(attack_cls):
            cls._attacks[name or attack_cls.__name__] = {
                "class": attack_cls,
                "category": category,
            }
            return attack_cls
        return decorator

    @classmethod
    def model(cls):
        """Register a model class by its class name."""
        def decorator(model_cls):
            cls._models[model_cls.__name__] = model_cls
            return model_cls
        return decorator

    @classmethod
    def evaluator(cls):
        """Register an evaluator class by its class name."""
        def decorator(eval_cls):
            cls._evaluators[eval_cls.__name__] = eval_cls
            return eval_cls
        return decorator

    # ── discovery ─────────────────────────────────────────────────────

    @classmethod
    def discover(cls, package_path: str) -> None:
        """Import all modules in a package tree to trigger decorator registration.

        Safe to call multiple times — already-discovered packages are skipped.
        """
        if package_path in cls._discovered:
            return
        cls._discovered.add(package_path)

        try:
            package = importlib.import_module(package_path)
        except ImportError as e:
            logger.warning("Could not import package %s: %s", package_path, e)
            return

        if not hasattr(package, "__path__"):
            return

        for _importer, modname, _ispkg in pkgutil.walk_packages(
            package.__path__, prefix=package.__name__ + "."
        ):
            try:
                importlib.import_module(modname)
            except Exception as e:
                logger.warning("Skipped module %s: %s", modname, e)

    # ── introspection ─────────────────────────────────────────────────

    @classmethod
    def all_attacks(cls) -> dict[str, dict[str, Any]]:
        """Return a copy of the full attack registry."""
        return dict(cls._attacks)

    @classmethod
    def all_models(cls) -> dict[str, type]:
        """Return a copy of the full model registry."""
        return dict(cls._models)

    @classmethod
    def all_evaluators(cls) -> dict[str, type]:
        """Return a copy of the full evaluator registry."""
        return dict(cls._evaluators)

    @classmethod
    def attack_categories(cls) -> dict[str, list[str]]:
        """Return category -> [attack_names] mapping."""
        cats: dict[str, list[str]] = {}
        for name, info in cls._attacks.items():
            cats.setdefault(info["category"], []).append(name)
        return cats

    @classmethod
    def reset(cls) -> None:
        """Clear all registrations. Useful for testing."""
        cls._attacks.clear()
        cls._models.clear()
        cls._evaluators.clear()
        cls._discovered.clear()
