"""Unit tests for hivetracered.attacks.composed_attack.ComposedAttack.

Covers inner-then-outer composition order, default/custom name & description,
recursive get_params, and stream_abatch ordering.

The ``|`` operator itself lives on BaseAttack and is exercised by
test_attacks_base_attack.py, so it is not retested here.
"""

from __future__ import annotations

import pytest

from hivetracered.attacks.composed_attack import ComposedAttack
from hivetracered.attacks.template_attack import TemplateAttack
from tests.conftest import async_collect


def test_composed_attack_apply_string_runs_inner_then_outer():
    inner = TemplateAttack(template="[i]{prompt}")
    outer = TemplateAttack(template="[o]{prompt}")
    composed = ComposedAttack(outer_attack=outer, inner_attack=inner)

    result = composed.apply("X")

    # inner first: "[i]X", then outer wraps: "[o][i]X"
    assert result == "[o][i]X"


@pytest.mark.parametrize(
    ("kwargs", "method", "checker"),
    [
        ({}, "get_name", lambda v: v == "Composed(Outer ∘ Inner)"),
        ({"name": "MyCustom"}, "get_name", lambda v: v == "MyCustom"),
        ({}, "get_description", lambda v: "Inner" in v and "Outer" in v),
        ({"description": "custom desc"}, "get_description", lambda v: v == "custom desc"),
    ],
    ids=["default-name", "custom-name", "default-description", "custom-description"],
)
def test_composed_attack_name_and_description_defaults_and_overrides(kwargs, method, checker):
    inner = TemplateAttack(template="{prompt}", name="Inner")
    outer = TemplateAttack(template="{prompt}", name="Outer")

    composed = ComposedAttack(outer_attack=outer, inner_attack=inner, **kwargs)

    assert checker(getattr(composed, method)())


def test_composed_attack_get_params_returns_dict_with_recursive_inner_outer_params():
    inner = TemplateAttack(template="i-{prompt}", name="Inner", description="id")
    outer = TemplateAttack(template="o-{prompt}", name="Outer", description="od")
    composed = ComposedAttack(outer_attack=outer, inner_attack=inner)

    params = composed.get_params()

    assert set(params.keys()) == {"outer_attack", "inner_attack", "name", "description"}
    assert params["outer_attack"] == {
        "template": "o-{prompt}",
        "name": "Outer",
        "description": "od",
    }
    assert params["inner_attack"] == {
        "template": "i-{prompt}",
        "name": "Inner",
        "description": "id",
    }


def test_composed_attack_stream_abatch_applies_inner_then_outer_preserving_order():
    inner = TemplateAttack(template="[i]{prompt}")
    outer = TemplateAttack(template="[o]{prompt}")
    composed = ComposedAttack(outer_attack=outer, inner_attack=inner)
    prompts = ["a", "b", "c"]

    results = async_collect(composed.stream_abatch(prompts))

    assert results == ["[o][i]a", "[o][i]b", "[o][i]c"]


