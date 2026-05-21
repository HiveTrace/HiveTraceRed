"""Unit tests for hivetracered.attacks.base_attack.BaseAttack.

Covers the abstract contract, the `__or__` composition operator's behavior on
both BaseAttack and non-BaseAttack right-hand-sides, and the default
`get_params` implementation.
"""

from __future__ import annotations

import pytest

from hivetracered.attacks.base_attack import BaseAttack
from hivetracered.attacks.composed_attack import ComposedAttack
from hivetracered.attacks.template_attack import TemplateAttack


def test_base_attack_or_with_baseattack_returns_composedattack_with_outer_and_inner():
    outer = TemplateAttack(template="O[{prompt}]")
    inner = TemplateAttack(template="I[{prompt}]")

    composed = outer | inner

    assert isinstance(composed, ComposedAttack)
    assert composed.outer_attack is outer
    assert composed.inner_attack is inner


def test_base_attack_or_with_non_baseattack_returns_notimplemented_then_typeerror():
    attack = TemplateAttack(template="{prompt}")

    # str has no __ror__ that handles BaseAttack, so Python re-raises TypeError.
    with pytest.raises(TypeError, match=r"unsupported operand type"):
        attack | "not-an-attack"  # type: ignore[operator]


def test_base_attack_get_params_default_returns_instance_dict():
    attack = TemplateAttack(template="T[{prompt}]", name="custom-name", description="d")

    params = attack.get_params()

    # TemplateAttack overrides get_params, so use a non-overriding subclass to
    # check the BaseAttack default. We verify the contract directly:
    class Minimal(BaseAttack):
        def __init__(self):
            self.x = 1
            self.y = "two"

        def apply(self, prompt):
            return prompt

        async def stream_abatch(self, prompts):
            for p in prompts:
                yield p

        def get_name(self):
            return "Minimal"

        def get_description(self):
            return "minimal attack"

    minimal = Minimal()
    assert minimal.get_params() == {"x": 1, "y": "two"}
    # Sanity: TemplateAttack overrode get_params, distinct from __dict__
    assert "template" in params
