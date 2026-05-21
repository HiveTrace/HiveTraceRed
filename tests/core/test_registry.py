"""Tests for hivetracered.registry.Registry.

Spec sources:
- Class docstring src/hivetracered/registry.py:37-38 ("Central registry for
  attacks, models, and evaluators.")
- Decorator/method docstrings src/hivetracered/registry.py:48-139:
    * attack(category, name=None) registers under {"class", "category"}
    * model() / evaluator() register by class name
    * discover(package_path) "Safe to call multiple times — already-discovered
      packages are skipped."
    * all_attacks/all_models/all_evaluators "Return a copy"
    * attack_categories: "Return category -> [attack_names] mapping."
    * reset(): "Clear all registrations."

Critical: Registry holds class-level state shared with the rest of the suite.
A class-scoped autouse fixture snapshots & restores _attacks/_models/_evaluators
/_discovered around every test in this file.
"""

from __future__ import annotations

import pytest

from hivetracered.registry import Registry


class TestRegistry:
    """All registry tests share a snapshot/restore fixture for global state."""

    @pytest.fixture(autouse=True)
    def _isolate_registry_state(self):
        # Snapshot
        attacks = dict(Registry._attacks)
        models = dict(Registry._models)
        evaluators = dict(Registry._evaluators)
        discovered = set(Registry._discovered)
        yield
        # Restore — full replacement of class-level dicts.
        Registry._attacks.clear()
        Registry._attacks.update(attacks)
        Registry._models.clear()
        Registry._models.update(models)
        Registry._evaluators.clear()
        Registry._evaluators.update(evaluators)
        Registry._discovered.clear()
        Registry._discovered.update(discovered)

    # ── attack decorator ──────────────────────────────────────────

    def test_attack_decorator_registers_class_under_category(self):
        Registry.reset()

        @Registry.attack(category="roleplay")
        class DummyAttack:
            pass

        all_attacks = Registry.all_attacks()
        assert "DummyAttack" in all_attacks
        entry = all_attacks["DummyAttack"]
        assert entry["class"] is DummyAttack
        assert entry["category"] == "roleplay"  # = arg passed to decorator

    def test_attack_decorator_with_name_override_uses_override(self):
        Registry.reset()

        @Registry.attack(category="persuasion", name="custom-name")
        class _AttackImpl:
            pass

        assert "custom-name" in Registry.all_attacks()  # = name kwarg
        assert "_AttackImpl" not in Registry.all_attacks()

    def test_attack_decorator_returns_class_unchanged(self):
        Registry.reset()
        original = type("OriginalAttack", (), {})

        wrapped = Registry.attack(category="x")(original)

        assert wrapped is original  # decorator must not wrap the class

    # ── model / evaluator decorators ──────────────────────────────

    @pytest.mark.parametrize(
        ("decorator_attr", "introspect_attr", "class_name"),
        [
            ("model", "all_models", "FooModel"),
            ("evaluator", "all_evaluators", "FooEvaluator"),
        ],
        ids=["model", "evaluator"],
    )
    def test_simple_decorator_registers_by_class_name(
        self, decorator_attr, introspect_attr, class_name
    ):
        Registry.reset()

        decorator = getattr(Registry, decorator_attr)()
        cls = decorator(type(class_name, (), {}))

        assert getattr(Registry, introspect_attr)() == {class_name: cls}

    # ── discover idempotence ──────────────────────────────────────

    def test_discover_called_twice_is_idempotent(self, monkeypatch):
        Registry.reset()
        call_count = {"n": 0}

        import hivetracered.registry as registry_mod
        original_import_module = registry_mod.importlib.import_module

        def counting_import_module(name, *args, **kwargs):
            if name == "hivetracered.evaluators":
                call_count["n"] += 1
            return original_import_module(name, *args, **kwargs)

        monkeypatch.setattr(registry_mod.importlib, "import_module", counting_import_module)

        Registry.discover("hivetracered.evaluators")
        Registry.discover("hivetracered.evaluators")

        assert call_count["n"] == 1  # = first call only; second was a no-op

    # ── return-value isolation ────────────────────────────────────

    @pytest.mark.parametrize(
        ("register", "introspect_attr", "injected_value"),
        [
            (
                lambda: Registry.attack(category="cat")(type("A", (), {})),
                "all_attacks",
                {"class": object, "category": "fake"},
            ),
            (
                lambda: Registry.model()(type("M", (), {})),
                "all_models",
                object,
            ),
            (
                lambda: Registry.evaluator()(type("E", (), {})),
                "all_evaluators",
                object,
            ),
        ],
        ids=["attacks", "models", "evaluators"],
    )
    def test_all_x_returns_copy_mutation_does_not_affect_registry(
        self, register, introspect_attr, injected_value
    ):
        Registry.reset()
        register()

        snapshot = getattr(Registry, introspect_attr)()
        snapshot["INJECTED"] = injected_value

        assert "INJECTED" not in getattr(Registry, introspect_attr)()

    # ── attack_categories grouping ────────────────────────────────

    def test_attack_categories_groups_attacks_by_category(self):
        Registry.reset()

        @Registry.attack(category="roleplay")
        class A1:
            pass

        @Registry.attack(category="roleplay")
        class A2:
            pass

        @Registry.attack(category="persuasion")
        class A3:
            pass

        cats = Registry.attack_categories()

        assert set(cats.keys()) == {"roleplay", "persuasion"}
        assert set(cats["roleplay"]) == {"A1", "A2"}  # = the two registered roleplay attacks
        assert cats["persuasion"] == ["A3"]

    def test_attack_categories_empty_when_no_attacks_registered(self):
        Registry.reset()

        assert Registry.attack_categories() == {}

    # ── reset ─────────────────────────────────────────────────────

    def test_reset_clears_all_buckets_and_discovered(self):
        Registry.reset()

        @Registry.attack(category="cat")
        class A:
            pass

        @Registry.model()
        class M:
            pass

        @Registry.evaluator()
        class E:
            pass

        Registry._discovered.add("some.pkg")

        Registry.reset()

        assert Registry.all_attacks() == {}
        assert Registry.all_models() == {}
        assert Registry.all_evaluators() == {}
        assert Registry._discovered == set()
