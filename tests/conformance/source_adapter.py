"""Shared SourceAdapter conformance fixtures and assertions."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from data_viewer.domain import (
    ArrayPayload,
    DataDomain,
    DataMetadata,
    DataViewerError,
    ErrorCode,
    NodeKind,
    OperationScope,
    ReadResult,
    ResourceId,
    ResourceNode,
    SelectionSpec,
    SourceCapability,
    SourceFingerprint,
)
from data_viewer.sources.api import (
    DATASOURCE_API_VERSION,
    NodePage,
    ProbeResult,
    ProgressCallback,
    ReadRequest,
)
from data_viewer.sources.registry import SourceRegistry
from data_viewer.tasks import CancellationToken

FAKE_HEADER = b"DVFAKE\n"
FAKE_VALUES = np.arange(6, dtype=np.int64).reshape(2, 3)


def write_fake_source(path: Path, *, payload: bytes = b"payload") -> Path:
    path.write_bytes(FAKE_HEADER + payload)
    return path


class FakeArrayAdapter:
    """Small in-memory adapter used to prove the public SourceAdapter contract."""

    adapter_id: str = "fake.array"
    api_version = DATASOURCE_API_VERSION
    extensions: tuple[str, ...] = (".fake",)

    def __init__(
        self,
        *,
        adapter_id: str | None = None,
        extensions: tuple[str, ...] | None = None,
        confidence: int = 95,
        detected_format: str = "fake-array",
    ) -> None:
        self.adapter_id = adapter_id or type(self).adapter_id
        self.extensions = extensions or type(self).extensions
        self.confidence = confidence
        self.detected_format = detected_format
        self.probe_header_lengths: list[int] = []
        self.last_session: FakeArraySession | None = None

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        self.probe_header_lengths.append(len(header))
        if header.startswith(FAKE_HEADER):
            return ProbeResult(
                adapter_id=self.adapter_id,
                confidence=self.confidence,
                detected_format=self.detected_format,
                reason=f"{path.name} starts with the fake conformance signature",
            )
        return None

    def open(self, path: Path, *, cancellation: CancellationToken) -> "FakeArraySession":
        _raise_read_cancelled_if_needed(cancellation, operation="source.open")
        header = path.read_bytes()[: len(FAKE_HEADER)]
        if header != FAKE_HEADER:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="Fake source header is malformed.",
                operation="source.open",
                details={"adapter_id": self.adapter_id},
            )
        session = FakeArraySession(path)
        self.last_session = session
        return session


class FakeArraySession:
    """SourceSession implementation with one array resource and no library leaks."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._source_uri = path.resolve(strict=False).as_uri()
        self._fingerprint = _fingerprint(path)
        self._closed = False
        self.close_count = 0

    @property
    def source_uri(self) -> str:
        return self._source_uri

    @property
    def fingerprint(self) -> SourceFingerprint:
        return self._fingerprint

    @property
    def capabilities(self) -> SourceCapability:
        return (
            SourceCapability.HIERARCHY
            | SourceCapability.RANDOM_SLICE
            | SourceCapability.SEARCH
        )

    def root(self) -> ResourceNode:
        self._ensure_open("source.root")
        return ResourceNode(
            resource_id=ResourceId(self.source_uri, "/"),
            name=self._path.name,
            node_kind=NodeKind.ROOT,
            domain=DataDomain.HIERARCHICAL_ARRAY,
            has_children=True,
            summary="fake conformance root",
        )

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: CancellationToken,
    ) -> NodePage:
        self._ensure_open("source.list_children")
        _raise_read_cancelled_if_needed(cancellation, operation="source.list_children")
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        if parent != ResourceId(self.source_uri, "/"):
            raise _not_found(parent, operation="source.list_children")
        start = int(cursor) if cursor is not None else 0
        children = (
            ResourceNode(
                resource_id=ResourceId(self.source_uri, "/array"),
                name="array",
                node_kind=NodeKind.RESOURCE,
                domain=DataDomain.ARRAY,
                has_children=False,
                summary="2 x 3 int64",
            ),
        )
        stop = min(start + page_size, len(children))
        return NodePage(
            items=children[start:stop],
            next_cursor=str(stop) if stop < len(children) else None,
            total_count=len(children),
        )

    def get_metadata(
        self,
        resource: ResourceId,
        *,
        cancellation: CancellationToken,
    ) -> DataMetadata:
        self._ensure_open("source.get_metadata")
        _raise_read_cancelled_if_needed(cancellation, operation="source.get_metadata")
        if resource != ResourceId(self.source_uri, "/array"):
            raise _not_found(resource, operation="source.get_metadata")
        return DataMetadata(
            resource_id=resource,
            name="array",
            domain=DataDomain.ARRAY,
            node_kind=NodeKind.RESOURCE,
            shape=FAKE_VALUES.shape,
            dtype=str(FAKE_VALUES.dtype),
            logical_size_bytes=FAKE_VALUES.nbytes,
            storage_size_bytes=self._fingerprint.size_bytes,
            capabilities=SourceCapability.RANDOM_SLICE,
        )

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: CancellationToken,
        progress: ProgressCallback,
    ) -> ReadResult:
        self._ensure_open("source.read")
        _raise_read_cancelled_if_needed(cancellation, operation="source.read")
        if request.resource_id != ResourceId(self.source_uri, "/array"):
            raise _not_found(request.resource_id, operation="source.read")
        if request.max_bytes < FAKE_VALUES.nbytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Fake read exceeds the requested byte budget.",
                operation="source.read",
                resource_id=request.resource_id,
                details={"max_bytes": request.max_bytes},
            )
        normalized = request.selection.normalize(FAKE_VALUES.shape)
        if not normalized.ok:
            raise DataViewerError(
                code=ErrorCode.SELECTION_INVALID,
                message="Fake selection is invalid for the array shape.",
                operation="source.read",
                resource_id=request.resource_id,
                details={
                    "errors": [error.to_json() for error in normalized.errors],
                },
            )
        reporter = progress
        reporter(0, 1, "start")
        values = FAKE_VALUES[normalized.unwrap().to_numpy_key()]
        reporter(1, 1, "done")
        return ReadResult(
            payload=ArrayPayload(
                values=np.asarray(values),
                original_shape=FAKE_VALUES.shape,
                selection=normalized.unwrap(),
            ),
            scope=request.scope,
            bytes_read=int(np.asarray(values).nbytes),
            is_sampled=False,
            sample=None,
        )

    def search(
        self,
        query: str,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: CancellationToken,
    ) -> NodePage:
        self._ensure_open("source.search")
        _raise_read_cancelled_if_needed(cancellation, operation="source.search")
        root = self.root()
        if "array".startswith(query.lower()):
            return self.list_children(
                root.resource_id,
                cursor=cursor,
                page_size=page_size,
                cancellation=cancellation,
            )
        return NodePage(items=(), next_cursor=None, total_count=0)

    def refresh_fingerprint(self) -> SourceFingerprint:
        self._ensure_open("source.refresh_fingerprint")
        self._fingerprint = _fingerprint(self._path)
        return self._fingerprint

    def close(self) -> None:
        if not self._closed:
            self.close_count += 1
            self._closed = True

    def _ensure_open(self, operation: str) -> None:
        if self._closed:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CLOSED,
                message="Fake source session is closed.",
                operation=operation,
            )


