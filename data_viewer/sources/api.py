"""Public DataSource API v1 contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from data_viewer.domain import (
    DataMetadata,
    OperationScope,
    ReadResult,
    ResourceId,
    ResourceNode,
    SampleSpec,
    SelectionSpec,
    SourceCapability,
    SourceFingerprint,
)

DATASOURCE_API_VERSION = 1
DEFAULT_READ_MAX_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class NodePage:
    """A page of direct child/search nodes from a source session."""

    items: tuple[ResourceNode, ...]
    next_cursor: str | None
    total_count: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        if self.next_cursor is not None and not self.next_cursor:
            raise ValueError("next_cursor must be non-empty or null")
        if self.total_count is not None and (
            isinstance(self.total_count, bool) or self.total_count < 0
        ):
            raise ValueError("total_count must be a non-negative integer or null")


@dataclass(frozen=True, slots=True)
class ReadRequest:
    """A bounded payload read request with explicit selection and scope."""

    resource_id: ResourceId
    selection: SelectionSpec = field(default_factory=SelectionSpec)
    scope: OperationScope = OperationScope.SLICE
    sample: SampleSpec | None = None
    max_bytes: int = DEFAULT_READ_MAX_BYTES
    row_offset: int | None = None
    row_limit: int | None = None
    selected_columns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope", OperationScope(self.scope))
        if isinstance(self.max_bytes, bool) or self.max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")
        _validate_optional_non_negative(self.row_offset, "row_offset")
        if self.row_limit is not None and (
            isinstance(self.row_limit, bool) or self.row_limit <= 0
        ):
            raise ValueError("row_limit must be a positive integer or null")
        selected_columns = tuple(self.selected_columns)
        if any(not isinstance(column, str) or not column for column in selected_columns):
            raise ValueError("selected_columns must contain non-empty strings")
        object.__setattr__(self, "selected_columns", selected_columns)
        if self.scope is OperationScope.SAMPLE and self.sample is None:
            raise ValueError("sample scope requires sample parameters")


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """Bounded adapter probe result."""

    adapter_id: str
    confidence: int
    detected_format: str
    reason: str

    def __post_init__(self) -> None:
        if not self.adapter_id:
            raise ValueError("adapter_id must not be empty")
        if isinstance(self.confidence, bool) or not 0 <= self.confidence <= 100:
            raise ValueError("confidence must be between 0 and 100")
        if not self.detected_format:
            raise ValueError("detected_format must not be empty")
        if not self.reason:
            raise ValueError("probe reason must not be empty")


class CancellationToken(Protocol):
    """Protocol accepted by source operations for cooperative cancellation."""

    @property
    def is_cancelled(self) -> bool:
        """Whether cancellation has been requested."""
        ...

    def raise_if_cancelled(self) -> None:
        """Raise if cancellation was requested."""
        ...


ProgressCallback = Callable[[int, int | None, str], None]


class SourceSession(Protocol):
    """Open, source-owned session for one file-like source."""

    @property
    def source_uri(self) -> str:
        """Canonical source URI."""
        ...

    @property
    def fingerprint(self) -> SourceFingerprint:
        """Current source fingerprint."""
        ...

    @property
    def capabilities(self) -> SourceCapability:
        """Capabilities supported by this session."""
        ...

    def root(self) -> ResourceNode:
        """Return the root node without loading payload data."""
        ...

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: CancellationToken,
    ) -> NodePage:
        """Return one direct-child page for a parent resource."""
        ...

    def get_metadata(
        self,
        resource: ResourceId,
        *,
        cancellation: CancellationToken,
    ) -> DataMetadata:
        """Return metadata without full payload materialization."""
        ...

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: CancellationToken,
        progress: ProgressCallback,
    ) -> ReadResult:
        """Read a bounded payload for a resource request."""
        ...

    def search(
        self,
        query: str,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: CancellationToken,
    ) -> NodePage:
        """Search resource nodes with adapter-owned opaque cursors."""
        ...

    def refresh_fingerprint(self) -> SourceFingerprint:
        """Refresh and return the source fingerprint."""
        ...

    def close(self) -> None:
        """Close this source session idempotently."""
        ...


class SourceAdapter(Protocol):
    """Stateless adapter descriptor/factory."""

    @property
    def adapter_id(self) -> str:
        """Stable adapter ID persisted in workspace metadata."""
        ...

    @property
    def api_version(self) -> int:
        """DataSource API version implemented by this adapter."""
        ...

    @property
    def extensions(self) -> tuple[str, ...]:
        """Supported suffixes, including compound suffixes where applicable."""
        ...

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        """Validate whether this adapter can open path from a bounded header."""
        ...

    def open(
        self,
        path: Path,
        *,
        cancellation: CancellationToken,
    ) -> SourceSession:
        """Open a source-owned session for path."""
        ...


def _validate_optional_non_negative(value: int | None, label: str) -> None:
    if value is not None and (isinstance(value, bool) or value < 0):
        raise ValueError(f"{label} must be a non-negative integer or null")


__all__ = [
    "DATASOURCE_API_VERSION",
    "DEFAULT_READ_MAX_BYTES",
    "CancellationToken",
    "NodePage",
    "ProbeResult",
    "ProgressCallback",
    "ReadRequest",
    "SourceAdapter",
    "SourceSession",
]
