"""Tests for TypoAttack.transform() — algorithmic behavior.

The transform branches per the four typo patterns documented in the class
docstring (swap, omit, double, adjacent-key) chosen via `random`. Tests
seed `random` deterministically and pin one mode at a time so each row
exercises a single documented branch.

Determinism: each test seeds `random` immediately before calling transform
(the SUT calls module-level `random.*` directly).
"""

from __future__ import annotations

import random

import pytest

from hivetracered.attacks.types.text_structure_modification.typo_attack import TypoAttack


# ── per-mode behavior (each row enables exactly one mode) ───────────


@pytest.mark.parametrize(
    ("mode_flags", "len_delta", "anagram_preserved"),
    [
        # swap: pair adjacent → same letters, length, but ≠ original.
        ({"allow_swaps": True}, 0, True),
        # omission: drop one char → length decreases by 1.
        ({"allow_omissions": True}, -1, False),
        # doubling: repeat one char → length increases by 1.
        ({"allow_doubles": True}, +1, False),
        # adjacent: substitute one char with keyboard neighbor → length preserved.
        ({"allow_adjacents": True}, 0, False),
    ],
    ids=["swap", "omission", "doubling", "adjacent"],
)
def test_transform_per_mode_length_invariant(mode_flags, len_delta, anagram_preserved):
    flags = {"allow_swaps": False, "allow_omissions": False, "allow_doubles": False, "allow_adjacents": False}
    flags.update(mode_flags)
    random.seed(0)
    attack = TypoAttack(typo_rate=1.0, **flags)
    text = "hello"

    result = attack.transform(text)

    assert len(result) == len(text) + len_delta
    if anagram_preserved:
        # Swap is an adjacent-pair permutation: same multiset of chars, ≠ original.
        assert sorted(result) == sorted(text)
        assert result != text


# ── determinism with fixed seed ─────────────────────────────────────


def test_transform_is_deterministic_under_fixed_seed():
    # Property: same seed → same output (the unit reads from `random` only).
    text = "the quick brown fox"

    random.seed(123)
    out_a = TypoAttack(typo_rate=1.0).transform(text)

    random.seed(123)
    out_b = TypoAttack(typo_rate=1.0).transform(text)

    assert out_a == out_b


# ── rate gating ─────────────────────────────────────────────────────


def test_transform_rate_zero_returns_input_unchanged():
    # typo_rate=0 → random.random() > 0 always true → no-op (per source guard).
    random.seed(0)
    attack = TypoAttack(typo_rate=0.0)
    text = "hello world today"

    result = attack.transform(text)

    assert result == text


# ── forced typos ────────────────────────────────────────────────────


def test_transform_forced_word_is_modified_even_at_zero_rate():
    # Source contract: words listed in forced_typo_words always get a typo.
    random.seed(0)
    attack = TypoAttack(typo_rate=0.0, forced_typo_words=["secret"])

    result = attack.transform("the secret stays")

    # 'the' and 'stays' are not forced and pass through; 'secret' must change.
    parts = result.split()
    assert parts[0] == "the"
    assert parts[2] == "stays"
    assert parts[1] != "secret"


# ── word-length gating ──────────────────────────────────────────────


def test_transform_single_char_words_unchanged():
    # Source: _apply_typo returns word unchanged for len(word) <= 1.
    random.seed(0)
    attack = TypoAttack(typo_rate=1.0)

    result = attack.transform("a b c")

    assert result == "a b c"
