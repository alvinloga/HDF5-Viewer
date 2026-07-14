"""Validation behavior for safe edit values."""

from __future__ import annotations

import numpy as np
import pytest

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.editing.validation import ValidationPolicy, validate_edit_value


def test_integer_validation_rejects_unsigned_negative_and_overflow() -> None:
    dtype = np.dtype("uint8")

    assert validate_edit_value(3, dtype=dtype) == 3
    assert validate_edit_value("12", dtype=dtype) == 12

    with pytest.raises(DataViewerError) as exc_info:
        validate_edit_value(-1, dtype=dtype)
    assert exc_info.value.code == ErrorCode.EDIT_VALIDATION_FAILED

    with pytest.raises(DataViewerError):
        validate_edit_value("256", dtype=dtype)


def test_float_validation_requires_nonfinite_policy() -> None:
    dtype = np.dtype("float32")

    assert validate_edit_value("1.5", dtype=dtype) == 1.5
    with pytest.raises(DataViewerError):
        validate_edit_value("nan", dtype=dtype)
    with pytest.raises(DataViewerError):
        validate_edit_value("inf", dtype=dtype)

    permissive = ValidationPolicy(allow_nonfinite=True)
    assert np.isnan(validate_edit_value("nan", dtype=dtype, policy=permissive))


def test_complex_validation_rejects_nonfinite_by_default() -> None:
    dtype = np.dtype("complex128")
    assert validate_edit_value("1+2j", dtype=dtype) == 1 + 2j

    with pytest.raises(DataViewerError):
        validate_edit_value("1+infj", dtype=dtype)

    permissive = ValidationPolicy(allow_nonfinite=True)
    assert validate_edit_value("1+infj", dtype=dtype, policy=permissive) == (
        complex(1.0, float("inf"))
    )


def test_boolean_validation_accepts_explicit_and_disallows_invalid() -> None:
    dtype = np.dtype("bool")
    assert validate_edit_value(True, dtype=dtype) is True
    assert validate_edit_value(0, dtype=dtype) is False
    with pytest.raises(DataViewerError):
        validate_edit_value(2, dtype=dtype)


def test_fixed_width_string_rejects_truncation_without_policy() -> None:
    dtype = np.dtype("S4")

    assert validate_edit_value("hi", dtype=dtype) == "hi"
    with pytest.raises(DataViewerError):
        validate_edit_value("abcdef", dtype=dtype)

    permissive = ValidationPolicy(allow_string_truncation=True)
    truncated = validate_edit_value("abcdef", dtype=dtype, policy=permissive)
    assert truncated == "abcd"

    utf8 = np.dtype("U3")
    assert validate_edit_value("aa", dtype=utf8) == "aa"
    with pytest.raises(DataViewerError):
        validate_edit_value("abcdef", dtype=utf8)

    permissive_unicode = ValidationPolicy(
        allow_string_truncation=True,
        strict_text_encoding=False,
    )
    assert (
        validate_edit_value("abcdef", dtype=utf8, policy=permissive_unicode)
        == "abc"
    )


def test_structured_validation_is_field_exact_and_nested() -> None:
    dtype = np.dtype([("a", "i4"), ("b", "f8")])
    source = {"a": "1", "b": "2.0"}

    assert validate_edit_value(source, dtype=dtype) == {"a": 1, "b": 2.0}

    with pytest.raises(DataViewerError):
        validate_edit_value({"a": 1}, dtype=dtype)

    with pytest.raises(DataViewerError):
        validate_edit_value({"a": 1, "b": 2, "c": 3}, dtype=dtype)


def test_unsupported_dtype_raises_validation_error() -> None:
    with pytest.raises(DataViewerError) as exc_info:
        validate_edit_value("x", dtype=np.dtype("O"))
    assert exc_info.value.code == ErrorCode.EDIT_VALIDATION_FAILED
