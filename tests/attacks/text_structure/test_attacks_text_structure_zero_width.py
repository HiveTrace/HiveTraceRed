"""Tests for ZeroWidthAttack.transform() — algorithmic behavior.

Per the class docstring, the attack inserts zero-width Unicode characters
between visible characters with a configurable density. `ZERO_WIDTH_CHARS`
is exposed as a public class attribute (the contract). The contract is:
- density=0 → no insertions (output equals input)
- density=1 → at least one ZW char inserted after every visible char
- stripping ZW chars from output recovers the original text (visible-length preserved)
- density outside [0,1] → ValueError
"""

from __future__ import annotations

import random

import pytest

from hivetracered.attacks.types.text_structure_modification.zero_width_attack import (
    ZeroWidthAttack,
)


ZW_SET = set(ZeroWidthAttack.ZERO_WIDTH_CHARS)


def _strip_zw(s: str) -> str:
    return "".join(c for c in s if c not in ZW_SET)


def test_transform_density_zero_returns_input_unchanged():
    # density=0 → random.random() < 0 always false → no insertion at all.
    random.seed(0)
    attack = ZeroWidthAttack(density=0.0)
    text = "hello world"

    result = attack.transform(text)

    assert result == text


def test_transform_density_one_inserts_only_zw_chars_and_strip_recovers_original():
    # density=1 → guard always passes; every visible char is followed by 1..3
    # zero-width chars from ZERO_WIDTH_CHARS. Single test asserts:
    #   - insertion happened (output strictly longer than input)
    #   - every non-input char belongs to the public ZW set
    #   - stripping ZW chars recovers the exact original text.
    random.seed(0)
    attack = ZeroWidthAttack(density=1.0)
    text = "Hello, World!"
    text_chars = set(text)

    result = attack.transform(text)

    assert len(result) > len(text)                                   # = B2 insertion happened
    inserted = [c for c in result if c not in text_chars]
    assert inserted and all(c in ZW_SET for c in inserted)           # = B4 only ZW class chars
    assert _strip_zw(result) == text                                 # = B3 stripping recovers


@pytest.mark.parametrize("bad_density", [1.5, -0.1], ids=["above-one", "negative"])
def test_constructor_rejects_density_outside_unit_interval(bad_density):
    with pytest.raises(ValueError, match=r"between 0 and 1"):
        ZeroWidthAttack(density=bad_density)
