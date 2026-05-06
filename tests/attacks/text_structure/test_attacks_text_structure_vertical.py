"""Tests for VerticalTextAttack.transform() — algorithmic behavior.

Per the class docstring, the attack stacks each word's characters vertically.
The implementation pads shorter words with spaces and joins per-row words by
single spaces, with rows separated by '\\n'. The contract is therefore:
- output split by '\\n' → number of rows == max(len(word) for word in words)
- row i, when split by ' ', yields one entry per input word: that word's
  i-th character if it exists, else a single space.
"""

from __future__ import annotations

import pytest

from hivetracered.attacks.types.text_structure_modification.vertical_text_attack import (
    VerticalTextAttack,
)


@pytest.mark.parametrize(
    ("text", "expected_lines"),
    [
        # single word: one char per line (no inter-word spacing).
        ("abc", ["a", "b", "c"]),
        # uneven lengths: shorter word ('hi', len 2) padded with spaces for
        # rows 2..4. Exercises padding, row count = max word length,
        # column-wise inter-word join, and top-to-bottom order preservation.
        ("hi there", ["h t", "i h", "  e", "  r", "  e"]),
    ],
    ids=["single-word", "uneven-pads-shorter"],
)
def test_transform_stacks_characters_vertically(text, expected_lines):
    attack = VerticalTextAttack(raw=True)

    result = attack.transform(text)

    assert result.split("\n") == expected_lines
