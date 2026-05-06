"""Tests for hivetracered.pipeline.utils.data_io."""

from __future__ import annotations

import os
import re
from unittest.mock import patch

import numpy as np
import pytest

from hivetracered.pipeline.utils.data_io import (
    get_filename_timestamp,
    is_parquet_serializable,
    load_from_csv,
    load_from_json,
    load_from_parquet,
    load_from_xlsx,
    make_parquet_compatible,
    save_pipeline_results,
    save_to_csv,
    save_to_json,
    save_to_parquet,
    save_to_xlsx,
)


TIMESTAMP_LEN = 15  # = 8 digits + "_" + 6 digits
TIMESTAMP_RE = re.compile(r"\d{8}_\d{6}")


# ── get_filename_timestamp ──────────────────────────────────────────────


def test_get_filename_timestamp_returns_15_char_pattern():
    result = get_filename_timestamp()

    assert len(result) == TIMESTAMP_LEN
    assert TIMESTAMP_RE.fullmatch(result) is not None


# ── is_parquet_serializable ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value",),
    [(1,), ("hello",), (1.5,), (True,)],
    ids=["int", "str", "float", "bool"],
)
def test_is_parquet_serializable_primitives_returns_true(value):
    assert is_parquet_serializable(value) is True


def test_is_parquet_serializable_arbitrary_object_returns_false():
    class Arbitrary:
        pass

    assert is_parquet_serializable(Arbitrary()) is False


# ── make_parquet_compatible ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value",),
    [(1,), ("hello",), (1.5,), (True,), (None,)],
    ids=["int", "str", "float", "bool", "none"],
)
def test_make_parquet_compatible_primitives_pass_through(value):
    result = make_parquet_compatible(value)

    assert result == value
    assert type(result) is type(value)


@pytest.mark.parametrize(
    ("input_val", "expected"),
    [
        ([1, "two", 3.0, None], [1, "two", 3.0, None]),
        (np.array(["a", "b", "c"]), ["a", "b", "c"]),
    ],
    ids=["list", "ndarray"],
)
def test_make_parquet_compatible_list_like_returns_list(input_val, expected):
    result = make_parquet_compatible(input_val)

    assert result == expected
    assert isinstance(result, list)


def test_make_parquet_compatible_tuple_returns_tuple():
    result = make_parquet_compatible((1, "two", 3.0))

    assert result == (1, "two", 3.0)
    assert isinstance(result, tuple)


def test_make_parquet_compatible_set_returns_set():
    input_set = {1, 2, 3}

    result = make_parquet_compatible(input_set)

    assert result == input_set
    assert isinstance(result, set)


def test_make_parquet_compatible_dict_with_empty_inner_replaces_with_none():
    # Documented in _convert_dict_to_parquet_compatible: empty inner dict -> None.
    result = make_parquet_compatible({"a": {}, "b": 1})

    assert result == {"a": None, "b": 1}


def test_make_parquet_compatible_nested_dict_recurses():
    result = make_parquet_compatible({"outer": {"inner": "value"}})

    assert result == {"outer": {"inner": "value"}}


def test_make_parquet_compatible_model_returns_get_params(mock_model):
    # MockModel from conftest: Model subclass; get_params() == {"model_name": "mock"}.
    expected = mock_model.get_params()

    result = make_parquet_compatible(mock_model)

    assert result == expected


def test_make_parquet_compatible_object_with_public_attrs_wraps_in_classname_dict():
    class Holder:
        pass

    h = Holder()
    h.foo = 1
    h.bar = "two"
    h._private = "skipped"

    result = make_parquet_compatible(h)

    assert result == {"Holder": {"foo": 1, "bar": "two"}}


def test_make_parquet_compatible_object_no_public_attrs_returns_str():
    class Empty:
        pass

    e = Empty()

    result = make_parquet_compatible(e)

    assert result == str(e)


def test_make_parquet_compatible_object_skips_unserializable_public_attr():
    # Branch 48->43: a public attribute whose converted form fails
    # is_parquet_serializable is skipped; remaining serializable attribute is kept.
    class Holder:
        pass

    h = Holder()
    h.drop_me = "DROP_ATTR"
    h.keep_me = "kept"

    real = __import__(
        "hivetracered.pipeline.utils.data_io", fromlist=["is_parquet_serializable"]
    )
    real_check = real.is_parquet_serializable

    def fake_is_serializable(v):
        if v == "DROP_ATTR":
            return False
        return real_check(v)

    with patch(
        "hivetracered.pipeline.utils.data_io.is_parquet_serializable",
        side_effect=fake_is_serializable,
    ):
        result = make_parquet_compatible(h)

    assert result == {"Holder": {"keep_me": "kept"}}


