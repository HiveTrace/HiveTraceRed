"""Tests for hivetracered.utils.utils.

Spec sources:
- get_unsafe_word docstring (src/hivetracered/utils/utils.py:31-44):
    "Returns the first unsafe word found, or None if no unsafe words detected"
    "Raises Exception: If the model call fails"
"""

from __future__ import annotations

import pytest

from hivetracered.utils.utils import get_unsafe_word
from tests.conftest import MockModel


# Sentinels used by the SUT — pulled out as named constants so tests don't
# silently mirror string literals from the implementation.
NONE_FOUND_SENTINEL = "НИ ОДНОГО"  # = exact uppercase Russian sentinel
NONE_FOUND_LOWERCASE = "ни одного"  # = lowercase substring trigger


# ── get_unsafe_word ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "model_content",
    [NONE_FOUND_SENTINEL, "ни одного чего"],
    ids=["exact-sentinel", "lowercase-substring"],
)
def test_get_unsafe_word_none_found_returns_none(model_content):
    # Both branches of `response == "НИ ОДНОГО" or "ни одного" in response.lower()`
    # must produce None per docstring "None if no unsafe words detected".
    model = MockModel(response={"content": model_content})

    result = get_unsafe_word("any text", model)

    assert result is None


def test_get_unsafe_word_unsafe_response_returns_stripped_word():
    # Whitespace/newline padded — verifies both the return contract and the
    # `.strip()` contract per docstring; subsumes the plain (no-whitespace)
    # case because `.strip()` on a clean word is a no-op.
    model = MockModel(response={"content": "  взломать\n"})

    result = get_unsafe_word("text", model)

    assert result == "взломать"


def test_get_unsafe_word_model_failure_propagates_exception():
    def boom(prompt):
        raise RuntimeError("network down")

    model = MockModel(side_effect=boom)

    with pytest.raises(RuntimeError, match=r"network down"):
        get_unsafe_word("text", model)
