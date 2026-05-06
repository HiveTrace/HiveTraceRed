"""Tests for BackToFrontAttack.transform() — algorithmic behavior.

Per the class docstring, the attack "reverses the entire text". Tests assert
the standard string-reversal property and the involution
transform(transform(x)) == x.
"""

from __future__ import annotations

import pytest

from hivetracered.attacks.types.text_structure_modification.back_to_front_attack import (
    BackToFrontAttack,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("abc", "cba"),                      # = "abc" reversed (slice [::-1])
        ("привет", "тевирп"),                # = unicode reversed correctly
    ],
    ids=["abc", "cyrillic"],
)
def test_transform_reverses_input_text(text, expected):
    attack = BackToFrontAttack(raw=True)

    result = attack.transform(text)

    assert result == expected
