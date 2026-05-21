"""Unit tests for hivetracered.attacks.template_attack.TemplateAttack.

Covers __init__ storage, apply() across str / list / invalid inputs,
stream_abatch ordering, name/description fallbacks, and get_params shape.
"""

from __future__ import annotations

import pytest

from hivetracered.attacks.template_attack import TemplateAttack
from tests.conftest import async_collect


def test_template_attack_apply_list_with_non_human_last_role_raises_valueerror():
    attack = TemplateAttack(template="W[{prompt}]")
    msgs = [{"role": "ai", "content": "assistant text"}]

    with pytest.raises(ValueError, match=r"Last message in prompt is not a human message"):
        attack.apply(msgs)


@pytest.mark.parametrize(
    "bad_prompt",
    [42, None, {"role": "human", "content": "x"}, 3.14],
    ids=["int", "none", "dict", "float"],
)
def test_template_attack_apply_with_invalid_prompt_type_raises_valueerror(bad_prompt):
    attack = TemplateAttack(template="{prompt}")

    with pytest.raises(ValueError, match=r"Prompt is not a string or list of messages"):
        attack.apply(bad_prompt)


@pytest.mark.parametrize(
    ("prompts", "expected"),
    [
        (
            ["a", "b", "c", "d"],
            ["<a>", "<b>", "<c>", "<d>"],
        ),
        (
            [
                [{"role": "human", "content": "x"}],
                [{"role": "human", "content": "y"}],
            ],
            [
                [{"role": "human", "content": "<x>"}],
                [{"role": "human", "content": "<y>"}],
            ],
        ),
    ],
    ids=["strings", "message-lists"],
)
def test_template_attack_stream_abatch_yields_one_per_input_in_order(prompts, expected):
    attack = TemplateAttack(template="<{prompt}>")

    results = async_collect(attack.stream_abatch(prompts))

    assert results == expected


@pytest.mark.parametrize(
    ("name_kwarg", "expected"),
    [("MyName", "MyName"), (None, "TemplateAttack")],
    ids=["custom", "default"],
)
def test_template_attack_get_name(name_kwarg, expected):
    attack = TemplateAttack(template="{prompt}", name=name_kwarg)

    assert attack.get_name() == expected


@pytest.mark.parametrize(
    ("kwargs", "check"),
    [
        ({"description": "my description"}, lambda d: d == "my description"),
        ({}, lambda d: "UNIQUE_TEMPLATE_TOKEN_{prompt}" in d),
    ],
    ids=["custom", "default"],
)
def test_template_attack_get_description(kwargs, check):
    template = "UNIQUE_TEMPLATE_TOKEN_{prompt}"
    attack = TemplateAttack(template=template, **kwargs)

    assert check(attack.get_description())


def test_template_attack_get_params_returns_dict_with_template_name_description():
    attack = TemplateAttack(template="X{prompt}", name="N", description="D")

    params = attack.get_params()

    assert params == {"template": "X{prompt}", "name": "N", "description": "D"}