def test_make_parquet_compatible_dict_skips_unserializable_inner_value():
    # _convert_dict_to_parquet_compatible: only-add-if-serializable branch (36->29).
    # Patch is_parquet_serializable to return False for a sentinel converted value;
    # the corresponding key must be dropped, while serializable siblings are kept.
    real = __import__("hivetracered.pipeline.utils.data_io", fromlist=["is_parquet_serializable"])
    real_check = real.is_parquet_serializable

    def fake_is_serializable(v):
        if v == "DROP_ME":
            return False
        return real_check(v)

    with patch(
        "hivetracered.pipeline.utils.data_io.is_parquet_serializable",
        side_effect=fake_is_serializable,
    ):
        result = make_parquet_compatible({"drop": "DROP_ME", "keep": 1})

    assert "drop" not in result
    assert result["keep"] == 1


# ── save/load round-trip across all formats ────────────────────────────


@pytest.mark.parametrize(
    ("save_fn", "load_fn"),
    [
        (save_to_csv, load_from_csv),
        (save_to_parquet, load_from_parquet),
        (save_to_json, load_from_json),
        (save_to_xlsx, load_from_xlsx),
    ],
    ids=["csv", "parquet", "json", "xlsx"],
)
def test_save_load_round_trips_list_of_dicts(tmp_path, save_fn, load_fn):
    data = [{"a": 1, "b": "hello"}, {"a": 2, "b": "world"}]

    path = save_fn(data, str(tmp_path), "fixed_20250101_120000")
    loaded = load_fn(path)

    assert loaded == data


@pytest.mark.parametrize(
    ("save_fn", "load_fn"),
    [
        (save_to_csv, load_from_csv),
        (save_to_parquet, load_from_parquet),
        (save_to_json, load_from_json),
        (save_to_xlsx, load_from_xlsx),
    ],
    ids=["csv", "parquet", "json", "xlsx"],
)
def test_save_load_flat_dict_round_trips(tmp_path, save_fn, load_fn):
    # Flat dict (no nested values) routes through the single-row / Series('data')
    # path depending on format. All four formats round-trip the dict identically.
    data = {"a": 1, "b": "hello"}

    path = save_fn(data, str(tmp_path), "flat_20250101_120000")
    loaded = load_fn(path)

    assert loaded == data


@pytest.mark.parametrize(
    ("save_fn", "load_fn"),
    [
        (save_to_csv, load_from_csv),
        (save_to_parquet, load_from_parquet),
        (save_to_xlsx, load_from_xlsx),
    ],
    ids=["csv", "parquet", "xlsx"],
)
def test_save_load_scalar_uses_data_column_fallback(tmp_path, save_fn, load_fn):
    # Non-list-of-dict, non-dict input -> {'data': [value]} fallback.
    # Loader's 'data'-column branch returns the bare scalar back.
    # JSON differs (wraps in {'data': value}) and is tested separately.
    data = "scalar value"

    path = save_fn(data, str(tmp_path), "scalar_20250101_120000")
    loaded = load_fn(path)

    assert loaded == "scalar value"


def test_save_to_json_scalar_wraps_in_data_dict(tmp_path):
    # JSON loader returns {'data': value} for the scalar fallback (asymmetric
    # vs csv/parquet/xlsx which return the bare value).
    data = "scalar"

    path = save_to_json(data, str(tmp_path), "scalar_20250101_120000")
    loaded = load_from_json(path)

    assert loaded == {"data": "scalar"}


# ── Filename / IO error / loader-edge behavior ─────────────────────────


@pytest.mark.parametrize(
    ("save_fn", "ext", "stem"),
    [
        (save_to_csv, ".csv", "noDigitsHere"),
        (save_to_parquet, ".parquet", "noDigits"),
        (save_to_json, ".json", "noDigitsJson"),
        (save_to_xlsx, ".xlsx", "noDigitsXlsx"),
    ],
    ids=["csv", "parquet", "json", "xlsx"],
)
def test_save_appends_timestamp_when_no_digits(tmp_path, save_fn, ext, stem):
    path = save_fn([{"a": 1}], str(tmp_path), stem)

    base = os.path.basename(path)
    assert base.startswith(stem + "_")
    assert base.endswith(ext)
    assert TIMESTAMP_RE.search(base) is not None


@pytest.mark.parametrize(
    ("save_fn", "filename"),
    [
        (save_to_csv, "fixed_20250101.csv"),
        (save_to_parquet, "fixed_2025.parquet"),
        (save_to_json, "fixed_2025.json"),
        (save_to_xlsx, "fixed_2025.xlsx"),
    ],
    ids=["csv", "parquet", "json", "xlsx"],
)
def test_save_strips_format_extension(tmp_path, save_fn, filename):
    path = save_fn([{"a": 1}], str(tmp_path), filename)

    assert os.path.basename(path) == filename


@pytest.mark.parametrize(
    ("save_fn", "mock_target"),
    [
        (save_to_csv, "pandas.DataFrame.to_csv"),
        (save_to_parquet, "pandas.DataFrame.to_parquet"),
        (save_to_json, "pandas.DataFrame.to_json"),
        (save_to_xlsx, "pandas.DataFrame.to_excel"),
    ],
    ids=["csv", "parquet", "json", "xlsx"],
)
def test_save_returns_empty_string_on_io_error(tmp_path, save_fn, mock_target):
    with patch(mock_target, side_effect=OSError("boom")):
        result = save_fn([{"a": 1}], str(tmp_path), "err_20250101_120000")

    assert result == ""