def assert_source_adapter_conformance(
    registry: SourceRegistry,
    path: Path,
    adapter: FakeArrayAdapter,
) -> None:
    """Run shared source contract checks against one adapter through the registry."""

    token = CancellationToken()
    selected = registry.select_adapter(path, cancellation=token)
    assert selected.adapter is adapter
    assert selected.probe.adapter_id == adapter.adapter_id

    session = registry.open(path, cancellation=token)
    root = session.root()
    assert root.resource_id == ResourceId(path.resolve(strict=False).as_uri(), "/")

    page = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=1,
        cancellation=token,
    )
    assert page.next_cursor is None
    assert page.total_count == 1
    resource = page.items[0].resource_id

    metadata = session.get_metadata(resource, cancellation=token)
    assert metadata.shape == FAKE_VALUES.shape
    assert metadata.logical_size_bytes == FAKE_VALUES.nbytes

    progress_events: list[tuple[int, int | None, str]] = []
    result = session.read(
        ReadRequest(
            resource_id=resource,
            selection=SelectionSpec.slice(0, start=1, stop=2),
            scope=OperationScope.SLICE,
            max_bytes=FAKE_VALUES.nbytes,
        ),
        cancellation=token,
        progress=lambda done, total, message: progress_events.append(
            (done, total, message)
        ),
    )

    assert isinstance(result.payload, ArrayPayload)
    assert result.scope is OperationScope.SLICE
    assert result.bytes_read == result.payload.values.nbytes
    assert result.payload.source_coordinates((0, 1)) == (1, 1)
    assert progress_events == [(0, 1, "start"), (1, 1, "done")]

    cancelled = CancellationToken()
    cancelled.cancel()
    with pytest.raises(DataViewerError) as cancelled_error:
        session.read(
            ReadRequest(resource_id=resource),
            cancellation=cancelled,
            progress=lambda _done, _total, _message: None,
        )
    assert cancelled_error.value.code is ErrorCode.READ_CANCELLED

    with pytest.raises(DataViewerError) as missing_error:
        session.get_metadata(
            ResourceId(session.source_uri, "/missing"),
            cancellation=token,
        )
    assert missing_error.value.code is ErrorCode.RESOURCE_NOT_FOUND

    session.close()
    session.close()
    assert adapter.last_session is not None
    assert adapter.last_session.close_count == 1

    with pytest.raises(DataViewerError) as closed_error:
        session.root()
    assert closed_error.value.code is ErrorCode.SOURCE_CLOSED


def _fingerprint(path: Path) -> SourceFingerprint:
    stat = path.stat()
    return SourceFingerprint(
        size_bytes=stat.st_size,
        modified_time_ns=stat.st_mtime_ns,
    )


def _not_found(resource: ResourceId, *, operation: str) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.RESOURCE_NOT_FOUND,
        message="Fake resource was not found.",
        operation=operation,
        resource_id=resource,
    )


def _raise_read_cancelled_if_needed(
    cancellation: CancellationToken,
    *,
    operation: str,
) -> None:
    if cancellation.is_cancelled:
        raise DataViewerError(
            code=ErrorCode.READ_CANCELLED,
            message="Fake read was cancelled.",
            operation=operation,
            retryable=True,
        )
