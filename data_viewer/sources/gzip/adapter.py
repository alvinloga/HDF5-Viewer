"""Composable gzip source wrapper for stream-capable first-release formats."""

from __future__ import annotations

from dataclasses import replace
import gzip
import tempfile
from pathlib import Path
from typing import Iterable

from data_viewer.domain import (
    DataMetadata,
    DataViewerError,
    ErrorCode,
    ReadResult,
    ResourceId,
    ResourceNode,
    SourceCapability,
    SourceFingerprint,
)
from data_viewer.sources import api as source_api
from data_viewer.sources.api import (
    NodePage,
    ProbeResult,
    ReadRequest,
    SourceAdapter,
    SourceSession,
)

GZIP_MAGIC = b"\x1f\x8b"
DEFAULT_DECOMPRESSED_PROBE_BYTES = 1024 * 1024
DEFAULT_STREAM_DECOMPRESS_BYTES = 64 * 1024 * 1024
READ_ONLY_GZIP_WARNING = (
    "Read-only gzip wrapper; values were produced from a decompressed stream."
)


class GzipAdapter:
    """Generic `.gz` wrapper for stream-capable inner source adapters."""

    adapter_id = "data-viewer.gzip"
    api_version = source_api.DATASOURCE_API_VERSION

    def __init__(
        self,
        inner_adapters: Iterable[SourceAdapter],
        *,
        max_decompressed_probe_bytes: int = DEFAULT_DECOMPRESSED_PROBE_BYTES,
        max_stream_decompress_bytes: int = DEFAULT_STREAM_DECOMPRESS_BYTES,
    ) -> None:
        self._inner_by_extension: dict[str, SourceAdapter] = {}
        for adapter in inner_adapters:
            for extension in adapter.extensions:
                normalized = extension.lower()
                if normalized == ".nii":
                    continue
                self._inner_by_extension[normalized] = adapter
        self._extensions = tuple(
            f"{extension}.gz" for extension in sorted(self._inner_by_extension)
        )
        self._max_decompressed_probe_bytes = _positive(
            max_decompressed_probe_bytes,
            "max_decompressed_probe_bytes",
        )
        self._max_stream_decompress_bytes = _positive(
            max_stream_decompress_bytes,
            "max_stream_decompress_bytes",
        )

    @property
    def extensions(self) -> tuple[str, ...]:
        return self._extensions

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        inner = self._inner_for_path(path)
        if inner is None:
            return None
        if not header.startswith(GZIP_MAGIC):
            return None
        decompressed_prefix = _read_decompressed_prefix(
            path,
            max_bytes=self._max_decompressed_probe_bytes,
            operation="source.gzip.probe",
        )
        inner_probe = inner.probe(_inner_virtual_path(path), decompressed_prefix)
        if inner_probe is None:
            return None
        return ProbeResult(
            adapter_id=self.adapter_id,
            confidence=max(1, min(inner_probe.confidence, 90)),
            detected_format=f"gzip({inner_probe.detected_format})",
            reason=f"gzip framing is valid and inner {inner_probe.detected_format} probe accepted the decompressed prefix",
        )

    def open(
        self,
        path: Path,
        *,
        cancellation: source_api.CancellationToken,
    ) -> SourceSession:
        if cancellation.is_cancelled:
            raise DataViewerError(
                code=ErrorCode.READ_CANCELLED,
                message="Gzip open was cancelled.",
                operation="source.gzip.open",
                retryable=True,
            )
        inner = self._inner_for_path(path)
        if inner is None:
            raise DataViewerError(
                code=ErrorCode.SOURCE_UNSUPPORTED,
                message="No stream-capable gzip inner adapter accepts this extension.",
                operation="source.gzip.open",
                details={"path": str(path), "adapter_id": self.adapter_id},
            )
        temp_dir = tempfile.TemporaryDirectory(prefix="data-viewer-gzip-")
        temp_path = Path(temp_dir.name) / _inner_virtual_path(path).name
        try:
            _decompress_to_path(
                path,
                temp_path,
                max_bytes=self._max_stream_decompress_bytes,
                cancellation=cancellation,
            )
            inner_session = inner.open(temp_path, cancellation=cancellation)
            return _GzipWrappedSession(
                outer_path=path,
                temp_dir=temp_dir,
                inner_adapter_id=inner.adapter_id,
                inner_session=inner_session,
            )
        except Exception:
            temp_dir.cleanup()
            raise

    def _inner_for_path(self, path: Path) -> SourceAdapter | None:
        name = path.name.lower()
        if name.endswith(".nii.gz"):
            return None
        for extension, adapter in self._inner_by_extension.items():
            if name.endswith(f"{extension}.gz"):
                return adapter
        return None


