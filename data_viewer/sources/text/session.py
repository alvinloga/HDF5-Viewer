"""Session implementation for TXT text and explicit table modes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from data_viewer.domain import (
    DataDomain,
    DataMetadata,
    DataViewerError,
    ErrorCode,
    NodeKind,
    OperationScope,
    ReadResult,
    ResourceId,
    ResourceNode,
    SourceCapability,
    SourceFingerprint,
)
from data_viewer.domain.payload import TextPayload
from data_viewer.editing import ChangeSet, EditPatch, TextPatch, fingerprint_value
from data_viewer.editing.review import SaveStrategy
from data_viewer.persistence.transaction import AtomicReplacementService
from data_viewer.sources.api import NodePage, ProgressCallback, ReadRequest
from data_viewer.sources.delimited import DelimitedTextOptions
from data_viewer.sources.delimited.session import DelimitedSourceSession
from data_viewer.tasks import CancellationToken as TaskCancellationToken

TEXT_NODE_PATH = "/text"
DEFAULT_TEXT_PAGE_CHARS = 4096


class TextMode(StrEnum):
    """Confirmed TXT interpretation mode."""

    TEXT = "text"
    TABLE = "table"


@dataclass(frozen=True, slots=True)
class TextPersistenceResult:
    """Result of applying text patches through full replacement."""

    strategy: SaveStrategy
    source_fingerprint: SourceFingerprint
    changed_ranges: int
    warnings: tuple[str, ...] = ()


class TextSourceSession:
    """One owned TXT session; table mode is explicit and never inferred."""

    def __init__(
        self,
        path: Path,
        *,
        mode: TextMode = TextMode.TEXT,
        table_options: DelimitedTextOptions | None = None,
    ) -> None:
        self._path = path
        self._source_uri = path.resolve(strict=False).as_uri()
        self._closed = False
        self._fingerprint = _fingerprint(path)
        self._encoding = _detect_encoding(path)
        self._mode = TextMode(mode)
        self._table_session: DelimitedSourceSession | None = None
        if self._mode is TextMode.TABLE:
            if table_options is None:
                raise ValueError("table mode requires explicit DelimitedTextOptions")
            self._table_session = DelimitedSourceSession(path, options=table_options)

    @property
    def source_uri(self) -> str:
        return self._source_uri

    @property
    def fingerprint(self) -> SourceFingerprint:
        return self._fingerprint

    @property
    def capabilities(self) -> SourceCapability:
        if self._table_session is not None:
            return self._table_session.capabilities
        return (
            SourceCapability.HIERARCHY
            | SourceCapability.STREAMING_READ
            | SourceCapability.SEARCH
            | SourceCapability.EDIT_PATCH
            | SourceCapability.ATOMIC_REWRITE
            | SourceCapability.SAVE_AS
        )

    def root(self) -> ResourceNode:
        self._ensure_open(operation="source.txt.root")
        if self._table_session is not None:
            return self._table_session.root()
        return ResourceNode(
            resource_id=ResourceId(self._source_uri, "/"),
            name=self._path.name,
            node_kind=NodeKind.ROOT,
            domain=DataDomain.TEXT,
            has_children=True,
            summary=f"TXT text source {self._path.name}",
        )

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: object,
    ) -> NodePage:
        self._ensure_open(operation="source.txt.list_children")
        if self._table_session is not None:
            return self._table_session.list_children(
                parent,
                cursor=cursor,
                page_size=page_size,
                cancellation=cancellation,
            )
        _raise_if_cancelled(cancellation, operation="source.txt.list_children")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        if parent != ResourceId(self._source_uri, "/"):
            raise _resource_not_found(parent, operation="source.txt.list_children")
        try:
            start = int(cursor or 0)
        except ValueError as exc:
            raise ValueError("cursor must be a non-negative integer string") from exc
        children = (self._text_node(),)
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
        cancellation: object,
    ) -> DataMetadata:
        self._ensure_open(operation="source.txt.get_metadata")
        if self._table_session is not None:
            metadata = self._table_session.get_metadata(resource, cancellation=cancellation)
            attributes = dict(metadata.attributes)
            attributes["mode"] = TextMode.TABLE.value
            return DataMetadata(
                resource_id=metadata.resource_id,
                name=metadata.name,
                domain=metadata.domain,
                node_kind=metadata.node_kind,
                shape=metadata.shape,
                dtype=metadata.dtype,
                logical_size_bytes=metadata.logical_size_bytes,
                storage_size_bytes=metadata.storage_size_bytes,
                capabilities=metadata.capabilities,
                attributes=attributes,
                columns=metadata.columns,
                spatial=metadata.spatial,
            )
        _raise_if_cancelled(cancellation, operation="source.txt.get_metadata")
        if resource.source_uri != self._source_uri:
            raise _resource_not_found(resource, operation="source.txt.get_metadata")
        if resource.node_path == "/":
            return DataMetadata(
                resource_id=resource,
                name=self._path.name,
                domain=DataDomain.TEXT,
                node_kind=NodeKind.ROOT,
                shape=(self._path.stat().st_size,),
                dtype="text",
                storage_size_bytes=self._path.stat().st_size,
                capabilities=self.capabilities,
                attributes=self._metadata_attributes(root=True),
            )
        if resource.node_path != TEXT_NODE_PATH:
            raise _resource_not_found(resource, operation="source.txt.get_metadata")
        return DataMetadata(
            resource_id=resource,
            name="text",
            domain=DataDomain.TEXT,
            node_kind=NodeKind.RESOURCE,
            shape=(self._path.stat().st_size,),
            dtype="text",
            storage_size_bytes=self._path.stat().st_size,
            capabilities=(
                SourceCapability.STREAMING_READ
                | SourceCapability.SEARCH
                | SourceCapability.EDIT_PATCH
                | SourceCapability.ATOMIC_REWRITE
                | SourceCapability.SAVE_AS
            ),
            attributes=self._metadata_attributes(root=False),
        )

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: object,
        progress: ProgressCallback,
    ) -> ReadResult:
        self._ensure_open(operation="source.txt.read")
        if self._table_session is not None:
            return self._table_session.read(
                request,
                cancellation=cancellation,
                progress=progress,
            )
        _raise_if_cancelled(cancellation, operation="source.txt.read")
        if request.resource_id != ResourceId(self._source_uri, TEXT_NODE_PATH):
            raise _resource_not_found(request.resource_id, operation="source.txt.read")
        if request.scope not in {OperationScope.PAGE, OperationScope.FULL}:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="TXT reads support PAGE or FULL scope only.",
                operation="source.txt.read",
                resource_id=request.resource_id,
                details={"scope": request.scope.value},
            )
        progress(0, 1, "start")
        text = self._read_all_text()
        offset = request.row_offset or 0
        if offset < 0:
            raise ValueError("row_offset must be non-negative")
        if request.scope is OperationScope.FULL and request.row_limit is None:
            if len(text.encode(self._encoding)) > request.max_bytes:
                raise DataViewerError(
                    code=ErrorCode.BUDGET_EXCEEDED,
                    message="Full TXT read exceeds the requested read budget.",
                    operation="source.txt.read",
                    resource_id=request.resource_id,
                )
            chunk = text[offset:]
        else:
            limit = request.row_limit or DEFAULT_TEXT_PAGE_CHARS
            chunk = text[offset : offset + limit]
        encoded_bytes = len(chunk.encode(self._encoding))
        if encoded_bytes > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="TXT page exceeds the requested read budget.",
                operation="source.txt.read",
                resource_id=request.resource_id,
                details={"bytes_read": encoded_bytes, "max_bytes": request.max_bytes},
            )
        progress(1, 1, "done")
        return ReadResult(
            payload=TextPayload(
                text=chunk,
                offset=offset,
                is_complete=offset + len(chunk) >= len(text),
            ),
            scope=request.scope,
            bytes_read=encoded_bytes,
            is_sampled=False,
            sample=request.sample,
        )

    def search(
        self,
        query: str,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: object,
    ) -> NodePage:
        self._ensure_open(operation="source.txt.search")
        if self._table_session is not None:
            return self._table_session.search(
                query,
                cursor=cursor,
                page_size=page_size,
                cancellation=cancellation,
            )
        _raise_if_cancelled(cancellation, operation="source.txt.search")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        normalized = query.strip().lower()
        nodes = [self._text_node()] if normalized and "text".startswith(normalized) else []
        return NodePage(items=tuple(nodes), next_cursor=None, total_count=len(nodes))

    def refresh_fingerprint(self) -> SourceFingerprint:
        self._ensure_open(operation="source.txt.refresh_fingerprint")
        self._fingerprint = _fingerprint(self._path)
        return self._fingerprint

    def apply_change_set(
        self,
        changeset: ChangeSet,
        *,
        cancellation: object,
        replacement_service: AtomicReplacementService | None = None,
        failure_injector: Any | None = None,
    ) -> TextPersistenceResult | object:
        self._ensure_open(operation="source.txt.apply_change_set")
        if self._table_session is not None:
            return self._table_session.apply_change_set(
                changeset,
                cancellation=cancellation,
                replacement_service=replacement_service,
                failure_injector=failure_injector,
            )
        _raise_if_cancelled(cancellation, operation="source.txt.apply_change_set")
        _validate_changeset_source(changeset, source_uri=self._source_uri)
        if changeset.is_clean:
            raise ValueError("changeset must contain at least one patch")
        self._assert_unchanged(changeset.source_fingerprint)
        patches = _text_patches(changeset.patches)
        original = self._path.read_bytes()
        patched = _apply_text_patches(original, patches, encoding=self._encoding)
        service = replacement_service or AtomicReplacementService()
        token = cancellation if isinstance(cancellation, TaskCancellationToken) else None

        def write_payload(temp_path: Path) -> None:
            temp_path.write_bytes(patched)

        def validate_payload(candidate: Path) -> SourceFingerprint:
            _validate_text_candidate(candidate, patches, encoding=self._encoding)
            return _fingerprint(candidate)

        result = service.run_replacement(
            self._path,
            self._path,
            write_payload=write_payload,
            validate_payload=validate_payload,
            expected_source_fingerprint=changeset.source_fingerprint,
            estimated_output_bytes=max(self._path.stat().st_size, len(patched)),
            cancellation=token,
            failure_injector=failure_injector,
        )
        self._fingerprint = result.destination_fingerprint
        return TextPersistenceResult(
            strategy=SaveStrategy.REPLACEMENT,
            source_fingerprint=self._fingerprint,
            changed_ranges=len(patches),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._table_session is not None:
            self._table_session.close()

    def _text_node(self) -> ResourceNode:
        return ResourceNode(
            resource_id=ResourceId(self._source_uri, TEXT_NODE_PATH),
            name="text",
            node_kind=NodeKind.RESOURCE,
            domain=DataDomain.TEXT,
            has_children=False,
            summary=f"text bytes={self._path.stat().st_size}",
        )

    def _metadata_attributes(self, *, root: bool) -> dict[str, Any]:
        return {
            "format": "TXT",
            "mode": TextMode.TEXT.value,
            "encoding": self._encoding,
            "source_fingerprint": self._fingerprint.to_json(),
            "synthetic_root": root,
        }

    def _read_all_text(self) -> str:
        try:
            return self._path.read_text(encoding=self._encoding)
        except UnicodeDecodeError as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="TXT source cannot be decoded with the confirmed encoding.",
                operation="source.txt.read_text",
                details={
                    "path": str(self._path),
                    "encoding": self._encoding,
                    "replacement_characters": False,
                },
                cause=exc,
            ) from exc

    def _ensure_open(self, operation: str) -> None:
        if self._closed:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CLOSED,
                message="TXT source session is closed.",
                operation=operation,
                details={"source_uri": self._source_uri},
            )

    def _assert_unchanged(self, expected: SourceFingerprint) -> None:
        current = _fingerprint(self._path)
        if current != expected or self._fingerprint != expected:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CHANGED,
                message="TXT source changed before save; refusing to overwrite.",
                operation="source.txt.apply_change_set",
                details={
                    "expected_fingerprint": expected.to_json(),
                    "observed_fingerprint": current.to_json(),
                    "session_fingerprint": self._fingerprint.to_json(),
                },
                retryable=True,
            )


def _detect_encoding(path: Path) -> str:
    try:
        prefix = path.read_bytes()[:3]
    except OSError as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Unable to read TXT source.",
            operation="source.txt.detect_encoding",
            details={"path": str(path)},
            cause=exc,
        ) from exc
    encoding = "utf-8-sig" if prefix.startswith(b"\xef\xbb\xbf") else "utf-8"
    try:
        path.read_text(encoding=encoding)
    except UnicodeDecodeError as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="TXT source cannot be decoded with strict UTF-8.",
            operation="source.txt.detect_encoding",
            details={
                "path": str(path),
                "encoding": encoding,
                "replacement_characters": False,
            },
            cause=exc,
        ) from exc
    return encoding


def _apply_text_patches(
    original: bytes,
    patches: tuple[TextPatch, ...],
    *,
    encoding: str,
) -> bytes:
    output = bytearray()
    cursor = 0
    for patch in sorted(patches, key=lambda item: item.start_offset):
        if patch.start_offset < cursor:
            raise DataViewerError(
                code=ErrorCode.SELECTION_INVALID,
                message="TXT text patches must not overlap.",
                operation="source.txt.apply_text_patches",
                resource_id=patch.resource_id,
            )
        if patch.end_offset > len(original):
            raise DataViewerError(
                code=ErrorCode.SELECTION_INVALID,
                message="TXT text patch is outside the original byte range.",
                operation="source.txt.apply_text_patches",
                resource_id=patch.resource_id,
            )
        old_text = original[patch.start_offset : patch.end_offset].decode(
            encoding,
            errors="strict",
        )
        if fingerprint_value(old_text) != patch.old_text_fingerprint:
            raise DataViewerError(
                code=ErrorCode.EDIT_CONFLICT,
                message="TXT text patch old value no longer matches the source.",
                operation="source.txt.apply_text_patches",
                resource_id=patch.resource_id,
            )
        output.extend(original[cursor : patch.start_offset])
        output.extend(patch.replacement.encode(encoding, errors="strict"))
        cursor = patch.end_offset
    output.extend(original[cursor:])
    return bytes(output)


def _validate_text_candidate(
    candidate: Path,
    patches: tuple[TextPatch, ...],
    *,
    encoding: str,
) -> None:
    text = candidate.read_text(encoding=encoding)
    for patch in patches:
        if patch.replacement not in text:
            raise DataViewerError(
                code=ErrorCode.READ_FAILED,
                message="TXT replacement validation did not find patched text.",
                operation="source.txt.validate_payload",
                resource_id=patch.resource_id,
            )


def _text_patches(patches: tuple[EditPatch, ...]) -> tuple[TextPatch, ...]:
    converted: list[TextPatch] = []
    for patch in patches:
        if not isinstance(patch, TextPatch):
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="TXT persistence supports text patches only in text mode.",
                operation="source.txt.text_patches",
                resource_id=patch.resource_id,
                details={"patch_type": type(patch).__name__},
            )
        if patch.resource_id.node_path != TEXT_NODE_PATH:
            raise _resource_not_found(patch.resource_id, operation="source.txt.text_patches")
        converted.append(patch)
    return tuple(converted)


def _validate_changeset_source(changeset: ChangeSet, *, source_uri: str) -> None:
    for patch in changeset.patches:
        if patch.resource_id.source_uri != source_uri:
            raise DataViewerError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="TXT changeset targets a different source.",
                operation="source.txt.apply_change_set",
                resource_id=patch.resource_id,
                details={"expected_source_uri": source_uri},
            )


def _fingerprint(path: Path) -> SourceFingerprint:
    try:
        stat = path.stat()
    except OSError as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Unable to stat TXT source.",
            operation="source.txt.fingerprint",
            details={"path": str(path)},
            cause=exc,
        ) from exc
    return SourceFingerprint(size_bytes=stat.st_size, modified_time_ns=stat.st_mtime_ns)


def _resource_not_found(resource_id: ResourceId, *, operation: str) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.RESOURCE_NOT_FOUND,
        message="Requested TXT resource was not found.",
        operation=operation,
        resource_id=resource_id,
        details={"resource_id": resource_id.to_json()},
    )


def _raise_if_cancelled(cancellation: object, *, operation: str) -> None:
    if getattr(cancellation, "is_cancelled", False):
        raise DataViewerError(
            code=ErrorCode.READ_CANCELLED,
            message="TXT source operation was cancelled.",
            operation=operation,
            retryable=True,
        )


__all__ = ["TextMode", "TextPersistenceResult", "TextSourceSession"]
