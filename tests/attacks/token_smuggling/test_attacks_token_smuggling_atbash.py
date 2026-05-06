"""Tests for AtbashCipherAttack — per-encoder branches.

Golden letter-mapping rows are in test_attacks_token_smuggling_golden_transforms.py.
This file pins behaviors specific to Atbash that don't fit a single golden row:
non-letter passthrough, and the self-inverse round-trip property.
"""

from __future__ import annotations

from hivetracered.attacks.types.token_smuggling.atbash_attack import AtbashCipherAttack


EN_LOWER = "abcdefghijklmnopqrstuvwxyz"
EN_UPPER = EN_LOWER.upper()
RU_LOWER = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
RU_UPPER = RU_LOWER.upper()


def _atbash_reference(text: str) -> str:
    """Independent reference: each letter at index i → letter at index (len-1-i)."""
    table = {}
    for alphabet in (EN_LOWER, EN_UPPER, RU_LOWER, RU_UPPER):
        n = len(alphabet)
        for i, ch in enumerate(alphabet):
            table[ch] = alphabet[n - 1 - i]
    return "".join(table.get(ch, ch) for ch in text)


def test_transform_non_letters_are_preserved():
    attack = AtbashCipherAttack(raw=True)
    text = "Hi, 5! @#$"

    result = attack.transform(text)

    assert result == _atbash_reference(text)


def test_transform_round_trip_returns_original_for_ascii():
    # Atbash is its own inverse: atbash(atbash(x)) == x for all letters.
    attack = AtbashCipherAttack(raw=True)
    original = "Hello, World!"

    once = attack.transform(original)
    twice = attack.transform(once)

    assert twice == original
