# DataSource API v1

## 1. Purpose

The DataSource API isolates file-format behavior from application, UI, workspace, and plugin code. This contract is normative. Implementations may add private helpers but may not change public semantics without a new API version and ADR.

## 2. Design rules

- Adapter instances are stateless descriptors/factories.
- Open file handles live in source sessions owned by `DocumentController`.
- Resource identity is stable for the lifetime of a source fingerprint.
- Metadata and payload reads are separate.
- Pagination, selections, budgets, cancellation, and errors are explicit.
- Format-specific objects do not cross the API boundary.
- NumPy arrays are allowed payloads; pandas, h5py, nibabel, openpyxl, and scipy objects are not.

## 3. Contract types

The target implementation must provide equivalent Python types under `data_viewer.domain` and `data_viewer.sources.api`.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntFlag, StrEnum, auto
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

import numpy as np
from numpy.typing import NDArray


JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class DataDomain(StrEnum):
    HIERARCHICAL_ARRAY = "hierarchical_array"
    ARRAY = "array"
    TABLE = "table"
    TEXT = "text"
    STRUCTURED = "structured"
    WORKBOOK = "workbook"
    VOLUME = "volume"
    METADATA = "metadata"


class NodeKind(StrEnum):
    ROOT = "root"
    CONTAINER = "container"
    RESOURCE = "resource"
    METADATA = "metadata"


class SourceCapability(IntFlag):
    NONE = 0
    HIERARCHY = auto()
    RANDOM_SLICE = auto()
    PAGED_ROWS = auto()
    STREAMING_READ = auto()
    SEARCH = auto()
    EDIT_PATCH = auto()
    ATOMIC_REWRITE = auto()
    SAVE_AS = auto()
    SPATIAL_METADATA = auto()
    COLUMN_SCHEMA = auto()


class OperationScope(StrEnum):
    FULL = "full"
    SLICE = "slice"
    PAGE = "page"
    SAMPLE = "sample"


@dataclass(frozen=True, slots=True)
class ResourceId:
    source_uri: str
    node_path: str


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    size_bytes: int
    modified_time_ns: int
    content_tag: str | None = None


@dataclass(frozen=True, slots=True)
class AxisSelection:
    axis: int
    index: int | None = None
    start: int | None = None
    stop: int | None = None
    step: int | None = None

    def __post_init__(self) -> None:
        has_index = self.index is not None
        has_range = any(value is not None for value in (self.start, self.stop, self.step))
        if has_index == has_range:
            raise ValueError("AxisSelection requires exactly one of index or range")
        if self.step == 0:
            raise ValueError("selection step cannot be zero")


@dataclass(frozen=True, slots=True)
class SelectionSpec:
    axes: tuple[AxisSelection, ...] = ()


@dataclass(frozen=True, slots=True)
class SampleSpec:
    method: str
    max_items: int
    seed: int


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    name: str
    dtype: str
    nullable: bool
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SpatialMetadata:
    affine: tuple[tuple[float, ...], ...]
    voxel_sizes: tuple[float, ...]
    axis_codes: tuple[str, ...]
    units: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DataMetadata:
    resource_id: ResourceId
    name: str
    domain: DataDomain
    node_kind: NodeKind
    shape: tuple[int, ...] = ()
    dtype: str = ""
    logical_size_bytes: int | None = None
    storage_size_bytes: int | None = None
    capabilities: SourceCapability = SourceCapability.NONE
    attributes: Mapping[str, JsonValue] = field(default_factory=dict)
    columns: tuple[ColumnSpec, ...] = ()
    spatial: SpatialMetadata | None = None


@dataclass(frozen=True, slots=True)
class ResourceNode:
    resource_id: ResourceId
    name: str
    node_kind: NodeKind
    domain: DataDomain
    has_children: bool
    summary: str = ""


@dataclass(frozen=True, slots=True)
class NodePage:
    items: tuple[ResourceNode, ...]
    next_cursor: str | None
    total_count: int | None


@dataclass(frozen=True, slots=True)
class ReadRequest:
    resource_id: ResourceId
    selection: SelectionSpec = SelectionSpec()
    scope: OperationScope = OperationScope.SLICE
    sample: SampleSpec | None = None
    max_bytes: int = 256 * 1024 * 1024
    row_offset: int | None = None
    row_limit: int | None = None
    selected_columns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ArrayPayload:
    values: NDArray[np.generic]
    original_shape: tuple[int, ...]
    selection: SelectionSpec


@dataclass(frozen=True, slots=True)
class TablePayload:
    columns: tuple[ColumnSpec, ...]
    column_values: tuple[NDArray[np.generic], ...]
    row_offset: int
    total_rows: int | None


@dataclass(frozen=True, slots=True)
class TextPayload:
    text: str
    offset: int
    is_complete: bool


@dataclass(frozen=True, slots=True)
class StructuredPayload:
    value: JsonValue


@dataclass(frozen=True, slots=True)
class VolumePayload:
    values: NDArray[np.generic]
    selection: SelectionSpec
    spatial: SpatialMetadata


DataPayload = ArrayPayload | TablePayload | TextPayload | StructuredPayload | VolumePayload


