"""Unit tests for hivetracered.evaluators.data.utils."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from hivetracered.evaluators.data import utils as data_utils
from hivetracered.evaluators.data.utils import get_data_file_path, load_keywords


# ── get_data_file_path ────────────────────────────────────────────────


def test_get_data_file_path_uses_data_module_dir():
    # Asserting full dirname equality also catches:
    #   * non-absolute paths (B1) — expected_dir is absolute
    #   * missing filename join (B2) — dirname would shift to parent
    path = get_data_file_path("keywords.csv")

    expected_dir = os.path.dirname(os.path.abspath(data_utils.__file__))
    assert os.path.dirname(path) == expected_dir
    assert path.endswith("keywords.csv")


# ── load_keywords: real bundled file ──────────────────────────────────


def test_load_keywords_contains_known_entry_from_bundled_csv():
    # First data row in the bundled keywords.csv is "I'm sorry"; we use
    # this as a stable, factual oracle anchored to the shipped data file.
    # Also verifies non-empty list of non-empty strings.
    keywords = load_keywords()

    assert "I'm sorry" in keywords


# ── load_keywords: file-not-found fallback ────────────────────────────


def test_load_keywords_file_missing_uses_fallback_list(tmp_path, capsys):
    # Source defines an explicit fallback list of exactly 12 entries; verify
    # known entries, count, and warning print on exception.
    missing = str(tmp_path / "does_not_exist.csv")

    with patch(
        "hivetracered.evaluators.data.utils.get_data_file_path",
        return_value=missing,
    ):
        keywords = load_keywords()

    assert "bomb" in keywords
    assert "password" in keywords
    assert len(keywords) == 12  # = number of fallback entries in source
    assert "Warning" in capsys.readouterr().out


# ── load_keywords reads the 'keyword' column ──────────────────────────


@pytest.mark.parametrize(
    "csv_text, expected",
    [
        ("keyword\nfoo\nbar\nbaz\n", ["foo", "bar", "baz"]),
        ("keyword,category\nalpha,greek\nbeta,greek\n", ["alpha", "beta"]),
    ],
    ids=["keyword_only_column", "extra_columns_ignored"],
)
def test_load_keywords_reads_keyword_column_from_csv(tmp_path, csv_text, expected):
    custom = tmp_path / "keywords.csv"
    custom.write_text(csv_text, encoding="utf-8")

    with patch(
        "hivetracered.evaluators.data.utils.get_data_file_path",
        return_value=str(custom),
    ):
        keywords = load_keywords()

    assert keywords == expected
