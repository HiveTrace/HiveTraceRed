"""Tests for TransliterationAttack.transform() — algorithmic behavior.

Per docstring, the attack delegates to `cyrtranslit.to_latin` /
`cyrtranslit.to_cyrillic` with the appropriate language code. Independent
oracle: call cyrtranslit directly with the same args.
"""

from __future__ import annotations

import cyrtranslit
import pytest

from hivetracered.attacks.types.token_smuggling.transliteration_attack import (
    TransliterationAttack,
)


def test_transform_russian_to_english_matches_cyrtranslit_to_latin():
    attack = TransliterationAttack(source_language="russian", target_language="english")

    result = attack.transform("привет")

    assert result == cyrtranslit.to_latin("привет", "ru")


def test_transform_english_to_russian_matches_cyrtranslit_to_cyrillic():
    attack = TransliterationAttack(source_language="english", target_language="russian")

    result = attack.transform("hello")

    assert result == cyrtranslit.to_cyrillic("hello", "ru")

def test_constructor_rejects_unsupported_source_language():
    with pytest.raises(ValueError, match=r"Source language must be one of"):
        TransliterationAttack(source_language="klingon", target_language="english")


def test_constructor_rejects_same_source_and_target():
    with pytest.raises(ValueError, match=r"must be different"):
        TransliterationAttack(source_language="russian", target_language="russian")


def test_constructor_rejects_pair_without_english():
    with pytest.raises(ValueError, match=r"must be English"):
        TransliterationAttack(source_language="russian", target_language="ukrainian")