@dataclass(frozen=True, slots=True)
class ReadResult:
    payload: DataPayload
    scope: OperationScope
    bytes_read: int
    is_sampled: bool
    sample: SampleSpec | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProbeResult:
    adapter_id: str
    confidence: int
    detected_format: str
    reason: str

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 100:
            raise ValueError("confidence must be between 0 and 100")


class CancellationToken(Protocol):
    @property
    def is_cancelled(self) -> bool:
        raise NotImplementedError

    def raise_if_cancelled(self) -> None:
        raise NotImplementedError


ProgressCallback = Callable[[int, int | None, str], None]


class SourceSession(Protocol):
    @property
    def source_uri(self) -> str:
        raise NotImplementedError

    @property
    def fingerprint(self) -> SourceFingerprint:
        raise NotImplementedError

    @property
    def capabilities(self) -> SourceCapability:
        raise NotImplementedError

    def root(self) -> ResourceNode:
        raise NotImplementedError

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: CancellationToken,
    ) -> NodePage:
        raise NotImplementedError

    def get_metadata(
        self,
        resource: ResourceId,
        *,
        cancellation: CancellationToken,
    ) -> DataMetadata:
        raise NotImplementedError

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: CancellationToken,
        progress: ProgressCallback,
    ) -> ReadResult:
        raise NotImplementedError

    def search(
        self,
        query: str,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: CancellationToken,
    ) -> NodePage:
        raise NotImplementedError

    def refresh_fingerprint(self) -> SourceFingerprint:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class SourceAdapter(Protocol):
    @property
    def adapter_id(self) -> str:
        raise NotImplementedError

    @property
    def api_version(self) -> int:
        raise NotImplementedError

    @property
    def extensions(self) -> tuple[str, ...]:
        raise NotImplementedError

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        raise NotImplementedError

    def open(
        self,
        path: Path,
        *,
        cancellation: CancellationToken,
    ) -> SourceSession:
        raise NotImplementedError
```

## 4. Error semantics

All source errors derive from `DataViewerError` and use one of these stable codes:

| Code | Meaning | Retryable |
|---|---|---:|
| `SOURCE_UNSUPPORTED` | No adapter accepts the input | No |
| `SOURCE_AMBIGUOUS` | Multiple adapters have equal high confidence | No |
| `SOURCE_MALFORMED` | Header or structure is invalid | No |
| `SOURCE_ENCRYPTED` | Input requires unsupported credentials | No |
| `SOURCE_OPEN_FAILED` | Adapter could not open valid input | Sometimes |
| `SOURCE_CLOSED` | Operation used a closed session | No |
| `SOURCE_CHANGED` | Fingerprint changed during operation/save | Yes |
| `RESOURCE_NOT_FOUND` | Node no longer exists | Yes |
| `SELECTION_INVALID` | Selection is incompatible with metadata | No |
| `BUDGET_EXCEEDED` | Memory/disk/read budget denied | Yes |
| `READ_CANCELLED` | Cooperative cancellation | Yes |
| `READ_FAILED` | Payload read failed | Sometimes |
| `CAPABILITY_UNAVAILABLE` | Requested operation is not supported | No |

Error `details` must be JSON-compatible and may include adapter ID, format, selection summary, and redacted path. It must not include raw payload values.

## 5. Selection normalization

The application validates and normalizes user syntax before calling the adapter:

- one axis entry per original dimension;
- omitted axes expand to full slices;
- negative indices normalize against known shape;
- step cannot be zero;
- computed result shape must be non-negative;
- adapter-specific fancy indexing is not part of API v1;
- scalar resources use an empty selection and retain scalar shape `()`.

Adapters may reject a normalized selection only for a documented capability limitation.

The concrete `data_viewer.domain` implementation exposes additive helper values for this contract:

- `SelectionValidationError` and `SelectionValidationResult` carry stable, JSON-compatible validation failures for shape/page-specific errors such as duplicate axes, out-of-bounds indices, and invalid table pages.
- `NormalizedSelection` and `NormalizedAxisSelection` store one normalized entry per original dimension, provide the adapter key, and map display coordinates back to original coordinates.
- `TablePageSelection` and `NormalizedTablePage` normalize row offsets, limits, and selected column names without injecting row numbers into data columns.

`AxisSelection` construction still validates structural API mistakes such as mixing `index` with range fields or using step `0`. Shape-specific compatibility errors are reported through the structured normalization result.

## 6. Pagination

- Hierarchy pages default to 500 children.
- Table pages default to 1,000 rows.
- Cursors are opaque adapter strings and valid only for the same source fingerprint, parent/query, and page size.
- Consumers must not parse cursors.
- When total count is expensive, `total_count` is `None`.

## 7. Adapter conformance suite

Every adapter must pass shared tests for:

- probe purity and confidence;
- canonical root identity;
- stable node paths;
- metadata without full payload load where possible;
- valid and invalid selection behavior;
- pagination/cursor behavior;
- cancellation;
- close idempotence;
- malformed input errors;
- source fingerprint change;
- budget enforcement;
- thread/lease ownership.

Format-specific requirements are defined in `docs/FORMAT_SUPPORT.md`.

## 8. Compatibility policy

- `api_version` is `1` for all v1 adapters.
- Additive optional fields are allowed with defaults.
- Removing fields, changing types, or changing stable error meanings requires API v2 and a migration ADR.
- Adapter IDs and resource node paths are persisted in workspaces and therefore must remain stable.
