"""Tests for UnicodeStyleAttack and UnicodeRussianStyleAttack.transform().

UnicodeStyleAttack maps ASCII A-Z/a-z/0-9 to fancy Unicode ranges defined in
the public class attribute UNICODE_STYLES. The mapping for blackboard_bold is
documented as 𝔸-𝕫 (range 0x1D538-0x1D56B) with 'A' first, lowercase offset by
26 (per the class attribute and docstring).

UnicodeRussianStyleAttack picks a homoglyph from `russian_similar_chars` per
character based on `replacement_strategy` index; tests pin behavior of the
deterministic 'all_same' strategy, citing the public class attribute.
"""

from __future__ import annotations

import pytest

from hivetracered.attacks.types.single_turn.token_smuggling.unicode_attack import (
    UnicodeRussianStyleAttack,
    UnicodeStyleAttack,
)


# ── UnicodeStyleAttack ──────────────────────────────────────────────


BB_RANGE_START = 0x1D538  # = UNICODE_STYLES['blackboard_bold']['uppercase_range'][0]


def test_transform_blackboard_bold_uppercase_A_is_mapped_to_range_start():
    attack = UnicodeStyleAttack(style="blackboard_bold", raw=True)

    result = attack.transform("A")

    # 'A' maps to start of the documented uppercase range (𝔸).
    assert result == chr(BB_RANGE_START)


def test_transform_blackboard_bold_lowercase_a_offset_by_26():
    # Source: lowercase = uppercase_range[0] + offset + 26
    attack = UnicodeStyleAttack(style="blackboard_bold", raw=True)

    result = attack.transform("a")

    assert result == chr(BB_RANGE_START + 26)  # = 𝕒


def test_transform_blackboard_bold_digit_uses_styled_digit_string():
    # Per UNICODE_STYLES, blackboard_bold digits string starts with 𝟙 for '1'.
    attack = UnicodeStyleAttack(style="blackboard_bold", raw=True)
    digits = UnicodeStyleAttack.UNICODE_STYLES["blackboard_bold"]["digits"]

    result = attack.transform("1")

    # digits[1] is the styled glyph for '1' (per UNICODE_STYLES contract).
    assert result == digits[1]


def test_transform_non_alpha_non_digit_passes_through():
    attack = UnicodeStyleAttack(style="blackboard_bold", raw=True)

    result = attack.transform("!?")

    assert result == "!?"


def test_constructor_rejects_unknown_style():
    with pytest.raises(ValueError, match=r"not supported"):
        UnicodeStyleAttack(style="not_a_style")


# ── UnicodeRussianStyleAttack ──────────────────────────────────────


def test_russian_transform_all_same_uses_strategy_index_alternative():
    # 'all_same' is index 1 in replacement_strategies; per the public
    # russian_similar_chars dict, alternatives['а'][1] == 'ɑ'.
    attack = UnicodeRussianStyleAttack(replacement_strategy="all_same", raw=True)
    expected = UnicodeRussianStyleAttack.russian_similar_chars["а"][1]

    result = attack.transform("а")

    assert result == expected


def test_russian_transform_preserves_uppercase_when_replacement_uppercases():
    # Source: if char.isupper() and replacement.upper() != replacement,
    # output replacement.upper(). 'А' (Cyrillic) is upper; alternatives[1] for
    # lower 'а' is 'ɑ' which has a distinct upper form.
    attack = UnicodeRussianStyleAttack(replacement_strategy="all_same", raw=True)
    lower_replacement = UnicodeRussianStyleAttack.russian_similar_chars["а"][1]

    result = attack.transform("А")

    assert result == lower_replacement.upper()


def test_russian_transform_non_cyrillic_passes_through():
    attack = UnicodeRussianStyleAttack(replacement_strategy="all_same", raw=True)

    result = attack.transform("hello!")

    # ASCII letters/punct aren't in russian_similar_chars; preserved verbatim.
    assert result == "hello!"


def test_russian_constructor_rejects_unknown_strategy():
    with pytest.raises(ValueError, match=r"not supported"):
        UnicodeRussianStyleAttack(replacement_strategy="not_a_strategy")


