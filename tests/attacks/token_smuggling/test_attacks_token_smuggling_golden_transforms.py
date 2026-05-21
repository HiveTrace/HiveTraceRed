"""Golden-input contract tests across token-smuggling encoders.

Each row pins `attack.transform(input) == expected` where `expected` is either
a literal known-output (e.g. classical-cipher mapping) or computed from an
independent oracle (stdlib codec / RFC reference). One row per (encoder, input)
case; per-encoder branch behaviors (round-trip, passthrough, error paths, etc.)
remain in their own files.
"""

from __future__ import annotations

import base64
import codecs

import pytest

from hivetracered.attacks.types.single_turn.token_smuggling.atbash_attack import AtbashCipherAttack
from hivetracered.attacks.types.single_turn.token_smuggling.base64_attack import Base64InputOnlyAttack
from hivetracered.attacks.types.single_turn.token_smuggling.binary_encoding_attack import BinaryEncodingAttack
from hivetracered.attacks.types.single_turn.token_smuggling.hex_encoding_attack import HexEncodingAttack
from hivetracered.attacks.types.single_turn.token_smuggling.html_entity_attack import HtmlEntityAttack
from hivetracered.attacks.types.single_turn.token_smuggling.leetspeak_attack import LeetspeakAttack
from hivetracered.attacks.types.single_turn.token_smuggling.morse_code_attack import MorseCodeAttack
from hivetracered.attacks.types.single_turn.token_smuggling.rot_attack import RotCipherAttack


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")


def _hex_ref(text: str) -> str:
    return " ".join(f"{ord(c):x}" for c in text)


def _bin_ref(text: str, bits: int = 16) -> str:
    return " ".join(bin(ord(c))[2:].zfill(bits) for c in text)


@pytest.mark.parametrize(
    ("attack_cls", "kwargs", "sample_input", "expected"),
    [
        # ── AtbashCipherAttack: classical cipher mirror mapping ──────────
        (AtbashCipherAttack, {"raw": True}, "abc", "zyx"),
        (AtbashCipherAttack, {"raw": True}, "ABC", "ZYX"),
        (AtbashCipherAttack, {"raw": True}, "абв", "яюэ"),
        # ── Base64InputOnlyAttack: stdlib base64 oracle (RFC 4648) ───────
        (Base64InputOnlyAttack, {"raw": True}, "hello", _b64("hello")),
        (Base64InputOnlyAttack, {"raw": True}, "Привет", _b64("Привет")),
        # ── BinaryEncodingAttack: 16-bit per-char binary oracle ──────────
        (BinaryEncodingAttack, {"raw": True}, "A", _bin_ref("A")),
        (BinaryEncodingAttack, {"raw": True}, "hi", _bin_ref("hi")),
        (BinaryEncodingAttack, {"raw": True}, "А", _bin_ref("А")),
        # ── HexEncodingAttack: per-char `{ord:x}` oracle ─────────────────
        (HexEncodingAttack, {"raw": True}, "A", _hex_ref("A")),
        (HexEncodingAttack, {"raw": True}, "Привет", _hex_ref("Привет")),
        # ── HtmlEntityAttack: numeric entity reference (W3C HTML5) ───────
        (HtmlEntityAttack, {"raw": True}, "<", "&#60;"),
        # ── LeetspeakAttack: LEET_DICT golden (l→1, e→3, t→7) ────────────
        (LeetspeakAttack, {}, "leet", "1337"),
        # ── MorseCodeAttack: ITU-R M.1677-1 ──────────────────────────────
        (MorseCodeAttack, {"raw": True}, "E", "."),
        (MorseCodeAttack, {"raw": True}, "T", "-"),
        (MorseCodeAttack, {"raw": True}, "A", ".-"),
        (MorseCodeAttack, {"raw": True}, "N", "-."),
        (MorseCodeAttack, {"raw": True}, "SOS", "... --- ..."),
        # ── RotCipherAttack: stdlib rot_13 codec oracle ──────────────────
        (RotCipherAttack, {}, "abc", codecs.encode("abc", "rot_13")),
        (RotCipherAttack, {}, "ABC", codecs.encode("ABC", "rot_13")),
        (RotCipherAttack, {}, "Hello, World!", codecs.encode("Hello, World!", "rot_13")),
    ],
    ids=[
        "atbash-abc", "atbash-ABC", "atbash-абв",
        "base64-hello", "base64-cyrillic",
        "binary-A", "binary-hi", "binary-cyrillic",
        "hex-A", "hex-cyrillic",
        "html-lt",
        "leet-leet",
        "morse-E", "morse-T", "morse-A", "morse-N", "morse-SOS",
        "rot13-abc", "rot13-ABC", "rot13-punct",
    ],
)
def test_transform_matches_oracle(attack_cls, kwargs, sample_input, expected):
    attack = attack_cls(**kwargs)

    result = attack.transform(sample_input)

    assert result == expected
