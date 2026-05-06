"""Tests for hivetracered.pipeline.constants — registry-backed live views."""

from __future__ import annotations

import pytest

from hivetracered.pipeline.constants import (
    ATTACK_CLASSES,
    ATTACK_TYPES,
    EVALUATOR_CLASSES,
    MODEL_CLASSES,
)
from hivetracered.registry import Registry


# ── Registry teardown helpers ──────────────────────────────────────────


@pytest.fixture
def registry_attacks_snapshot():
    """Snapshot the attacks registry; restore exactly on teardown.

    Avoids Registry.reset(), which would wipe MODEL_CLASSES used elsewhere.
    """
    saved = dict(Registry._attacks)
    yield saved
    Registry._attacks.clear()
    Registry._attacks.update(saved)


# ── Mapping protocol on every view ─────────────────────────────────────


@pytest.mark.parametrize(
    ("view",),
    [(MODEL_CLASSES,), (ATTACK_CLASSES,), (ATTACK_TYPES,), (EVALUATOR_CLASSES,)],
    ids=["MODEL_CLASSES", "ATTACK_CLASSES", "ATTACK_TYPES", "EVALUATOR_CLASSES"],
)
def test_registry_view_supports_len_iter_contains_repr(view):
    # All four views are _RegistryView Mapping instances; they must support
    # the standard Mapping protocol (len, iter, __contains__, repr).
    length = len(view)
    items = list(iter(view))
    rendered = repr(view)

    assert length == len(items)
    assert all(item in view for item in items)
    assert rendered.startswith("{")  # = dict-style repr from _fetch()


# ── _RegistryView reflects live state ──────────────────────────────────


def test_attack_classes_view_reflects_new_registration(registry_attacks_snapshot):
    class _ProbeAttack:  # noqa: D401 - test probe
        pass

    before = len(ATTACK_CLASSES)
    Registry.attack(category="test_cat")(_ProbeAttack)
    after = len(ATTACK_CLASSES)

    assert "_ProbeAttack" in ATTACK_CLASSES
    assert after == before + 1
    assert ATTACK_CLASSES["_ProbeAttack"]["attack_type"] == "test_cat"


def test_attack_types_view_reflects_new_category(registry_attacks_snapshot):
    class _ProbeAttack2:
        pass

    Registry.attack(category="brand_new_cat")(_ProbeAttack2)

    assert "brand_new_cat" in ATTACK_TYPES
    assert "_ProbeAttack2" in ATTACK_TYPES["brand_new_cat"]


# ── ATTACK_CLASSES contains attacks but not evaluators ─────────────────


def test_attack_classes_lookup_evaluator_name_raises_keyerror():
    # KeywordEvaluator is in EVALUATOR_CLASSES, never ATTACK_CLASSES.
    with pytest.raises(KeyError, match=r"KeywordEvaluator"):
        ATTACK_CLASSES["KeywordEvaluator"]


def test_attack_classes_known_entry_has_attack_class_and_type_keys():
    # NoneAttack is the canonical baseline attack registered in attacks.types.
    entry = ATTACK_CLASSES["NoneAttack"]

    assert set(entry.keys()) == {"attack_class", "attack_type"}
    assert isinstance(entry["attack_type"], str)
    assert entry["attack_class"].__name__ == "NoneAttack"
