"""Tests for JSONTransformAttack.transform() — algorithmic behavior.

Per the class docstring: 'How to get a cake?' becomes
{"How": "to", "get": "a", "cake?": ""}. Each parametrize case asserts the
parsed dict, which catches both the pairing rule and the JSON-validity
property in one assertion.
"""

from __future__ import annotations

import json

import pytest

from hivetracered.attacks.types.text_structure_modification.json_transform_attack import (
    JSONTransformAttack,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a b", {"a": "b"}),                                        # = single key/value pair
        ("a b c", {"a": "b", "c": ""}),                             # = trailing odd word → empty value
        ("", {}),                                                    # = empty input branches the json-string trim
    ],
    ids=["single-pair", "odd-trailing", "empty"],
)
def test_transform_pairs_words_as_keys_and_values(text, expected):
    attack = JSONTransformAttack()

    result = attack.transform(text)
    parsed = json.loads(result)

    assert parsed == expected
