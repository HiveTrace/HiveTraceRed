"""Tests for RotCipherAttack — per-encoder branches.

Default ROT-13 golden rows live in test_attacks_token_smuggling_golden_transforms.py.
This file pins the configurable-rotation behavior (which the parametrized golden
file can't express in its (cls, kwargs, input, expected) shape) and the
documented Russian 'ё' preservation special-case.
"""

from __future__ import annotations

import pytest

from hivetracered.attacks.types.token_smuggling.rot_attack import RotCipherAttack


@pytest.mark.parametrize(
    ("text", "rotation", "expected"),
    [
        ("a", 1, "b"),     # = a shifted by 1
        ("z", 1, "a"),     # = wrap-around: z+1 → a
        ("a", 25, "z"),    # = a+25 → z
        ("a", 26, "a"),    # = full rotation returns original
    ],
    ids=["a-rot1", "z-rot1-wraps", "a-rot25", "a-rot26-identity"],
)
def test_transform_configurable_rotation_shifts_correctly(text, rotation, expected):
    attack = RotCipherAttack(rotation=rotation)

    result = attack.transform(text)

    assert result == expected


def test_transform_russian_yo_kept_unchanged():
    # Source documents 'ё'/'Ё' as a special case kept as-is.
    attack = RotCipherAttack(rotation=1)

    result = attack.transform("ё")

    assert result == "ё"
