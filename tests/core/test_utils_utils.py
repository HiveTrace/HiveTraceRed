"""Tests for hivetracered.utils.utils.

Spec sources:
- get_unsafe_word docstring (src/hivetracered/utils/utils.py:57-70):
    "Returns the first unsafe word found, or None if no unsafe words detected"
    "Raises Exception: If the model call fails"
- get_all_unsafe_words docstring (src/hivetracered/utils/utils.py:93-106):
    "List of all unsafe words found, or empty list if none detected"
    Implementation contract on response handling: response.content path for
    LangChain-style responses, str(response) fallback otherwise; "НИ ОДНОГО"
    sentinel signals empty result; multiline output split on \n with stripping.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hivetracered.utils.utils import get_all_unsafe_words, get_unsafe_word
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


# ── get_all_unsafe_words ─────────────────────────────────────────────


def test_get_all_unsafe_words_dict_response_falls_back_to_str():
    # MockModel returns a dict; SUT falls through to `str(response).strip()`.
    # Choose a single-token output to keep the str() representation small.
    model = MockModel(response={"content": "обмануть"})

    result = get_all_unsafe_words("text", model)

    # str({"content": "обмануть"}) == "{'content': 'обмануть'}" — one line, kept.
    assert result == [str({"content": "обмануть"})]


@pytest.mark.parametrize(
    "content",
    [NONE_FOUND_SENTINEL, "ни одного слова"],
    ids=["exact-sentinel", "lowercase-substring"],
)
def test_get_all_unsafe_words_none_found_returns_empty_list(content):
    # Both branches of `result == "НИ ОДНОГО" or "ни одного" in result.lower()`
    # must produce [] per docstring "empty list if none detected".
    response = MagicMock()
    response.content = content
    model = MagicMock()
    model.invoke.return_value = response

    result = get_all_unsafe_words("clean text", model)

    assert result == []


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        # blanks + whitespace — verifies strip + falsy-filter and split('\n') ordering
        ("  бомбу  \n\n   \nвзломать\n", ["бомбу", "взломать"]),
    ],
    ids=["filter-blanks-and-strip"],
)
def test_get_all_unsafe_words_split_strip_filter(content, expected):
    response = MagicMock()
    response.content = content
    model = MagicMock()
    model.invoke.return_value = response

    result = get_all_unsafe_words("text", model)

    assert result == expected


def test_get_all_unsafe_words_model_failure_propagates_exception():
    model = MagicMock()
    model.invoke.side_effect = ValueError("bad request")

    with pytest.raises(ValueError, match=r"bad request"):
        get_all_unsafe_words("text", model)
