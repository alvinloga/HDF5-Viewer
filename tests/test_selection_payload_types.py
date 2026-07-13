"""Contracts for normalized selections and payload coordinate provenance."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from data_viewer.domain import (
    ArrayPayload,
    AxisSelection,
    ColumnSpec,
    OperationScope,
    ReadResult,
    SampleSpec,
    SelectionErrorCode,
    SelectionSpec,
    TablePageSelection,
    TablePayload,
    TextPayload,
)


def test_scalar_selection_uses_empty_key_and_scalar_shape() -> None:
    normalized = SelectionSpec.all().normalize(()).unwrap()

    assert normalized.original_shape == ()
    assert normalized.result_shape == ()
    assert normalized.to_numpy_key() == ()
    assert normalized.source_coordinates(()) == ()


def test_negative_index_selection_normalizes_against_shape() -> None:
    normalized = SelectionSpec.index(axis=0, index=-1).normalize((5,)).unwrap()

    assert normalized.result_shape == ()
    assert normalized.to_numpy_key() == (4,)
    assert normalized.source_coordinates(()) == (4,)


def test_hyperslab_selection_preserves_source_coordinates() -> None:
    normalized = SelectionSpec.hyperslab(
        AxisSelection.slice(axis=0, start=-3),
        AxisSelection.slice(axis=1, start=1, stop=5, step=2),
    ).normalize((6, 8)).unwrap()

    assert normalized.result_shape == (3, 2)
    assert normalized.to_numpy_key() == (slice(3, 6, 1), slice(1, 5, 2))
    assert normalized.source_coordinates((2, 1)) == (5, 3)


def test_omitted_axes_expand_to_full_slices_without_flattening() -> None:
    normalized = SelectionSpec.slice(axis=1, start=1, step=2).normalize(
        (2, 5, 4)
    ).unwrap()

    assert normalized.result_shape == (2, 2, 4)
    assert normalized.to_numpy_key() == (
        slice(0, 2, 1),
        slice(1, 5, 2),
        slice(0, 4, 1),
    )
    assert normalized.source_coordinates((1, 1, 3)) == (1, 3, 3)


def test_invalid_shape_selection_returns_structured_errors() -> None:
    result = SelectionSpec.hyperslab(
        AxisSelection(axis=1, index=0),
        AxisSelection(axis=1, index=1),
        AxisSelection(axis=3, index=0),
    ).normalize((2, 2))

    assert not result.ok
    assert [error.code for error in result.errors] == [
        SelectionErrorCode.DUPLICATE_AXIS,
        SelectionErrorCode.AXIS_OUT_OF_BOUNDS,
    ]
    assert result.errors[0].axis == 1
    assert result.errors[0].to_json()["code"] == "duplicate_axis"


def test_structurally_invalid_axis_selection_raises_value_error() -> None:
    with pytest.raises(ValueError, match="step cannot be zero"):
        AxisSelection.slice(axis=0, step=0)

    with pytest.raises(ValueError, match="exactly one"):
        AxisSelection(axis=0, index=1, start=0)


@given(
    shape=st.lists(st.integers(min_value=1, max_value=20), min_size=1, max_size=4),
    data=st.data(),
)
def test_index_selection_property_maps_display_to_source_coordinates(
    shape: list[int],
    data: st.DataObject,
) -> None:
    axis = data.draw(st.integers(min_value=0, max_value=len(shape) - 1))
    dimension = shape[axis]
    raw_index = data.draw(st.integers(min_value=-dimension, max_value=dimension - 1))

    normalized = SelectionSpec.index(axis, raw_index).normalize(tuple(shape)).unwrap()
    display_index = tuple(0 for _dimension in normalized.result_shape)
    source_coordinate = normalized.source_coordinates(display_index)

    assert source_coordinate[axis] == raw_index % dimension
    assert len(source_coordinate) == len(shape)
    assert len(normalized.result_shape) == len(shape) - 1


def test_table_page_normalizes_negative_offsets_and_clips_known_totals() -> None:
    normalized = TablePageSelection(
        row_offset=-5,
        row_limit=10,
        selected_columns=("signal",),
    ).normalize(total_rows=12).unwrap()

    assert normalized.row_offset == 7
    assert normalized.row_limit == 5
    assert normalized.row_stop == 12
    assert normalized.source_row(4) == 11
    assert normalized.selected_columns == ("signal",)


def test_table_page_returns_structured_errors_without_known_total() -> None:
    result = TablePageSelection(row_offset=-1, row_limit=10).normalize(
        total_rows=None
    )

    assert not result.ok
    assert result.errors[0].code == SelectionErrorCode.NEGATIVE_OFFSET_WITHOUT_TOTAL


def test_array_payload_validates_shape_and_maps_display_coordinates() -> None:
    selection = SelectionSpec.hyperslab(
        AxisSelection.slice(axis=0, start=1),
        AxisSelection.slice(axis=1, start=0, stop=4, step=2),
    ).normalize((3, 4)).unwrap()
    payload = ArrayPayload(
        values=np.asarray([[4, 6], [8, 10]]),
        original_shape=(3, 4),
        selection=selection,
    )

    assert payload.values.shape == (2, 2)
    assert payload.source_coordinates((1, 1)) == (2, 2)

    with pytest.raises(ValueError, match="payload values shape"):
        ArrayPayload(
            values=np.asarray([1, 2, 3]),
            original_shape=(3, 4),
            selection=selection,
        )


def test_table_payload_keeps_row_headers_out_of_data_columns() -> None:
    columns = (
        ColumnSpec("a", "int64", nullable=False),
        ColumnSpec("b", "int64", nullable=False),
    )
    payload = TablePayload(
        columns=columns,
        column_values=(np.asarray([1, 2]), np.asarray([3, 4])),
        row_offset=5,
        total_rows=10,
    )

    assert payload.row_count == 2
    assert payload.source_row(1) == 6
    assert payload.source_cell(1, "b") == (6, "b")

    with pytest.raises(ValueError, match="same row count"):
        TablePayload(
            columns=columns,
            column_values=(np.asarray([1, 2]), np.asarray([3])),
            row_offset=0,
            total_rows=2,
        )


def test_text_payload_and_read_result_preserve_scope_and_sample() -> None:
    payload = TextPayload(text="abcdef", offset=10, is_complete=False)
    sample = SampleSpec(method="head", max_items=6, seed=123)
    result = ReadResult(
        payload=payload,
        scope=OperationScope.SAMPLE,
        bytes_read=6,
        is_sampled=True,
        sample=sample,
        warnings=("truncated",),
    )

    assert payload.source_offset(3) == 13
    assert result.scope == OperationScope.SAMPLE
    assert result.sample == sample
    assert result.warnings == ("truncated",)