class _GzipWrappedSession:
    """Lifecycle wrapper that hides the decompressed temporary inner path."""

    def __init__(
        self,
        *,
        outer_path: Path,
        temp_dir: tempfile.TemporaryDirectory[str],
        inner_adapter_id: str,
        inner_session: SourceSession,
    ) -> None:
        self._outer_path = outer_path
        self._outer_uri = outer_path.resolve(strict=False).as_uri()
        self._fingerprint = _fingerprint(outer_path)
        self._temp_dir = temp_dir
        self._inner_adapter_id = inner_adapter_id
        self._inner = inner_session
        self._inner_uri = inner_session.source_uri
        self._closed = False

    @property
    def source_uri(self) -> str:
        return self._outer_uri

    @property
    def fingerprint(self) -> SourceFingerprint:
        return self._fingerprint

    @property
    def capabilities(self) -> SourceCapability:
        return _read_only_capabilities(self._inner.capabilities)

    def root(self) -> ResourceNode:
        self._ensure_open("source.gzip.root")
        return self._outer_node(self._inner.root())

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: source_api.CancellationToken,
    ) -> NodePage:
        self._ensure_open("source.gzip.list_children")
        page = self._inner.list_children(
            self._inner_resource(parent),
            cursor=cursor,
            page_size=page_size,
            cancellation=cancellation,
        )
        return NodePage(
            items=tuple(self._outer_node(item) for item in page.items),
            next_cursor=page.next_cursor,
            total_count=page.total_count,
        )

    def get_metadata(
        self,
        resource: ResourceId,
        *,
        cancellation: source_api.CancellationToken,
    ) -> DataMetadata:
        self._ensure_open("source.gzip.get_metadata")
        metadata = self._inner.get_metadata(
            self._inner_resource(resource),
            cancellation=cancellation,
        )
        attributes = dict(metadata.attributes)
        attributes.update(
            {
                "gzip_wrapped": True,
                "inner_adapter_id": self._inner_adapter_id,
                "source_compression": "gzip",
                "gzip_access": "read_only_stream_wrapper",
            }
        )
        return replace(
            metadata,
            resource_id=self._outer_resource(metadata.resource_id),
            capabilities=_read_only_capabilities(metadata.capabilities),
            attributes=attributes,
        )

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: source_api.CancellationToken,
        progress: source_api.ProgressCallback,
    ) -> ReadResult:
        self._ensure_open("source.gzip.read")
        inner_request = replace(
            request,
            resource_id=self._inner_resource(request.resource_id),
        )
        result = self._inner.read(
            inner_request,
            cancellation=cancellation,
            progress=progress,
        )
        return replace(
            result,
            warnings=tuple(result.warnings) + (READ_ONLY_GZIP_WARNING,),
        )

    def search(
        self,
        query: str,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: source_api.CancellationToken,
    ) -> NodePage:
        self._ensure_open("source.gzip.search")
        page = self._inner.search(
            query,
            cursor=cursor,
            page_size=page_size,
            cancellation=cancellation,
        )
        return NodePage(
            items=tuple(self._outer_node(item) for item in page.items),
            next_cursor=page.next_cursor,
            total_count=page.total_count,
        )

    def refresh_fingerprint(self) -> SourceFingerprint:
        self._ensure_open("source.gzip.refresh_fingerprint")
        self._fingerprint = _fingerprint(self._outer_path)
        return self._fingerprint

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._inner.close()
        finally:
            self._temp_dir.cleanup()

    def _outer_node(self, node: ResourceNode) -> ResourceNode:
        return replace(node, resource_id=self._outer_resource(node.resource_id))

    def _outer_resource(self, resource: ResourceId) -> ResourceId:
        if resource.source_uri != self._inner_uri:
            return resource
        return ResourceId(self._outer_uri, resource.node_path)

    def _inner_resource(self, resource: ResourceId) -> ResourceId:
        if resource.source_uri != self._outer_uri:
            raise DataViewerError(
                code=ErrorCode.SOURCE_UNSUPPORTED,
                message="Resource does not belong to this gzip source.",
                operation="source.gzip.resource_map",
                details={"source_uri": resource.source_uri},
            )
        return ResourceId(self._inner_uri, resource.node_path)

    def _ensure_open(self, operation: str) -> None:
        if self._closed:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CLOSED,
                message="Gzip source session is closed.",
                operation=operation,
                details={"source_uri": self._outer_uri},
            )


