"""Payload values returned by bounded Data Viewer reads."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from .metadata import ColumnSpec, FrozenJsonMapping, JsonValue, SpatialMetadata
from .selection import NormalizedSelection, SelectionSpec


class OperationScope(StrEnum):
    """Declared scope used to produce a read result."""

    FULL = "full"
    SLICE = "slice"
    PAGE = "page"
    SAMPLE = "sample"


@dataclass(frozen=True, slots=True)
class SampleSpec:
    """Sampling parameters used for a bounded result."""

    method: str
    max_items: int
    seed: int

    def __post_init__(self) -> None:
        if not self.method:
            raise ValueError("sample method must not be empty")
        if isinstance(self.max_items, bool) or self.max_items <= 0:
            raise ValueError("sample max items must be positive")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("sample seed must be an integer")

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "method": self.method,
            "max_items": self.max_items,
            "seed": self.seed,
        }


@dataclass(frozen=True, slots=True)
class ArrayPayload:
    """Array values with explicit original-shape and selection provenance."""

    values: NDArray[np.generic]
    original_shape: tuple[int, ...]
    selection: SelectionSpec | NormalizedSelection

    def __post_init__(self) -> None:
        original_shape = _validate_shape(self.original_shape, "original shape")
        normalized = _ensure_normalized_selection(self.selection, original_shape)
        value_shape = _array_shape(self.values, "payload values")
        if value_shape != normalized.result_shape:
            raise ValueError(
                "payload values shape must match normalized selection result shape"
            )
        object.__setattr__(self, "original_shape", original_shape)
        object.__setattr__(self, "selection", normalized)

    def source_coordinates(self, display_index: tuple[int, ...]) -> tuple[int, ...]:
        if not isinstance(self.selection, NormalizedSelection):
            raise ValueError("array payload selection is not normalized")
        return self.selection.source_coordinates(display_index)


@dataclass(frozen=True, slots=True)
class TablePayload:
    """Columnar table payload without injecting row numbers into data columns."""

    columns: tuple[ColumnSpec, ...]
    column_values: tuple[NDArray[np.generic], ...]
    row_offset: int
    total_rows: int | None

    def __post_init__(self) -> None:
        if isinstance(self.row_offset, bool) or self.row_offset < 0:
            raise ValueError("table row offset must be non-negative")
        if self.total_rows is not None and (
            isinstance(self.total_rows, bool) or self.total_rows < 0
        ):
            raise ValueError("table total rows must be non-negative or null")
        columns = tuple(self.columns)
        values = tuple(self.column_values)
        if len(columns) != len(values):
            raise ValueError("table payload needs one value array per column")
        row_counts = tuple(_column_row_count(value) for value in values)
        if len(set(row_counts)) > 1:
            raise ValueError("table payload columns must have the same row count")
        if self.total_rows is not None and self.row_offset + (row_counts[0] if row_counts else 0) > self.total_rows:
            raise ValueError("table payload rows exceed total row count")
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "column_values", values)

    @property
    def row_count(self) -> int:
        if not self.column_values:
            return 0
        return _column_row_count(self.column_values[0])

    def source_row(self, display_row: int) -> int:
        if isinstance(display_row, bool) or not isinstance(display_row, int):
            raise ValueError("display row must be an integer")
        if display_row < 0 or display_row >= self.row_count:
            raise ValueError("display row is out of bounds")
        return self.row_offset + display_row

    def source_cell(self, display_row: int, column: int | str) -> tuple[int, str]:
        source_row = self.source_row(display_row)
        if isinstance(column, int) and not isinstance(column, bool):
            try:
                column_name = self.columns[column].name
            except IndexError as exc:
                raise ValueError("column index is out of bounds") from exc
        else:
            column_name = str(column)
            if column_name not in {spec.name for spec in self.columns}:
                raise ValueError("column name is not present in the payload")
        return source_row, column_name


@dataclass(frozen=True, slots=True)
class TextPayload:
    """Text payload with byte/character offset provenance."""

    text: str
    offset: int
    is_complete: bool

    def __post_init__(self) -> None:
        if isinstance(self.offset, bool) or self.offset < 0:
            raise ValueError("text payload offset must be non-negative")
        if not isinstance(self.is_complete, bool):
            raise ValueError("text payload completion flag must be boolean")

    def source_offset(self, local_offset: int) -> int:
        if isinstance(local_offset, bool) or not isinstance(local_offset, int):
            raise ValueError("local text offset must be an integer")
        if local_offset < 0 or local_offset > len(self.text):
            raise ValueError("local text offset is out of bounds")
        return self.offset + local_offset


@dataclass(frozen=True, slots=True)
class StructuredPayload:
    """JSON-compatible structured payload."""

    value: JsonValue

    def __post_init__(self) -> None:
        FrozenJsonMapping({"value": self.value})


@dataclass(frozen=True, slots=True)
class VolumePayload:
    """Volume values with normalized selection and spatial metadata."""

    values: NDArray[np.generic]
    selection: SelectionSpec | NormalizedSelection
    spatial: SpatialMetadata

    def __post_init__(self) -> None:
        normalized = self.selection
        if not isinstance(normalized, NormalizedSelection):
            raise ValueError("volume payload requires a normalized selection")
        value_shape = _array_shape(self.values, "volume payload values")
        if value_shape != normalized.result_shape:
            raise ValueError(
                "volume payload values shape must match normalized selection result shape"
            )
        object.__setattr__(self, "selection", normalized)

    def source_coordinates(self, display_index: tuple[int, ...]) -> tuple[int, ...]:
        if not isinstance(self.selection, NormalizedSelection):
            raise ValueError("volume payload selection is not normalized")
        return self.selection.source_coordinates(display_index)


DataPayload: TypeAlias = (
    ArrayPayload | TablePayload | TextPayload | StructuredPayload | VolumePayload
)


@dataclass(frozen=True, slots=True)
class ReadResult:
    """Bounded read result with declared scope and sampling state."""

    payload: DataPayload
    scope: OperationScope
    bytes_read: int
    is_sampled: bool
    sample: SampleSpec | None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope", OperationScope(self.scope))
        if isinstance(self.bytes_read, bool) or self.bytes_read < 0:
            raise ValueError("read result bytes_read must be non-negative")
        if not isinstance(self.is_sampled, bool):
            raise ValueError("read result is_sampled must be boolean")
        if self.is_sampled and self.sample is None:
            raise ValueError("sampled read result requires sample parameters")
        object.__setattr__(self, "warnings", tuple(self.warnings))


def _ensure_normalized_selection(
    selection: SelectionSpec | NormalizedSelection,
    original_shape: tuple[int, ...],
) -> NormalizedSelection:
    if isinstance(selection, NormalizedSelection):
        if selection.original_shape != original_shape:
            raise ValueError("normalized selection original shape mismatch")
        return selection
    result = selection.normalize(original_shape)
    if not result.ok:
        joined = "; ".join(error.message for error in result.errors)
        raise ValueError(f"payload selection is invalid: {joined}")
    return result.unwrap()


def _validate_shape(shape: tuple[int, ...], label: str) -> tuple[int, ...]:
    normalized = tuple(shape)
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in normalized):
        raise ValueError(f"{label} dimensions must be non-negative integers")
    return normalized


def _array_shape(value: NDArray[np.generic], label: str) -> tuple[int, ...]:
    shape = getattr(value, "shape", None)
    if shape is None:
        raise ValueError(f"{label} must expose a NumPy-compatible shape")
    return tuple(int(item) for item in shape)


def _column_row_count(value: NDArray[np.generic]) -> int:
    shape = _array_shape(value, "table column values")
    if not shape:
        raise ValueError("table column values must be one-dimensional or higher")
    return shape[0]
