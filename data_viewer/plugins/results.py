"""Typed Plugin API v1 result payloads, validation, and bounded materialization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray

from data_viewer.domain import FrozenJsonMapping, JsonValue
from data_viewer.plugins.api import PluginResult, ResultKind, ResultProvenance


INLINE_RESULT_BUDGET_BYTES = 64 * 1024 * 1024
SUPPORTED_PLOT_MARKS = ("line", "scatter", "histogram", "box", "heatmap", "image")


class ResultValidationError(ValueError):
    """Raised when a plugin result cannot cross the public result boundary."""


@dataclass(frozen=True, slots=True)
class ResultColumn:
    """One typed column in a table result."""

    name: str
    dtype: str
    unit: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ResultValidationError("table column name must not be empty")
        if not self.dtype:
            raise ResultValidationError("table column dtype must not be empty")

    def to_json(self) -> dict[str, JsonValue]:
        return {"name": self.name, "dtype": self.dtype, "unit": self.unit}


@dataclass(frozen=True, slots=True)
class TableResultPayload:
    """Bounded JSON-safe table payload for plugin results."""

    columns: tuple[ResultColumn, ...]
    rows: tuple[Mapping[str, JsonValue], ...]

    def __post_init__(self) -> None:
        columns = tuple(self.columns)
        if not columns:
            raise ResultValidationError("table result requires at least one column")
        names = tuple(column.name for column in columns)
        if len(set(names)) != len(names):
            raise ResultValidationError("table result column names must be unique")
        normalized_rows: list[Mapping[str, JsonValue]] = []
        expected = set(names)
        for row in self.rows:
            if set(row) != expected:
                raise ResultValidationError("table result row keys must match columns")
            normalized_rows.append(_freeze_mapping(row, "table result row"))
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "rows", tuple(normalized_rows))

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "columns": [column.to_json() for column in self.columns],
            "rows": [
                _freeze_mapping(row, "table result row").to_json()
                for row in self.rows
            ],
        }


@dataclass(frozen=True, slots=True)
class ArrayResultPayload:
    """Array/image result payload with explicit axes and source-selection provenance."""

    values: NDArray[np.generic]
    axes: tuple[str, ...]
    source_selection: Mapping[str, JsonValue]
    units: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = np.asarray(self.values)
        if values.dtype == np.dtype("object"):
            raise ResultValidationError("array result cannot use object dtype")
        axes = tuple(self.axes)
        if len(axes) != values.ndim:
            raise ResultValidationError("array result axes must match value rank")
        if any(not axis for axis in axes):
            raise ResultValidationError("array result axes must not be empty")
        units = tuple(self.units)
        if units and len(units) != len(axes):
            raise ResultValidationError("array result units must match axes")
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "axes", axes)
        object.__setattr__(self, "source_selection", FrozenJsonMapping(self.source_selection))
        object.__setattr__(self, "units", units)

    @property
    def nbytes(self) -> int:
        return int(self.values.nbytes)

    def metadata_json(self) -> dict[str, JsonValue]:
        return {
            "shape": list(self.values.shape),
            "dtype": str(self.values.dtype),
            "axes": list(self.axes),
            "units": list(self.units),
            "source_selection": FrozenJsonMapping(self.source_selection).to_json(),
        }


@dataclass(frozen=True, slots=True)
class PlotMark:
    """One declarative plot mark owned by the application renderer."""

    kind: str
    x: tuple[float, ...]
    y: tuple[float, ...]
    label: str = ""
    values: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in SUPPORTED_PLOT_MARKS:
            raise ResultValidationError(f"plot mark kind is unsupported: {self.kind}")
        x = tuple(float(value) for value in self.x)
        y = tuple(float(value) for value in self.y)
        values = tuple(float(value) for value in self.values)
        if not x or len(x) != len(y):
            raise ResultValidationError("plot mark x/y values must be non-empty and equal length")
        if any(not isfinite(value) for value in (*x, *y)):
            raise ResultValidationError("plot mark values must be finite")
        if values and len(values) != len(x):
            raise ResultValidationError("plot mark values must match x/y length")
        if any(not isfinite(value) for value in values):
            raise ResultValidationError("plot mark values must be finite")
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "values", values)

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "kind": self.kind,
            "x": list(self.x),
            "y": list(self.y),
            "values": list(self.values),
            "label": self.label,
        }


@dataclass(frozen=True, slots=True)
class PlotSpec:
    """Declarative plot specification; never a Matplotlib/Qt figure object."""

    title: str
    x_label: str
    y_label: str
    marks: tuple[PlotMark, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.title:
            raise ResultValidationError("plot title must not be empty")
        if not self.x_label or not self.y_label:
            raise ResultValidationError("plot axes labels must not be empty")
        marks = tuple(self.marks)
        if not marks:
            raise ResultValidationError("plot result requires at least one mark")
        object.__setattr__(self, "marks", marks)
        object.__setattr__(self, "warnings", tuple(self.warnings))

    @property
    def supported_marks(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(mark.kind for mark in self.marks))

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "title": self.title,
            "x_label": self.x_label,
            "y_label": self.y_label,
            "marks": [mark.to_json() for mark in self.marks],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class ValidatedPluginResult:
    """Validated plugin result ready for workspace routing/export metadata."""

    result_id: str
    kind: ResultKind
    title: str
    payload: object
    provenance: ResultProvenance
    metadata: Mapping[str, JsonValue]
    warnings: tuple[str, ...]
    materialization: str
    result_channel: str
    stored_bytes: int = 0

    def to_export_record(self) -> dict[str, JsonValue]:
        return {
            "result_id": self.result_id,
            "plugin_id": self.provenance.plugin_id,
            "plugin_version": self.provenance.plugin_version,
            "api_version": self.provenance.api_version,
            "inputs": [_input_to_json(input_descriptor) for input_descriptor in self.provenance.inputs],
            "parameters": _freeze_mapping(
                self.provenance.parameters,
                "result provenance parameters",
            ).to_json(),
            "result_kind": self.kind.value,
            "materialization": self.materialization,
            "computation_scope": self.provenance.computation_scope,
            "sampled": self.provenance.sampled,
            "warnings": list(self.warnings),
        }

    def accessible_summary(self) -> str:
        if isinstance(self.payload, PlotSpec):
            mark_names = ", ".join(self.payload.supported_marks)
            return (
                f"{self.payload.title}; x-axis {self.payload.x_label}; "
                f"y-axis {self.payload.y_label}; marks {mark_names}"
            )
        return f"{self.title}; {self.kind.value}; materialization {self.materialization}"


class BoundedResultStore:
    """In-memory bounded store used until persistent result storage is introduced."""

    def __init__(self, *, max_bytes: int) -> None:
        if isinstance(max_bytes, bool) or max_bytes <= 0:
            raise ValueError("result store max_bytes must be positive")
        self._max_bytes = max_bytes
        self._bytes_used = 0
        self._arrays: dict[str, NDArray[np.generic]] = {}

    @property
    def bytes_used(self) -> int:
        return self._bytes_used

    def store_array(self, result_id: str, values: NDArray[np.generic]) -> int:
        nbytes = int(values.nbytes)
        if self._bytes_used + nbytes > self._max_bytes:
            raise ResultValidationError("result store budget would be exceeded")
        self._arrays[result_id] = np.array(values, copy=True)
        self._bytes_used += nbytes
        return nbytes

    def load_array(self, result_id: str) -> NDArray[np.generic]:
        return np.array(self._arrays[result_id], copy=True)


def validate_plugin_result(result: PluginResult) -> ValidatedPluginResult:
    """Validate a plugin result without forcing external materialization."""

    return materialize_plugin_result(
        result,
        store=None,
        inline_budget_bytes=INLINE_RESULT_BUDGET_BYTES,
    )


def materialize_plugin_result(
    result: PluginResult,
    *,
    store: BoundedResultStore | None,
    inline_budget_bytes: int,
) -> ValidatedPluginResult:
    """Validate a result and store oversized array-like payloads when needed."""

    if isinstance(inline_budget_bytes, bool) or inline_budget_bytes <= 0:
        raise ValueError("inline_budget_bytes must be positive")
    kind = ResultKind(result.kind)
    payload = _validate_payload(kind, result.payload)
    result_id = f"result-{uuid4()}"
    materialization = "inline"
    stored_bytes = 0
    if isinstance(payload, ArrayResultPayload) and payload.nbytes > inline_budget_bytes:
        if store is None:
            raise ResultValidationError("array result exceeds inline budget and no store was provided")
        stored_bytes = store.store_array(result_id, payload.values)
        materialization = "stored"
    metadata = _freeze_mapping(result.metadata, "result metadata")
    return ValidatedPluginResult(
        result_id=result_id,
        kind=kind,
        title=_non_empty(result.title, "result title"),
        payload=payload,
        provenance=_validate_provenance(result.provenance),
        metadata=metadata,
        warnings=tuple(_non_empty(warning, "result warning") for warning in result.warnings),
        materialization=materialization,
        result_channel=_result_channel(kind),
        stored_bytes=stored_bytes,
    )


def _validate_payload(kind: ResultKind, payload: object) -> object:
    if kind is ResultKind.SUMMARY:
        if not isinstance(payload, Mapping):
            raise ResultValidationError("summary result payload must be a JSON object")
        return _freeze_mapping(payload, "summary result payload")
    if kind is ResultKind.TABLE:
        if not isinstance(payload, TableResultPayload):
            raise ResultValidationError("table result payload must be TableResultPayload")
        return payload
    if kind in {ResultKind.ARRAY, ResultKind.IMAGE}:
        if not isinstance(payload, ArrayResultPayload):
            raise ResultValidationError(f"{kind.value} result payload must be ArrayResultPayload")
        if kind is ResultKind.IMAGE and payload.values.ndim != 2:
            raise ResultValidationError("image result payload must be a 2D array")
        return payload
    if kind is ResultKind.PLOT:
        if not isinstance(payload, PlotSpec):
            raise ResultValidationError("plot result payload must be PlotSpec")
        return payload
    if kind is ResultKind.COLLECTION:
        if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
            raise ResultValidationError("collection result payload must be a sequence")
        items = tuple(payload)
        if not items:
            raise ResultValidationError("collection result payload must not be empty")
        if not all(isinstance(item, ValidatedPluginResult) for item in items):
            raise ResultValidationError("collection result items must already be validated")
        return items
    raise ResultValidationError(f"unsupported result kind: {kind.value}")


def _validate_provenance(provenance: ResultProvenance) -> ResultProvenance:
    _non_empty(provenance.plugin_id, "plugin_id")
    _non_empty(provenance.plugin_version, "plugin_version")
    if provenance.api_version != 1:
        raise ResultValidationError("result provenance api_version must be 1")
    if not provenance.inputs:
        raise ResultValidationError("result provenance requires at least one input")
    _freeze_mapping(provenance.parameters, "result provenance parameters")
    _non_empty(provenance.computation_scope, "computation_scope")
    return provenance


def _input_to_json(input_descriptor) -> dict[str, JsonValue]:
    return {
        "source_id": input_descriptor.source_id,
        "source_fingerprint": _freeze_mapping(
            input_descriptor.source_fingerprint,
            "input source fingerprint",
        ).to_json(),
        "resource_path": input_descriptor.resource_path,
        "domain": input_descriptor.domain,
        "shape": list(input_descriptor.shape) if input_descriptor.shape is not None else None,
        "dtype": input_descriptor.dtype,
        "selection": _freeze_mapping(input_descriptor.selection, "input selection").to_json(),
        "estimated_elements": input_descriptor.estimated_elements,
        "estimated_bytes": input_descriptor.estimated_bytes,
    }


def _result_channel(kind: ResultKind) -> str:
    return {
        ResultKind.SUMMARY: "plugin.summary",
        ResultKind.TABLE: "workspace.table",
        ResultKind.ARRAY: "workspace.array",
        ResultKind.IMAGE: "workspace.image",
        ResultKind.PLOT: "workspace.plot",
        ResultKind.COLLECTION: "plugin.collection",
    }[kind]


def _non_empty(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ResultValidationError(f"{label} must not be empty")
    return value


def _freeze_mapping(value: Mapping[str, object], label: str) -> FrozenJsonMapping:
    try:
        return FrozenJsonMapping({str(key): _json_value(item) for key, item in value.items()})
    except ValueError as exc:
        raise ResultValidationError(f"{label} must be JSON-safe") from exc


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    raise ValueError(f"unsupported JSON value: {type(value).__name__}")


__all__ = [
    "ArrayResultPayload",
    "BoundedResultStore",
    "PlotMark",
    "PlotSpec",
    "ResultColumn",
    "ResultValidationError",
    "TableResultPayload",
    "ValidatedPluginResult",
    "materialize_plugin_result",
    "validate_plugin_result",
]