def _inner_virtual_path(path: Path) -> Path:
    name = path.name
    if name.lower().endswith(".gz"):
        return path.with_name(name[:-3])
    return path


def _read_decompressed_prefix(path: Path, *, max_bytes: int, operation: str) -> bytes:
    try:
        with gzip.open(path, "rb") as handle:
            return handle.read(max_bytes)
    except (EOFError, OSError, gzip.BadGzipFile) as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="Gzip source is corrupt or truncated.",
            operation=operation,
            details={"path": str(path), "adapter_id": GzipAdapter.adapter_id},
            cause=exc,
        ) from exc


def _decompress_to_path(
    source: Path,
    target: Path,
    *,
    max_bytes: int,
    cancellation: source_api.CancellationToken,
) -> None:
    try:
        with gzip.open(source, "rb") as source_file, target.open("wb") as target_file:
            copied = 0
            while True:
                if cancellation.is_cancelled:
                    raise DataViewerError(
                        code=ErrorCode.READ_CANCELLED,
                        message="Gzip decompression was cancelled.",
                        operation="source.gzip.decompress",
                        retryable=True,
                    )
                chunk = source_file.read(1024 * 1024)
                if not chunk:
                    break
                copied += len(chunk)
                if copied > max_bytes:
                    raise DataViewerError(
                        code=ErrorCode.BUDGET_EXCEEDED,
                        message="Gzip decompressed stream exceeds the configured DV-0501 stream budget.",
                        operation="source.gzip.decompress",
                        details={"max_bytes": max_bytes, "path": str(source)},
                    )
                target_file.write(chunk)
    except DataViewerError:
        raise
    except (EOFError, OSError, gzip.BadGzipFile) as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="Gzip source is corrupt or truncated.",
            operation="source.gzip.decompress",
            details={"path": str(source), "adapter_id": GzipAdapter.adapter_id},
            cause=exc,
        ) from exc


def _read_only_capabilities(capabilities: SourceCapability) -> SourceCapability:
    return capabilities & ~(
        SourceCapability.EDIT_PATCH | SourceCapability.ATOMIC_REWRITE
    )


def _fingerprint(path: Path) -> SourceFingerprint:
    stat = path.stat()
    return SourceFingerprint(
        size_bytes=stat.st_size,
        modified_time_ns=stat.st_mtime_ns,
        content_tag=f"gzip:{stat.st_size}:{stat.st_mtime_ns}",
    )


def _positive(value: int, label: str) -> int:
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


__all__ = ["GzipAdapter"]
