"""Immutable metadata values for Data Viewer resources."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
import math
from typing import TYPE_CHECKING, Any

from .capabilities import (
    DataDomain,
    NodeKind,
    SourceCapability,
    capabilities_from_names,
    capabilities_to_names,
)

if TYPE_CHECKING:
    from .resources import ResourceId

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
_FrozenJsonValue = JsonScalar | tuple[str, tuple[Any, ...]]


def _freeze_json(value: JsonValue) -> _FrozenJsonValue:
    if value is None or isinstance(value, str | bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON metadata cannot contain NaN or infinity")
        return value
    if isinstance(value, list):
        return ("list", tuple(_freeze_json(item) for item in value))
    if isinstance(value, dict):
        frozen_items: list[tuple[str, _FrozenJsonValue]] = []
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON metadata object keys must be strings")
            frozen_items.append((key, _freeze_json(item)))
        return ("dict", tuple(sorted(frozen_items)))
    raise ValueError(f"unsupported JSON metadata value: {type(value).__name__}")


def _thaw_json(value: _FrozenJsonValue) -> JsonValue:
    if isinstance(value, tuple):
        tag, payload = value
        if tag == "list":
            return [_thaw_json(item) for item in payload]
        if tag == "dict":
            return {key: _thaw_json(item) for key, item in payload}
        raise ValueError(f"unknown frozen JSON tag: {tag}")
    return value


class FrozenJsonMapping(Mapping[str, JsonValue]):
    """Hashable, immutable copy of a JSON-compatible mapping."""

    __slots__ = ("_index", "_items")
    _index: dict[str, _FrozenJsonValue]
    _items: tuple[tuple[str, _FrozenJsonValue], ...]

    def __init__(
        self,
        values: Mapping[str, JsonValue] | Iterable[tuple[str, JsonValue]] = (),
    ) -> None:
        if isinstance(values, FrozenJsonMapping):
            self._items = values._items
            self._index = values._index
            return
        raw_items = values.items() if isinstance(values, Mapping) else values
        frozen_items: list[tuple[str, _FrozenJsonValue]] = []
        for key, value in raw_items:
            if not isinstance(key, str):
                raise ValueError("JSON metadata object keys must be strings")
            frozen_items.append((key, _freeze_json(value)))
        self._items = tuple(sorted(frozen_items))
        self._index = dict(self._items)

    def __getitem__(self, key: str) -> JsonValue:
        return _thaw_json(self._index[key])

    def __iter__(self) -> Iterator[str]:
        return (key for key, _value in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __hash__(self) -> int:
        return hash(self._items)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return self._items == FrozenJsonMapping(other)._items
        return NotImplemented

    def to_json(self) -> dict[str, JsonValue]:
        """Return a JSON-compatible mutable copy."""
        return {key: _thaw_json(value) for key, value in self._items}


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    """Column metadata for table-like resources."""

    name: str
    dtype: str
    nullable: bool
    metadata: Mapping[str, JsonValue] = field(default_factory=FrozenJsonMapping)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("column name must not be empty")
        if not self.dtype:
            raise ValueError("column dtype must not be empty")
        object.__setattr__(self, "metadata", FrozenJsonMapping(self.metadata))

    def __hash__(self) -> int:
        return hash((self.name, self.dtype, self.nullable, self.metadata))

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "name": self.name,
            "dtype": self.dtype,
            "nullable": self.nullable,
            "metadata": self.metadata.to_json()
            if isinstance(self.metadata, FrozenJsonMapping)
            else FrozenJsonMapping(self.metadata).to_json(),
        }

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "ColumnSpec":
        metadata = _expect_mapping(value.get("metadata", {}), "column metadata")
        return cls(
            name=str(value["name"]),
            dtype=str(value["dtype"]),
            nullable=_expect_bool(value["nullable"], "column nullable"),
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True)
class SpatialMetadata:
    """Spatial metadata for volume resources."""

    affine: tuple[tuple[float, ...], ...]
    voxel_sizes: tuple[float, ...]
    axis_codes: tuple[str, ...]
    units: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_finite_rows(self.affine, "affine")
        _validate_positive_floats(self.voxel_sizes, "voxel size")
        if any(not code for code in self.axis_codes):
            raise ValueError("axis codes must not be empty")
        if any(not unit for unit in self.units):
            raise ValueError("spatial units must not be empty")

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "affine": [list(row) for row in self.affine],
            "voxel_sizes": list(self.voxel_sizes),
            "axis_codes": list(self.axis_codes),
            "units": list(self.units),
        }

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "SpatialMetadata":
        affine_rows = _expect_list(value.get("affine"), "affine")
        voxel_sizes = _expect_list(value.get("voxel_sizes"), "voxel_sizes")
        axis_codes = _expect_list(value.get("axis_codes"), "axis_codes")
        units = _expect_list(value.get("units"), "units")
        return cls(
            affine=tuple(
                tuple(_expect_float(item, "affine value") for item in row)
                for row in (_expect_list(row, "affine row") for row in affine_rows)
            ),
            voxel_sizes=tuple(
                _expect_float(item, "voxel size") for item in voxel_sizes
            ),
            axis_codes=tuple(str(item) for item in axis_codes),
            units=tuple(str(item) for item in units),
        )


@dataclass(frozen=True, slots=True)
class DataMetadata:
    """Resource metadata returned without requiring payload materialization."""

    resource_id: ResourceId
    name: str
    domain: DataDomain
    node_kind: NodeKind
    shape: tuple[int, ...] = ()
    dtype: str = ""
    logical_size_bytes: int | None = None
    storage_size_bytes: int | None = None
    capabilities: SourceCapability = SourceCapability.NONE
    attributes: Mapping[str, JsonValue] = field(default_factory=FrozenJsonMapping)
    columns: tuple[ColumnSpec, ...] = ()
    spatial: SpatialMetadata | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("metadata name must not be empty")
        object.__setattr__(self, "domain", DataDomain(self.domain))
        object.__setattr__(self, "node_kind", NodeKind(self.node_kind))
        object.__setattr__(self, "shape", _validate_shape(self.shape))
        _validate_optional_size(self.logical_size_bytes, "logical size")
        _validate_optional_size(self.storage_size_bytes, "storage size")
        object.__setattr__(self, "capabilities", SourceCapability(self.capabilities))
        object.__setattr__(self, "attributes", FrozenJsonMapping(self.attributes))
        object.__setattr__(self, "columns", tuple(self.columns))

    def __hash__(self) -> int:
        return hash(
            (
                self.resource_id,
                self.name,
                self.domain,
                self.node_kind,
                self.shape,
                self.dtype,
                self.logical_size_bytes,
                self.storage_size_bytes,
                self.capabilities,
                self.attributes,
                self.columns,
                self.spatial,
            )
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "resource_id": self.resource_id.to_json(),
            "name": self.name,
            "domain": self.domain.value,
            "node_kind": self.node_kind.value,
            "shape": list(self.shape),
            "dtype": self.dtype,
            "logical_size_bytes": self.logical_size_bytes,
            "storage_size_bytes": self.storage_size_bytes,
            "capabilities": list(capabilities_to_names(self.capabilities)),
            "attributes": FrozenJsonMapping(self.attributes).to_json(),
            "columns": [column.to_json() for column in self.columns],
            "spatial": self.spatial.to_json() if self.spatial is not None else None,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "DataMetadata":
        from .resources import ResourceId

        resource_id = _expect_mapping(value["resource_id"], "resource_id")
        shape = _expect_list(value.get("shape", []), "shape")
        capabilities = _expect_list(value.get("capabilities", []), "capabilities")
        attributes = _expect_mapping(value.get("attributes", {}), "attributes")
        columns = _expect_list(value.get("columns", []), "columns")
        spatial_value = value.get("spatial")
        return cls(
            resource_id=ResourceId.from_json(resource_id),
            name=str(value["name"]),
            domain=DataDomain(str(value["domain"])),
            node_kind=NodeKind(str(value["node_kind"])),
            shape=tuple(_expect_int(item, "shape dimension") for item in shape),
            dtype=str(value.get("dtype", "")),
            logical_size_bytes=_optional_int(value.get("logical_size_bytes")),
            storage_size_bytes=_optional_int(value.get("storage_size_bytes")),
            capabilities=capabilities_from_names(str(item) for item in capabilities),
            attributes=attributes,
            columns=tuple(
                ColumnSpec.from_json(_expect_mapping(item, "column"))
                for item in columns
            ),
            spatial=SpatialMetadata.from_json(spatial_value)
            if isinstance(spatial_value, Mapping)
            else None,
        )


def _validate_shape(shape: tuple[int, ...]) -> tuple[int, ...]:
    validated = tuple(shape)
    if any(isinstance(item, bool) or item < 0 for item in validated):
        raise ValueError("shape dimensions must be non-negative integers")
    return validated


def _validate_optional_size(value: int | None, label: str) -> None:
    if value is not None and (isinstance(value, bool) or value < 0):
        raise ValueError(f"{label} must be a non-negative integer")


def _optional_int(value: JsonValue) -> int | None:
    if value is None:
        return None
    return _expect_int(value, "optional integer")


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


def _expect_float(value: JsonValue, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a numeric JSON value")
    return float(value)


def _expect_bool(value: JsonValue, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean JSON value")
    return value


def _validate_finite_rows(rows: tuple[tuple[float, ...], ...], label: str) -> None:
    if not rows:
        raise ValueError(f"{label} must not be empty")
    row_length = len(rows[0])
    if row_length == 0:
        raise ValueError(f"{label} rows must not be empty")
    for row in rows:
        if len(row) != row_length:
            raise ValueError(f"{label} rows must have equal lengths")
        if any(not math.isfinite(item) for item in row):
            raise ValueError(f"{label} values must be finite")


def _validate_positive_floats(values: tuple[float, ...], label: str) -> None:
    if not values:
        raise ValueError(f"{label}s must not be empty")
    if any(not math.isfinite(item) or item <= 0 for item in values):
        raise ValueError(f"{label}s must be positive finite values")
