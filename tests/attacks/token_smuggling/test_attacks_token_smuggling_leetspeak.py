"""Tests for LeetspeakAttack — per-encoder branches.

The golden "leet"→"1337" row lives in test_attacks_token_smuggling_golden_transforms.py.
This file pins the unmapped-character passthrough branch.
"""

from __future__ import annotations

from hivetracered.attacks.types.token_smuggling.leetspeak_attack import LeetspeakAttack


def test_transform_unmapped_chars_pass_through():
    attack = LeetspeakAttack()
    # 'x', 'y' aren't in LEET_DICT; punctuation also unmapped.
    text = "xy?!"

    result = attack.transform(text)

    assert result == "xy?!"
