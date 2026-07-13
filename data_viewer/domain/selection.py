"""Normalized selections and coordinate mapping for Data Viewer resources."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Generic, TypeVar

from .metadata import FrozenJsonMapping, JsonValue

DEFAULT_TABLE_PAGE_SIZE = 1_000


class AxisSelectionKind(StrEnum):
    """Normalized per-axis selection kinds."""

    INDEX = "index"
    SLICE = "slice"


class SelectionErrorCode(StrEnum):
    """Stable validation error codes for selection normalization."""

    INVALID_SHAPE = "invalid_shape"
    DUPLICATE_AXIS = "duplicate_axis"
    AXIS_OUT_OF_BOUNDS = "axis_out_of_bounds"
    INDEX_OUT_OF_BOUNDS = "index_out_of_bounds"
    RANK_MISMATCH = "rank_mismatch"
    DISPLAY_INDEX_OUT_OF_BOUNDS = "display_index_out_of_bounds"
    NEGATIVE_OFFSET_WITHOUT_TOTAL = "negative_offset_without_total"
    ROW_OFFSET_OUT_OF_BOUNDS = "row_offset_out_of_bounds"
    ROW_LIMIT_INVALID = "row_limit_invalid"
    COLUMN_NAME_INVALID = "column_name_invalid"


@dataclass(frozen=True, slots=True)
class SelectionValidationError:
    """Structured, JSON-safe selection validation error."""

    code: SelectionErrorCode
    message: str
    axis: int | None = None
    details: Mapping[str, JsonValue] = field(default_factory=FrozenJsonMapping)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", SelectionErrorCode(self.code))
        if not self.message:
            raise ValueError("selection validation message must not be empty")
        if self.axis is not None and (
            isinstance(self.axis, bool) or self.axis < 0
        ):
            raise ValueError("selection validation axis must be non-negative or null")
        object.__setattr__(self, "details", FrozenJsonMapping(self.details))

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "code": self.code.value,
            "message": self.message,
            "axis": self.axis,
            "details": FrozenJsonMapping(self.details).to_json(),
        }

    @classmethod
    def from_json(
        cls,
        value: Mapping[str, JsonValue],
    ) -> "SelectionValidationError":
        axis_value = value.get("axis")
        if axis_value is not None:
            axis_value = _expect_int(axis_value, "selection error axis")
        return cls(
            code=SelectionErrorCode(str(value["code"])),
            message=str(value["message"]),
            axis=axis_value,
            details=_expect_mapping(value.get("details", {}), "selection details"),
        )


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class SelectionValidationResult(Generic[T]):
    """Result value for non-throwing selection/page normalization."""

    value: T | None = None
    errors: tuple[SelectionValidationError, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "errors", tuple(self.errors))
        if self.value is None and not self.errors:
            raise ValueError("selection validation result needs a value or errors")
        if self.value is not None and self.errors:
            raise ValueError("selection validation result cannot mix value and errors")

    @classmethod
    def valid(cls, value: T) -> "SelectionValidationResult[T]":
        return cls(value=value)

    @classmethod
    def invalid(
        cls,
        errors: Iterable[SelectionValidationError],
    ) -> "SelectionValidationResult[T]":
        return cls(value=None, errors=tuple(errors))

    @property
    def ok(self) -> bool:
        return self.value is not None

    def unwrap(self) -> T:
        if self.value is None:
            joined = "; ".join(error.message for error in self.errors)
            raise ValueError(f"selection validation failed: {joined}")
        return self.value


@dataclass(frozen=True, slots=True)
class AxisSelection:
    """User/API selection for one original axis."""

    axis: int
    index: int | None = None
    start: int | None = None
    stop: int | None = None
    step: int | None = None

    def __post_init__(self) -> None:
        _validate_axis(self.axis)
        has_index = self.index is not None
        has_range = any(value is not None for value in (self.start, self.stop, self.step))
        if has_index == has_range:
            raise ValueError("AxisSelection requires exactly one of index or range")
        for label, value in (
            ("index", self.index),
            ("start", self.start),
            ("stop", self.stop),
            ("step", self.step),
        ):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise ValueError(f"selection {label} must be an integer or null")
        if self.step == 0:
            raise ValueError("selection step cannot be zero")

    @classmethod
    def slice(
        cls,
        axis: int,
        *,
        start: int | None = None,
        stop: int | None = None,
        step: int | None = None,
    ) -> "AxisSelection":
        return cls(axis=axis, start=start, stop=stop, step=1 if step is None else step)

    @classmethod
    def all(cls, axis: int) -> "AxisSelection":
        return cls.slice(axis)

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "axis": self.axis,
            "index": self.index,
            "start": self.start,
            "stop": self.stop,
            "step": self.step,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "AxisSelection":
        return cls(
            axis=_expect_int(value["axis"], "axis"),
            index=_optional_int(value.get("index"), "index"),
            start=_optional_int(value.get("start"), "start"),
            stop=_optional_int(value.get("stop"), "stop"),
            step=_optional_int(value.get("step"), "step"),
        )


@dataclass(frozen=True, slots=True)
class SelectionSpec:
    """Possibly sparse user/API selection over original axes."""

    axes: tuple[AxisSelection, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "axes", tuple(self.axes))

    @classmethod
    def all(cls) -> "SelectionSpec":
        return cls()

    @classmethod
    def index(cls, axis: int, index: int) -> "SelectionSpec":
        return cls((AxisSelection(axis=axis, index=index),))

    @classmethod
    def slice(
        cls,
        axis: int,
        *,
        start: int | None = None,
        stop: int | None = None,
        step: int | None = None,
    ) -> "SelectionSpec":
        return cls((AxisSelection.slice(axis, start=start, stop=stop, step=step),))

    @classmethod
    def hyperslab(cls, *axes: AxisSelection) -> "SelectionSpec":
        return cls(tuple(axes))

    def normalize(
        self,
        shape: tuple[int, ...],
    ) -> SelectionValidationResult["NormalizedSelection"]:
        shape_result = _normalize_shape(shape)
        if isinstance(shape_result, SelectionValidationError):
            return SelectionValidationResult.invalid((shape_result,))
        original_shape = shape_result
        errors = _validate_axis_references(self.axes, len(original_shape))
        if errors:
            return SelectionValidationResult.invalid(errors)

        axis_specs = {axis.axis: axis for axis in self.axes}
        normalized_axes: list[NormalizedAxisSelection] = []
        for axis, dimension in enumerate(original_shape):
            selection = axis_specs.get(axis)
            if selection is None:
                normalized_axes.append(
                    NormalizedAxisSelection.slice_axis(
                        axis=axis,
                        start=0,
                        stop=dimension,
                        step=1,
                        length=dimension,
                    )
                )
                continue
            normalized = _normalize_axis(selection, dimension)
            if isinstance(normalized, SelectionValidationError):
                errors.append(normalized)
                continue
            normalized_axes.append(normalized)
        if errors:
            return SelectionValidationResult.invalid(errors)
        return SelectionValidationResult.valid(
            NormalizedSelection(
                original_shape=original_shape,
                axes=tuple(normalized_axes),
            )
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {"axes": [axis.to_json() for axis in self.axes]}

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "SelectionSpec":
        axes = _expect_list(value.get("axes", []), "selection axes")
        return cls(tuple(AxisSelection.from_json(_expect_mapping(axis, "axis")) for axis in axes))


@dataclass(frozen=True, slots=True)
class NormalizedAxisSelection:
    """Per-axis normalized selection in original coordinates."""

    axis: int
    kind: AxisSelectionKind
    index: int | None = None
    start: int | None = None
    stop: int | None = None
    step: int | None = None
    length: int = 0

    def __post_init__(self) -> None:
        _validate_axis(self.axis)
        object.__setattr__(self, "kind", AxisSelectionKind(self.kind))
        if self.kind is AxisSelectionKind.INDEX:
            if self.index is None:
                raise ValueError("normalized index selection requires an index")
            if self.length != 0:
                raise ValueError("normalized index selection length must be zero")
        else:
            if self.start is None or self.stop is None or self.step is None:
                raise ValueError("normalized slice selection requires start, stop, and step")
            if self.step == 0:
                raise ValueError("normalized slice step cannot be zero")
            if self.length < 0:
                raise ValueError("normalized slice length must be non-negative")

    @classmethod
    def index_axis(cls, *, axis: int, index: int) -> "NormalizedAxisSelection":
        return cls(axis=axis, kind=AxisSelectionKind.INDEX, index=index)

    @classmethod
    def slice_axis(
        cls,
        *,
        axis: int,
        start: int,
        stop: int,
        step: int,
        length: int,
    ) -> "NormalizedAxisSelection":
        return cls(
            axis=axis,
            kind=AxisSelectionKind.SLICE,
            start=start,
            stop=stop,
            step=step,
            length=length,
        )

    @property
    def contributes_display_axis(self) -> bool:
        return self.kind is AxisSelectionKind.SLICE

    def source_index(self, display_position: int) -> int:
        if self.kind is AxisSelectionKind.INDEX:
            if self.index is None:
                raise ValueError("normalized index selection is missing index")
            return self.index
        if isinstance(display_position, bool) or not isinstance(display_position, int):
            raise ValueError("display index must be an integer")
        if display_position < 0 or display_position >= self.length:
            raise ValueError("display index is out of bounds")
        if self.start is None or self.step is None:
            raise ValueError("normalized slice selection is incomplete")
        return self.start + display_position * self.step

    def to_python(self) -> int | slice:
        if self.kind is AxisSelectionKind.INDEX:
            if self.index is None:
                raise ValueError("normalized index selection is missing index")
            return self.index
        return slice(self.start, self.stop, self.step)

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "axis": self.axis,
            "kind": self.kind.value,
            "index": self.index,
            "start": self.start,
            "stop": self.stop,
            "step": self.step,
            "length": self.length,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "NormalizedAxisSelection":
        return cls(
            axis=_expect_int(value["axis"], "axis"),
            kind=AxisSelectionKind(str(value["kind"])),
            index=_optional_int(value.get("index"), "index"),
            start=_optional_int(value.get("start"), "start"),
            stop=_optional_int(value.get("stop"), "stop"),
            step=_optional_int(value.get("step"), "step"),
            length=_expect_int(value.get("length", 0), "length"),
        )


@dataclass(frozen=True, slots=True)
class NormalizedSelection:
    """Selection normalized against a known original shape."""

    original_shape: tuple[int, ...]
    axes: tuple[NormalizedAxisSelection, ...]

    def __post_init__(self) -> None:
        shape_result = _normalize_shape(self.original_shape)
        if isinstance(shape_result, SelectionValidationError):
            raise ValueError(shape_result.message)
        axes = tuple(self.axes)
        if len(axes) != len(shape_result):
            raise ValueError("normalized selection needs one axis per original dimension")
        for expected_axis, axis in enumerate(axes):
            if axis.axis != expected_axis:
                raise ValueError("normalized selection axes must be ordered by dimension")
        object.__setattr__(self, "original_shape", shape_result)
        object.__setattr__(self, "axes", axes)

    @property
    def result_shape(self) -> tuple[int, ...]:
        return tuple(axis.length for axis in self.axes if axis.contributes_display_axis)

    def to_numpy_key(self) -> tuple[int | slice, ...]:
        return tuple(axis.to_python() for axis in self.axes)

    def source_coordinates(self, display_index: tuple[int, ...]) -> tuple[int, ...]:
        if len(display_index) != len(self.result_shape):
            raise ValueError("display index rank does not match selection result shape")
        coordinates: list[int] = []
        display_axis = 0
        for axis in self.axes:
            if axis.contributes_display_axis:
                coordinates.append(axis.source_index(display_index[display_axis]))
                display_axis += 1
            else:
                coordinates.append(axis.source_index(0))
        return tuple(coordinates)

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "original_shape": list(self.original_shape),
            "result_shape": list(self.result_shape),
            "axes": [axis.to_json() for axis in self.axes],
        }

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "NormalizedSelection":
        shape = _expect_list(value["original_shape"], "original shape")
        axes = _expect_list(value["axes"], "normalized axes")
        return cls(
            original_shape=tuple(_expect_int(item, "shape dimension") for item in shape),
            axes=tuple(
                NormalizedAxisSelection.from_json(_expect_mapping(axis, "axis"))
                for axis in axes
            ),
        )


@dataclass(frozen=True, slots=True)
class TablePageSelection:
    """Requested page over original table rows."""

    row_offset: int = 0
    row_limit: int = DEFAULT_TABLE_PAGE_SIZE
    selected_columns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for label, value in (
            ("row offset", self.row_offset),
            ("row limit", self.row_limit),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{label} must be an integer")
        object.__setattr__(self, "selected_columns", tuple(self.selected_columns))

    def normalize(
        self,
        *,
        total_rows: int | None,
    ) -> SelectionValidationResult["NormalizedTablePage"]:
        errors: list[SelectionValidationError] = []
        if total_rows is not None and (
            isinstance(total_rows, bool) or total_rows < 0
        ):
            errors.append(
                SelectionValidationError(
                    SelectionErrorCode.INVALID_SHAPE,
                    "total rows must be a non-negative integer or null",
                )
            )
        if self.row_limit <= 0:
            errors.append(
                SelectionValidationError(
                    SelectionErrorCode.ROW_LIMIT_INVALID,
                    "row limit must be positive",
                    details={"row_limit": self.row_limit},
                )
            )
        for column in self.selected_columns:
            if not isinstance(column, str) or not column:
                errors.append(
                    SelectionValidationError(
                        SelectionErrorCode.COLUMN_NAME_INVALID,
                        "selected column names must be non-empty strings",
                    )
                )
                break
        if errors:
            return SelectionValidationResult.invalid(errors)

        row_offset = self.row_offset
        if row_offset < 0:
            if total_rows is None:
                return SelectionValidationResult.invalid(
                    (
                        SelectionValidationError(
                            SelectionErrorCode.NEGATIVE_OFFSET_WITHOUT_TOTAL,
                            "negative row offset requires a known total row count",
                            details={"row_offset": row_offset},
                        ),
                    )
                )
            row_offset = total_rows + row_offset
        if row_offset < 0 or (total_rows is not None and row_offset > total_rows):
            return SelectionValidationResult.invalid(
                (
                    SelectionValidationError(
                        SelectionErrorCode.ROW_OFFSET_OUT_OF_BOUNDS,
                        "row offset is outside the known table bounds",
                        details={"row_offset": row_offset, "total_rows": total_rows},
                    ),
                )
            )

        row_limit = self.row_limit
        if total_rows is not None:
            row_limit = min(row_limit, max(0, total_rows - row_offset))
        return SelectionValidationResult.valid(
            NormalizedTablePage(
                row_offset=row_offset,
                row_limit=row_limit,
                total_rows=total_rows,
                selected_columns=self.selected_columns,
            )
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "row_offset": self.row_offset,
            "row_limit": self.row_limit,
            "selected_columns": list(self.selected_columns),
        }


@dataclass(frozen=True, slots=True)
class NormalizedTablePage:
    """Normalized table page in original row coordinates."""

    row_offset: int
    row_limit: int
    total_rows: int | None
    selected_columns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.row_offset < 0:
            raise ValueError("row offset must be non-negative")
        if self.row_limit < 0:
            raise ValueError("row limit must be non-negative")
        if self.total_rows is not None and self.total_rows < 0:
            raise ValueError("total rows must be non-negative or null")
        object.__setattr__(self, "selected_columns", tuple(self.selected_columns))

    @property
    def row_stop(self) -> int:
        return self.row_offset + self.row_limit

    def source_row(self, display_row: int) -> int:
        if isinstance(display_row, bool) or not isinstance(display_row, int):
            raise ValueError("display row must be an integer")
        if display_row < 0 or display_row >= self.row_limit:
            raise ValueError("display row is out of bounds")
        return self.row_offset + display_row

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "row_offset": self.row_offset,
            "row_limit": self.row_limit,
            "row_stop": self.row_stop,
            "total_rows": self.total_rows,
            "selected_columns": list(self.selected_columns),
        }


def _normalize_axis(
    selection: AxisSelection,
    dimension: int,
) -> NormalizedAxisSelection | SelectionValidationError:
    if selection.index is not None:
        index = selection.index
        if index < 0:
            index = dimension + index
        if index < 0 or index >= dimension:
            return SelectionValidationError(
                SelectionErrorCode.INDEX_OUT_OF_BOUNDS,
                "selection index is outside axis bounds",
                axis=selection.axis,
                details={
                    "index": selection.index,
                    "normalized_index": index,
                    "dimension": dimension,
                },
            )
        return NormalizedAxisSelection.index_axis(axis=selection.axis, index=index)

    start, stop, step = slice(selection.start, selection.stop, selection.step).indices(
        dimension
    )
    length = len(range(start, stop, step))
    return NormalizedAxisSelection.slice_axis(
        axis=selection.axis,
        start=start,
        stop=stop,
        step=step,
        length=length,
    )


def _validate_axis_references(
    axes: tuple[AxisSelection, ...],
    ndim: int,
) -> list[SelectionValidationError]:
    errors: list[SelectionValidationError] = []
    seen: set[int] = set()
    for selection in axes:
        if selection.axis in seen:
            errors.append(
                SelectionValidationError(
                    SelectionErrorCode.DUPLICATE_AXIS,
                    "selection specifies the same axis more than once",
                    axis=selection.axis,
                )
            )
            continue
        seen.add(selection.axis)
        if selection.axis >= ndim:
            errors.append(
                SelectionValidationError(
                    SelectionErrorCode.AXIS_OUT_OF_BOUNDS,
                    "selection axis is outside resource rank",
                    axis=selection.axis,
                    details={"axis": selection.axis, "rank": ndim},
                )
            )
    return errors


def _normalize_shape(
    shape: tuple[int, ...],
) -> tuple[int, ...] | SelectionValidationError:
    try:
        normalized = tuple(shape)
    except TypeError:
        return SelectionValidationError(
            SelectionErrorCode.INVALID_SHAPE,
            "shape must be an iterable of non-negative integers",
        )
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in normalized):
        return SelectionValidationError(
            SelectionErrorCode.INVALID_SHAPE,
            "shape dimensions must be non-negative integers",
        )
    return normalized


def _validate_axis(axis: int) -> None:
    if isinstance(axis, bool) or not isinstance(axis, int) or axis < 0:
        raise ValueError("selection axis must be a non-negative integer")


def _expect_mapping(value: JsonValue, label: str) -> Mapping[str, JsonValue]:
    if isinstance(value, dict):
        return value
    raise ValueError(f"{label} must be a JSON object")


def _expect_list(value: JsonValue, label: str) -> list[JsonValue]:
    if isinstance(value, list):
        return value
    raise ValueError(f"{label} must be a JSON array")


def _expect_int(value: JsonValue, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer JSON value")
    return value


def _optional_int(value: JsonValue, label: str) -> int | None:
    if value is None:
        return None
    return _expect_int(value, label)
