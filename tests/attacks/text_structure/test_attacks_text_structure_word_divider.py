"""Tests for WordDividerAttack.transform() — algorithmic behavior.

Per the class docstring: "inserts characters (dots by default) between letters
in words". The constructor exposes `divider_char`, `density`, and
`apply_to_words_longer_than`. With density=1.0 every eligible word is divided;
with density=0.0 no word is divided.

Determinism: density 1.0 / 0.0 are deterministic by definition (the random
gate `random.random() < density` always passes / always fails). For 1.0 we
seed `random` defensively to keep tests robust.
"""

from __future__ import annotations

import random

import pytest

from hivetracered.attacks.types.single_turn.text_structure_modification.word_divider_attack import (
    WordDividerAttack,
)


@pytest.mark.parametrize(
    ("divider", "text", "expected"),
    [
        ("+", "hello", "h+e+l+l+o"),                       # = '+'.join('hello')
        (".", "ab", "a.b"),                                # = different divider char (catches hardcoded char)
        ("+", "hello world", "h+e+l+l+o w+o+r+l+d"),       # = multi-word: each divided independently
    ],
    ids=["plus-hello", "dot-ab", "multi-word"],
)
def test_transform_divider_inserted_between_every_letter(divider, text, expected):
    random.seed(0)
    attack = WordDividerAttack(
        divider_char=divider, density=1.0, apply_to_words_longer_than=1
    )

    result = attack.transform(text)

    assert result == expected


def test_transform_skips_words_at_or_below_threshold():
    # Source: _divide_word returns word unchanged when len <= apply_to_words_longer_than.
    random.seed(0)
    attack = WordDividerAttack(
        divider_char="+", density=1.0, apply_to_words_longer_than=1
    )

    result = attack.transform("a hi")

    # 'a' has length 1 (not > 1) → unchanged; 'hi' has length 2 (> 1) → divided.
    assert result == "a h+i"


def test_transform_density_zero_returns_input_unchanged():
    # density=0 → random.random() < 0 is always false; no eligible word is divided.
    random.seed(0)
    attack = WordDividerAttack(divider_char="+", density=0.0)

    result = attack.transform("hello world")

    assert result == "hello world"
