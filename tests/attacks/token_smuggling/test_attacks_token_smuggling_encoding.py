"""Tests for EncodingAttack.transform() — algorithmic behavior.

Per docstring, "transforms text from one encoding to another (UTF-8 to KOI8-R
by default)". Independent oracle: encode in source, decode-as-target with
errors='replace' (matches the documented contract via stdlib codec semantics).
"""

from __future__ import annotations


from hivetracered.attacks.types.single_turn.token_smuggling.encoding_attack import EncodingAttack


def _encode_reference(text: str, source: str, target: str) -> str:
    return text.encode(source).decode(target, errors="replace")


def test_transform_default_utf8_to_koi8r_matches_reference():
    attack = EncodingAttack()  # = utf-8 → koi8-r (defaults)

    result = attack.transform("привет")

    assert result == _encode_reference("привет", "utf-8", "koi8-r")


def test_transform_uses_replace_for_undecodable_bytes():
    # UTF-8 multibyte for 'я' (0xd1 0x8f) is not valid in ascii decode; the
    # contract uses errors='replace' so output must equal the reference.
    attack = EncodingAttack(source_encoding="utf-8", target_encoding="ascii")

    result = attack.transform("я")

    assert result == _encode_reference("я", "utf-8", "ascii")


