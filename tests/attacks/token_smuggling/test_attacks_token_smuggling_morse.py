"""Tests for MorseCodeAttack — per-encoder branches.

Golden letter and SOS rows live in test_attacks_token_smuggling_golden_transforms.py.
This file pins the case-folding contract (input uppercased before lookup) and
the unsupported-char passthrough.
"""

from __future__ import annotations

from hivetracered.attacks.types.token_smuggling.morse_code_attack import MorseCodeAttack


def test_transform_lowercase_input_uppercased_then_encoded():
    attack = MorseCodeAttack(raw=True)

    lower = attack.transform("abc")
    upper = attack.transform("ABC")

    assert lower == upper


def test_transform_unknown_chars_passed_through_unchanged():
    # '!' and '@' are not in MORSE_CODE_DICT; class promises only English/Russian
    # alphabet support, so unsupported chars must pass through (joined by space).
    attack = MorseCodeAttack(raw=True)

    result = attack.transform("!@")

    assert result == "! @"
