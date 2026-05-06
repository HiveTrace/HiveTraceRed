"""Tests for DisemvowelAttack.transform() — algorithmic behavior.

The class docstring promises vowel removal in English and Russian. The two
public modes are documented via the constructor:
- only_last_vowel=True  → remove only the last vowel of each space-split word
- only_last_vowel=False → remove every vowel from the text

Class-level constants ENGLISH_VOWELS and RUSSIAN_VOWELS are the public vowel set.
"""

from __future__ import annotations

import pytest

from hivetracered.attacks.types.text_structure_modification.disemvowel_attack import (
    DisemvowelAttack,
)


# ── only_last_vowel=False (remove all vowels) ───────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hello", "hll"),         # = remove lowercase e and o
        ("AEIOU", ""),            # = all uppercase vowels removed (catches lowercase-only mutation)
        ("привет", "првт"),       # = Russian vowels и, е removed
    ],
    ids=["hello", "all-vowels", "russian"],
)
def test_transform_remove_all_strips_every_vowel(text, expected):
    attack = DisemvowelAttack(only_last_vowel=False, language="both")

    result = attack.transform(text)

    assert result == expected


# ── only_last_vowel=True (remove last vowel per word) ───────────────


def test_transform_only_last_vowel_drops_last_vowel_per_word():
    text, expected = "hello world", "hell wrld"  # = drop last 'o' of each word
    attack = DisemvowelAttack(only_last_vowel=True, language="both")

    result = attack.transform(text)

    assert result == expected


# ── language gating ─────────────────────────────────────────────────


def test_transform_english_only_does_not_touch_russian_vowels():
    # language='english' restricts the vowel set to ENGLISH_VOWELS.
    attack = DisemvowelAttack(only_last_vowel=False, language="english")

    result = attack.transform("привет")

    assert result == "привет"


def test_transform_russian_only_does_not_touch_english_vowels():
    attack = DisemvowelAttack(only_last_vowel=False, language="russian")

    result = attack.transform("hello")

    assert result == "hello"
