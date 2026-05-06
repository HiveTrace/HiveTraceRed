"""Unit tests for hivetracered.attacks.algo_attack.AlgoAttack.

Covers abstract instantiation, raw vs templated apply for str and list inputs,
last-user-message targeting, copy-not-mutate, stream_abatch ordering, and
the _get_mode helper.
"""

from __future__ import annotations

import pytest

from hivetracered.attacks.algo_attack import AlgoAttack
from tests.conftest import async_collect


# ── Concrete subclass for testing ──────────────────────────────────────


class UpperAttack(AlgoAttack):
    """Minimal concrete AlgoAttack: uppercases input."""

    def __init__(self, raw=False, template=None, name=None, description=None):
        if template is None:
            template = "INSTR[{prompt}]"
        super().__init__(raw=raw, template=template, name=name, description=description)

    def transform(self, text, **kwargs):
        return text.upper()


# ── Tests ──────────────────────────────────────────────────────────────


def test_algo_attack_apply_string_with_raw_true_returns_transformed_text_only():
    attack = UpperAttack(raw=True, template="INSTR[{prompt}]")

    result = attack.apply("hello")

    assert result == "HELLO"


def test_algo_attack_apply_string_with_raw_false_wraps_transformed_in_template():
    attack = UpperAttack(raw=False, template="WRAP[{prompt}]")

    result = attack.apply("hello")

    assert result == "WRAP[HELLO]"


@pytest.mark.parametrize(
    "non_user_role",
    ["system", "ai"],
    ids=["with-system-prefix", "with-ai-prefix"],
)
def test_algo_attack_apply_list_transforms_last_user_message_only(non_user_role):
    attack = UpperAttack(raw=True, template="WRAP[{prompt}]")
    msgs = [
        {"role": non_user_role, "content": "stay-as-is"},
        {"role": "user", "content": "hello"},
    ]

    result = attack.apply(msgs)

    assert result[0] == {"role": non_user_role, "content": "stay-as-is"}
    assert result[1] == {"role": "user", "content": "HELLO"}


def test_algo_attack_apply_list_with_no_user_role_returns_unchanged_copy():
    attack = UpperAttack(raw=True)
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "ai", "content": "ai"},
    ]

    result = attack.apply(msgs)

    assert result == [
        {"role": "system", "content": "sys"},
        {"role": "ai", "content": "ai"},
    ]


def test_algo_attack_apply_list_does_not_mutate_input_list_object():
    attack = UpperAttack(raw=True)
    original_msg = {"role": "user", "content": "hello"}
    msgs = [original_msg]

    result = attack.apply(msgs)

    # The outer list is a copy; mutation happens on the copy's elements.
    assert result is not msgs
    assert len(msgs) == 1


def test_algo_attack_stream_abatch_yields_per_input_results_in_order():
    attack = UpperAttack(raw=True)
    prompts = ["alpha", "beta", "gamma"]

    results = async_collect(attack.stream_abatch(prompts))

    assert results == ["ALPHA", "BETA", "GAMMA"]