@pytest.mark.parametrize(
    ("save_fn", "load_fn"),
    [
        (save_to_csv, load_from_csv),
        (save_to_parquet, load_from_parquet),
        (save_to_xlsx, load_from_xlsx),
    ],
    ids=["csv", "parquet", "xlsx"],
)
def test_load_single_row_returns_dict(tmp_path, save_fn, load_fn):
    path = save_fn([{"x": 10, "y": 20}], str(tmp_path), "one_20250101_120000")

    loaded = load_fn(path)

    assert loaded == {"x": 10, "y": 20}


@pytest.mark.parametrize(
    ("load_fn", "ext"),
    [
        (load_from_csv, ".csv"),
        (load_from_parquet, ".parquet"),
        (load_from_json, ".json"),
        (load_from_xlsx, ".xlsx"),
    ],
    ids=["csv", "parquet", "json", "xlsx"],
)
def test_load_nonexistent_path_returns_empty_dict(tmp_path, load_fn, ext):
    nonexistent = tmp_path / f"missing{ext}"

    result = load_fn(str(nonexistent))

    assert result == {}


def test_load_from_json_falls_back_to_series_on_value_error(tmp_path):
    # Branch line 289: first read_json raises ValueError -> retried as typ='series'.
    json_path = tmp_path / "series_20250101.json"
    # Write a JSON object that is not a valid records-orient frame: a flat object.
    json_path.write_text('{"a": 1, "b": "hello"}', encoding="utf-8")

    loaded = load_from_json(str(json_path))

    assert loaded == {"a": 1, "b": "hello"}


# ── Nested-dict triggers Series('data') layout (per-format verification) ─
# Each format's nested-dict path is verified differently because the
# verification mechanic genuinely differs (file-text read for csv, mocked
# DataFrame capture for parquet which can't write mixed-type Series, and
# openpyxl read for xlsx). Parametrize would collapse the verification.


def test_save_to_csv_nested_dict_uses_series_layout(tmp_path):
    # Branch lines 108-109: dict with nested dict value triggers Series('data') layout.
    data = {"a": 1, "b": {"nested": "yes"}}

    path = save_to_csv(data, str(tmp_path), "nested_20250101_120000")

    with open(path, "r", encoding="utf-8") as f:
        header = f.readline().strip()
    assert header == "data"  # = single 'data' column means Series-to-frame layout


def test_save_to_parquet_nested_dict_takes_series_branch(tmp_path):
    # Branch line 186: dict with nested dict/list -> Series('data'). Parquet write
    # of mixed-type Series fails; the SUT swallows and returns "". Mock to_parquet
    # to capture the DataFrame structure that the SUT built before the write.
    data = {"a": 1, "b": {"nested": "yes"}}
    captured = {}

    def fake_to_parquet(self, *args, **kwargs):
        captured["columns"] = list(self.columns)

    with patch("pandas.DataFrame.to_parquet", new=fake_to_parquet):
        save_to_parquet(data, str(tmp_path), "nested_20250101_120000")

    assert captured["columns"] == ["data"]


def test_save_to_xlsx_nested_dict_uses_series_layout(tmp_path):
    # Branch line 333: dict with nested dict/list -> Series('data') layout.
    data = {"a": 1, "b": {"nested": "yes"}}

    path = save_to_xlsx(data, str(tmp_path), "nested_20250101_120000")

    import pandas as pd
    df = pd.read_excel(path, engine="openpyxl")
    assert list(df.columns) == ["data"]


# ── save_pipeline_results ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("kwargs", "expected_ext"),
    [
        ({}, ".csv"),  # default format
        ({"format": "parquet"}, ".parquet"),
        ({"format": "xlsx"}, ".xlsx"),
    ],
    ids=["default-csv", "parquet", "xlsx"],
)
def test_save_pipeline_results_writes_chosen_format(tmp_path, kwargs, expected_ext):
    result = save_pipeline_results([{"a": 1}], str(tmp_path), "mystage", **kwargs)

    assert set(result.keys()) == {"path", "timestamp"}
    assert result["path"].endswith(expected_ext)
    assert os.path.exists(result["path"])
    assert TIMESTAMP_RE.fullmatch(result["timestamp"]) is not None


def test_save_pipeline_results_falls_back_to_json_on_save_exception(tmp_path):
    # When the chosen-format save raises, save_pipeline_results catches and
    # routes through save_to_json. Patch at the data_io module seam.
    with patch("hivetracered.pipeline.utils.data_io.save_to_csv", side_effect=RuntimeError("boom")):
        result = save_pipeline_results([{"a": 1}], str(tmp_path), "mystage", format="csv")

    assert result["path"].endswith(".json")
    assert os.path.exists(result["path"])
