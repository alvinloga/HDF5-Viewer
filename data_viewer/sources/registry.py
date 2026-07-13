"""Adapter registry, bounded probe arbitration, and session lifecycle wrappers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from data_viewer.domain import (
    DataMetadata,
    DataViewerError,
    ErrorCode,
    JsonValue,
    ReadResult,
    ResourceId,
    ResourceNode,
    SourceCapability,
    SourceFingerprint,
)

from .api import (
    DATASOURCE_API_VERSION,
    CancellationToken,
    NodePage,
    ProbeResult,
    ProgressCallback,
    ReadRequest,
    SourceAdapter,
    SourceSession,
)

DEFAULT_PROBE_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class SelectedAdapter:
    """Adapter selected by bounded probe arbitration."""

    adapter: SourceAdapter
    probe: ProbeResult


class SourceRegistry:
    """Registry of stateless source adapters."""

    def __init__(
        self,
        adapters: Sequence[SourceAdapter] = (),
        *,
        max_probe_bytes: int = DEFAULT_PROBE_BYTES,
        min_confidence: int = 1,
    ) -> None:
        if isinstance(max_probe_bytes, bool) or max_probe_bytes <= 0:
            raise ValueError("max_probe_bytes must be a positive integer")
        if isinstance(min_confidence, bool) or not 0 <= min_confidence <= 100:
            raise ValueError("min_confidence must be between 0 and 100")
        self._max_probe_bytes = max_probe_bytes
        self._min_confidence = min_confidence
        self._adapters: list[SourceAdapter] = []
        self._adapter_ids: set[str] = set()
        self._extensions: dict[str, str] = {}
        for adapter in adapters:
            self.register(adapter)

    @property
    def adapters(self) -> tuple[SourceAdapter, ...]:
        """Registered adapters in deterministic registration order."""

        return tuple(self._adapters)

    def register(self, adapter: SourceAdapter) -> None:
        """Register one adapter after validating public v1 identity."""

        adapter_id = _validate_adapter_id(adapter.adapter_id)
        if adapter_id in self._adapter_ids:
            raise _registry_error(
                message="Duplicate source adapter ID.",
                details={"duplicate_adapter_id": adapter_id},
            )
        if adapter.api_version != DATASOURCE_API_VERSION:
            raise DataViewerError(
                code=ErrorCode.SOURCE_UNSUPPORTED,
                message="Source adapter API version is unsupported.",
                operation="sources.register",
                details={
                    "adapter_id": adapter_id,
                    "api_version": adapter.api_version,
                    "required_api_version": DATASOURCE_API_VERSION,
                },
            )

        normalized_extensions = tuple(
            _normalize_extension(extension) for extension in adapter.extensions
        )
        if not normalized_extensions:
            raise ValueError("source adapter must declare at least one extension")
        if len(set(normalized_extensions)) != len(normalized_extensions):
            raise _registry_error(
                message="Adapter declares the same extension more than once.",
                details={"adapter_id": adapter_id},
            )
        for extension in normalized_extensions:
            existing = self._extensions.get(extension)
            if existing is not None:
                raise _registry_error(
                    message="Duplicate source adapter extension.",
                    details={
                        "duplicate_extension": extension,
                        "adapter_ids": _json_string_list(
                            sorted((existing, adapter_id))
                        ),
                    },
                )

        self._adapters.append(adapter)
        self._adapter_ids.add(adapter_id)
        for extension in normalized_extensions:
            self._extensions[extension] = adapter_id

    def select_adapter(
        self,
        path: Path,
        *,
        cancellation: CancellationToken,
    ) -> SelectedAdapter:
        """Run bounded probes and select exactly one adapter."""

        path = Path(path)
        _raise_if_cancelled(cancellation, operation="sources.probe")
        header = self._read_probe_header(path)
        results: list[SelectedAdapter] = []
        for adapter in self._probe_order(path):
            _raise_if_cancelled(cancellation, operation="sources.probe")
            try:
                probe = adapter.probe(path, header)
            except DataViewerError:
                raise
            except Exception as exc:
                raise DataViewerError(
                    code=ErrorCode.SOURCE_MALFORMED,
                    message="Source adapter probe failed.",
                    operation="sources.probe",
                    details={"adapter_id": adapter.adapter_id},
                    cause=exc,
                ) from exc
            if probe is None or probe.confidence < self._min_confidence:
                continue
            if probe.adapter_id != adapter.adapter_id:
                raise DataViewerError(
                    code=ErrorCode.SOURCE_MALFORMED,
                    message="Source adapter probe returned the wrong adapter ID.",
                    operation="sources.probe",
                    details={
                        "adapter_id": adapter.adapter_id,
                        "probe_adapter_id": probe.adapter_id,
                    },
                )
            results.append(SelectedAdapter(adapter=adapter, probe=probe))

        if not results:
            raise DataViewerError(
                code=ErrorCode.SOURCE_UNSUPPORTED,
                message="No registered source adapter accepts this input.",
                operation="sources.probe",
                details={
                    "path": str(path),
                    "extensions": _json_string_list(_path_suffixes(path)),
                    "adapter_ids": _json_string_list(
                        adapter.adapter_id for adapter in self._adapters
                    ),
                },
            )

        top_confidence = max(result.probe.confidence for result in results)
        top_results = [
            result for result in results if result.probe.confidence == top_confidence
        ]
        if len(top_results) > 1:
            formats = sorted({result.probe.detected_format for result in top_results})
            details: dict[str, JsonValue] = {
                "confidence": top_confidence,
                "adapter_ids": _json_string_list(
                    result.adapter.adapter_id for result in top_results
                ),
            }
            if len(formats) == 1:
                details["duplicate_format"] = formats[0]
            else:
                details["detected_formats"] = _json_string_list(formats)
            raise DataViewerError(
                code=ErrorCode.SOURCE_AMBIGUOUS,
                message="Multiple source adapters accept this input equally.",
                operation="sources.probe",
                details=details,
            )

        return top_results[0]

    def open(
        self,
        path: Path,
        *,
        cancellation: CancellationToken,
    ) -> "ManagedSourceSession":
        """Select an adapter and open a lifecycle-enforced session."""

        selected = self.select_adapter(path, cancellation=cancellation)
        _raise_if_cancelled(cancellation, operation="sources.open")
        try:
            session = selected.adapter.open(path, cancellation=cancellation)
        except DataViewerError:
            raise
        except Exception as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Source adapter could not open this input.",
                operation="sources.open",
                details={
                    "adapter_id": selected.adapter.adapter_id,
                    "detected_format": selected.probe.detected_format,
                },
                cause=exc,
            ) from exc
        return ManagedSourceSession(session)

    def _read_probe_header(self, path: Path) -> bytes:
        try:
            with path.open("rb") as source_file:
                return source_file.read(self._max_probe_bytes)
        except DataViewerError:
            raise
        except Exception as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Could not read source header.",
                operation="sources.probe",
                details={"path": str(path)},
                cause=exc,
            ) from exc

    def _probe_order(self, path: Path) -> tuple[SourceAdapter, ...]:
        matching_ids = set(_matching_adapter_ids(path, self._extensions))
        matching: list[SourceAdapter] = []
        remaining: list[SourceAdapter] = []
        for adapter in self._adapters:
            if adapter.adapter_id in matching_ids:
                matching.append(adapter)
            else:
                remaining.append(adapter)
        return tuple(matching + remaining)


class ManagedSourceSession:
    """Lifecycle guard around a SourceSession.

    The wrapper keeps session methods mutually exclusive with close(), so a close
    request waits for the current bounded source operation to return.
    """

    def __init__(self, inner: SourceSession) -> None:
        self._inner = inner
        self._source_uri = inner.source_uri
        self._fingerprint = inner.fingerprint
        self._capabilities = inner.capabilities
        self._closed = False
        self._lock = RLock()

    @property
    def source_uri(self) -> str:
        return self._source_uri

    @property
    def fingerprint(self) -> SourceFingerprint:
        return self._fingerprint

    @property
    def capabilities(self) -> SourceCapability:
        return self._capabilities

    @property
    def is_closed(self) -> bool:
        return self._closed

    def root(self) -> ResourceNode:
        with self._lock:
            self._ensure_open("source.root")
            return self._inner.root()

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: CancellationToken,
    ) -> NodePage:
        with self._lock:
            self._ensure_open("source.list_children")
            return self._inner.list_children(
                parent,
                cursor=cursor,
                page_size=page_size,
                cancellation=cancellation,
            )

    def get_metadata(
        self,
        resource: ResourceId,
        *,
        cancellation: CancellationToken,
    ) -> DataMetadata:
        with self._lock:
            self._ensure_open("source.get_metadata")
            return self._inner.get_metadata(resource, cancellation=cancellation)

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: CancellationToken,
        progress: ProgressCallback,
    ) -> ReadResult:
        with self._lock:
            self._ensure_open("source.read")
            return self._inner.read(
                request,
                cancellation=cancellation,
                progress=progress,
            )

    def search(
        self,
        query: str,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: CancellationToken,
    ) -> NodePage:
        with self._lock:
            self._ensure_open("source.search")
            return self._inner.search(
                query,
                cursor=cursor,
                page_size=page_size,
                cancellation=cancellation,
            )

    def refresh_fingerprint(self) -> SourceFingerprint:
        with self._lock:
            self._ensure_open("source.refresh_fingerprint")
            self._fingerprint = self._inner.refresh_fingerprint()
            return self._fingerprint

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._inner.close()

    def _ensure_open(self, operation: str) -> None:
        if self._closed:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CLOSED,
                message="Source session is closed.",
                operation=operation,
                details={"source_uri": self._source_uri},
            )


def _validate_adapter_id(adapter_id: str) -> str:
    if not isinstance(adapter_id, str) or not adapter_id:
        raise ValueError("source adapter ID must be a non-empty string")
    return adapter_id


def _normalize_extension(extension: str) -> str:
    if not isinstance(extension, str) or not extension.startswith("."):
        raise ValueError("source adapter extension must start with '.'")
    normalized = extension.lower()
    if normalized in {".", ".."}:
        raise ValueError("source adapter extension is invalid")
    return normalized


def _path_suffixes(path: Path) -> list[str]:
    name = path.name.lower()
    suffixes: list[str] = []
    for index, char in enumerate(name):
        if char == "." and index < len(name) - 1:
            suffixes.append(name[index:])
    return suffixes


def _matching_adapter_ids(
    path: Path,
    extension_to_adapter_id: dict[str, str],
) -> Iterable[str]:
    name = path.name.lower()
    for extension, adapter_id in extension_to_adapter_id.items():
        if name.endswith(extension):
            yield adapter_id


def _json_string_list(values: Iterable[str]) -> list[JsonValue]:
    return [value for value in values]


def _raise_if_cancelled(
    cancellation: CancellationToken,
    *,
    operation: str,
) -> None:
    if cancellation.is_cancelled:
        raise DataViewerError(
            code=ErrorCode.READ_CANCELLED,
            message="Source operation was cancelled.",
            operation=operation,
            retryable=True,
        )


def _registry_error(
    *,
    message: str,
    details: dict[str, JsonValue],
) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.SOURCE_AMBIGUOUS,
        message=message,
        operation="sources.register",
        details=details,
    )


__all__ = [
    "DEFAULT_PROBE_BYTES",
    "ManagedSourceSession",
    "SelectedAdapter",
    "SourceRegistry",
]
