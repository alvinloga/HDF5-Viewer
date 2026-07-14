"""Session implementation for NumPy ``.npz`` archive resources in Data Viewer v1."""

from __future__ import annotations

import io
import posixpath
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np

from data_viewer.domain import (
    ArrayPayload,
    DataDomain,
    DataMetadata,
    DataViewerError,
    ErrorCode,
    JsonValue,
    NodeKind,
    NormalizedSelection,
    OperationScope,
    ReadResult,
    ResourceId,
    ResourceNode,
    SourceCapability,
    SourceFingerprint,
)
from data_viewer.editing import CellPatch, ChangeSet, EditPatch, fingerprint_value
from data_viewer.editing.review import SaveStrategy
from data_viewer.persistence.transaction import AtomicReplacementService
from data_viewer.sources.api import NodePage, ProgressCallback, ReadRequest
from data_viewer.tasks import CancellationToken as TaskCancellationToken

MAX_ARCHIVE_ENTRIES = 10_000
MAX_MEMBER_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1_000

type NPZPersistenceFailureInjector = Callable[[Any], None]


@dataclass(frozen=True, slots=True)
class NPZMember:
    """Validated metadata for one NPZ array member."""

    archive_name: str
    node_path: str
    display_name: str
    shape: tuple[int, ...]
    dtype: np.dtype[Any]
    fortran_order: bool
    logical_size_bytes: int
    compressed_size_bytes: int


@dataclass(frozen=True, slots=True)
class NPZPersistenceResult:
    """Result of applying one NPZ changeset through archive rebuild."""

    strategy: SaveStrategy
    source_fingerprint: SourceFingerprint
    changed_coordinates: int
    warnings: tuple[str, ...] = ()


class NPZSourceSession:
    """One owned NPZ archive session with a synthetic resource hierarchy."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._source_uri = path.resolve(strict=False).as_uri()
        self._closed = False
        self._fingerprint = _fingerprint(path)
        self._archive: zipfile.ZipFile | None = None
        self._members: dict[str, NPZMember] = {}
        self._containers: frozenset[str] = frozenset()
        self._open_archive()

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
            | SourceCapability.EDIT_PATCH
            | SourceCapability.ATOMIC_REWRITE
            | SourceCapability.SAVE_AS
        )

    def root(self) -> ResourceNode:
        self._ensure_open(operation="source.npz.root")
        return ResourceNode(
            resource_id=ResourceId(self._source_uri, "/"),
            name=self._path.name,
            node_kind=NodeKind.ROOT,
            domain=DataDomain.HIERARCHICAL_ARRAY,
            has_children=True,
            summary=f"NPZ archive source {self._path.name}",
        )

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: object,
    ) -> NodePage:
        self._ensure_open(operation="source.npz.list_children")
        _raise_if_cancelled(cancellation, operation="source.npz.list_children")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        if parent.source_uri != self._source_uri:
            raise _resource_not_found(parent, operation="source.npz.list_children")
        if parent.node_path != "/" and parent.node_path not in self._containers:
            raise _resource_not_found(parent, operation="source.npz.list_children")

        try:
            start = int(cursor or 0)
        except ValueError as exc:
            raise ValueError("cursor must be a non-negative integer string") from exc
        if start < 0:
            raise ValueError("cursor must be a non-negative integer")

        children = tuple(self._children_for(parent.node_path))
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
        self._ensure_open(operation="source.npz.get_metadata")
        _raise_if_cancelled(cancellation, operation="source.npz.get_metadata")
        if resource.source_uri != self._source_uri:
            raise _resource_not_found(resource, operation="source.npz.get_metadata")
        if resource.node_path == "/":
            return DataMetadata(
                resource_id=resource,
                name=self._path.name,
                domain=DataDomain.HIERARCHICAL_ARRAY,
                node_kind=NodeKind.ROOT,
                shape=(),
                capabilities=self.capabilities,
                storage_size_bytes=self._path.stat().st_size,
                attributes={
                    "format": "NPZ",
                    "source_fingerprint": self._fingerprint.to_json(),
                    "synthetic_root": True,
                    "member_count": len(self._members),
                },
            )
        if resource.node_path in self._containers:
            return DataMetadata(
                resource_id=resource,
                name=resource.node_path.rsplit("/", 1)[-1],
                domain=DataDomain.HIERARCHICAL_ARRAY,
                node_kind=NodeKind.CONTAINER,
                shape=(),
                capabilities=SourceCapability.HIERARCHY | SourceCapability.SEARCH,
                storage_size_bytes=self._path.stat().st_size,
                attributes={
                    "format": "NPZ",
                    "source_fingerprint": self._fingerprint.to_json(),
                    "synthetic_container": True,
                },
            )
        member = self._member_for(resource, operation="source.npz.get_metadata")
        return DataMetadata(
            resource_id=resource,
            name=member.display_name,
            domain=DataDomain.ARRAY,
            node_kind=NodeKind.RESOURCE,
            shape=member.shape,
            dtype=str(member.dtype),
            logical_size_bytes=member.logical_size_bytes,
            storage_size_bytes=self._path.stat().st_size,
            capabilities=(
                SourceCapability.RANDOM_SLICE
                | SourceCapability.SEARCH
                | SourceCapability.EDIT_PATCH
                | SourceCapability.ATOMIC_REWRITE
                | SourceCapability.SAVE_AS
            ),
            attributes=_array_attributes(member, self._fingerprint),
        )

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: object,
        progress: ProgressCallback,
    ) -> ReadResult:
        self._ensure_open(operation="source.npz.read")
        _raise_if_cancelled(cancellation, operation="source.npz.read")
        member = self._member_for(request.resource_id, operation="source.npz.read")
        if request.row_offset is not None or request.row_limit is not None:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="row-based reads are not supported for NPZ arrays.",
                operation="source.npz.read",
                resource_id=request.resource_id,
            )
        if request.selected_columns:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="column-based reads are not supported for NPZ arrays.",
                operation="source.npz.read",
                resource_id=request.resource_id,
            )
        if request.scope not in {OperationScope.SLICE, OperationScope.FULL}:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="Unsupported NPZ read scope.",
                operation="source.npz.read",
                resource_id=request.resource_id,
                details={"scope": request.scope.value},
            )

        normalized = request.selection.normalize(member.shape)
        if not normalized.ok:
            raise DataViewerError(
                code=ErrorCode.SELECTION_INVALID,
                message="Selection is invalid for this NPZ array shape.",
                operation="source.npz.read",
                resource_id=request.resource_id,
                details={"errors": [error.to_json() for error in normalized.errors]},
            )
        selection = normalized.unwrap()
        estimated_bytes = _estimate_nbytes(member.dtype, selection)
        if estimated_bytes > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Requested NPZ selection exceeds read budget.",
                operation="source.npz.read",
                resource_id=request.resource_id,
                details={
                    "estimated_bytes": estimated_bytes,
                    "max_bytes": request.max_bytes,
                },
            )

        progress(0, 1, "start")
        array = self._load_member_array(member, operation="source.npz.read")
        try:
            values = _read_array_values(array, selection)
        finally:
            del array
        _raise_if_cancelled(cancellation, operation="source.npz.read")
        progress(1, 1, "done")

        if values.nbytes > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Read NPZ payload exceeds configured budget.",
                operation="source.npz.read",
                resource_id=request.resource_id,
                details={
                    "bytes_read": int(values.nbytes),
                    "max_bytes": request.max_bytes,
                },
            )

        return ReadResult(
            payload=ArrayPayload(
                values=values,
                original_shape=member.shape,
                selection=selection,
            ),
            scope=request.scope,
            bytes_read=int(values.nbytes),
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
        self._ensure_open(operation="source.npz.search")
        _raise_if_cancelled(cancellation, operation="source.npz.search")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        normalized_query = query.strip().lower()
        if not normalized_query:
            return NodePage(items=(), next_cursor=None, total_count=0)

        nodes = [
            self._node_for_path(path)
            for path in sorted((*self._containers, *self._members))
            if normalized_query in path.lower()
        ]
        try:
            start = int(cursor or 0)
        except ValueError as exc:
            raise ValueError("cursor must be a non-negative integer string") from exc
        if start < 0:
            raise ValueError("cursor must be a non-negative integer")
        stop = min(start + page_size, len(nodes))
        return NodePage(
            items=tuple(nodes[start:stop]),
            next_cursor=str(stop) if stop < len(nodes) else None,
            total_count=len(nodes),
        )

    def refresh_fingerprint(self) -> SourceFingerprint:
        self._ensure_open(operation="source.npz.refresh_fingerprint")
        self._fingerprint = _fingerprint(self._path)
        return self._fingerprint

    def apply_change_set(
        self,
        changeset: ChangeSet,
        *,
        cancellation: object,
        replacement_service: AtomicReplacementService | None = None,
        failure_injector: NPZPersistenceFailureInjector | None = None,
    ) -> NPZPersistenceResult:
        """Apply one reviewed changeset by rebuilding the NPZ archive."""

        self._ensure_open(operation="source.npz.apply_change_set")
        _raise_if_cancelled(cancellation, operation="source.npz.apply_change_set")
        _validate_changeset_source(changeset, source_uri=self._source_uri)
        if changeset.is_clean:
            raise ValueError("changeset must contain at least one patch")
        self._assert_unchanged(changeset.source_fingerprint)

        patches_by_node = _group_cell_patches(changeset.patches)
        source_arrays: dict[str, np.ndarray[Any, np.dtype[np.generic]]] = {}
        patched_arrays: dict[str, np.ndarray[Any, np.dtype[np.generic]]] = {}
        for node_path, patches in patches_by_node.items():
            member = self._members.get(node_path)
            if member is None:
                raise _resource_not_found(
                    ResourceId(self._source_uri, node_path),
                    operation="source.npz.apply_change_set",
                )
            source_values = self._load_member_array(
                member,
                operation="source.npz.apply_change_set",
            )
            patched_values = np.array(source_values, copy=True, order="K")
            _verify_old_values(source_values, tuple(patches), operation="source.npz.verify_old_values")
            _apply_numpy_patches(patched_values, tuple(patches))
            source_arrays[node_path] = source_values
            patched_arrays[node_path] = patched_values

        self._close_archive()
        service = replacement_service or AtomicReplacementService()
        token = cancellation if isinstance(cancellation, TaskCancellationToken) else None
        original_members = tuple(self._members.values())
        estimated_bytes = max(
            self._path.stat().st_size,
            sum(member.logical_size_bytes for member in original_members),
        )

        def write_payload(temp_path: Path) -> None:
            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for member in original_members:
                    array = patched_arrays.get(member.node_path)
                    if array is None:
                        array = self._load_member_array_from_path(
                            self._path,
                            member,
                            operation="source.npz.write_payload",
                        )
                    payload = io.BytesIO()
                    np.save(payload, array, allow_pickle=False)
                    archive.writestr(member.archive_name, payload.getvalue())

        def validate_payload(candidate: Path) -> SourceFingerprint:
            candidate_members = _inspect_archive(candidate)
            _validate_candidate_members(
                candidate,
                candidate_members,
                expected_members=original_members,
                patched_arrays=patched_arrays,
                source_arrays=source_arrays,
                patches=changeset.patches,
            )
            return _fingerprint(candidate)

        try:
            result = service.run_replacement(
                self._path,
                self._path,
                write_payload=write_payload,
                validate_payload=validate_payload,
                expected_source_fingerprint=changeset.source_fingerprint,
                estimated_output_bytes=estimated_bytes,
                cancellation=token,
                failure_injector=failure_injector,
            )
        finally:
            if self._archive is None and self._path.exists():
                self._open_archive()

        self._fingerprint = result.destination_fingerprint
        self._close_archive()
        self._open_archive()
        return NPZPersistenceResult(
            strategy=SaveStrategy.REPLACEMENT,
            source_fingerprint=self._fingerprint,
            changed_coordinates=_count_cell_patches(changeset.patches),
            warnings=(
                "NPZ archive rebuilt; unaffected members were preserved by decoded array semantics.",
            ),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._close_archive()

    def _open_archive(self) -> None:
        try:
            self._archive = zipfile.ZipFile(self._path, "r")
            members = _inspect_open_archive(self._archive, self._path)
        except DataViewerError:
            self._close_archive()
            raise
        except zipfile.BadZipFile as exc:
            self._close_archive()
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="NPZ source is not a valid ZIP archive.",
                operation="source.npz.open",
                details={"path": str(self._path)},
                cause=exc,
            ) from exc
        except OSError as exc:
            self._close_archive()
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Unable to open NPZ source.",
                operation="source.npz.open",
                details={"path": str(self._path)},
                cause=exc,
            ) from exc
        self._members = {member.node_path: member for member in members}
        self._containers = _derive_containers(tuple(self._members))

    def _close_archive(self) -> None:
        if self._archive is None:
            return
        self._archive.close()
        self._archive = None

    def _ensure_open(self, operation: str) -> None:
        if self._closed:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CLOSED,
                message="NPZ source session is closed.",
                operation=operation,
                details={"source_uri": self._source_uri},
            )
        if self._archive is None:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="NPZ archive handle is unavailable.",
                operation=operation,
                details={"source_uri": self._source_uri},
            )

    def _member_for(self, resource: ResourceId, *, operation: str) -> NPZMember:
        if resource.source_uri != self._source_uri:
            raise _resource_not_found(resource, operation=operation)
        member = self._members.get(resource.node_path)
        if member is None:
            raise _resource_not_found(resource, operation=operation)
        return member

    def _children_for(self, parent_path: str) -> list[ResourceNode]:
        prefix = "" if parent_path == "/" else parent_path.strip("/")
        names: dict[str, str] = {}
        for node_path in (*self._containers, *self._members):
            stripped = node_path.strip("/")
            if prefix:
                if not stripped.startswith(prefix + "/"):
                    continue
                remainder = stripped[len(prefix) + 1 :]
            else:
                remainder = stripped
            if not remainder:
                continue
            segment = remainder.split("/", 1)[0]
            child_path = f"/{segment}" if not prefix else f"/{prefix}/{segment}"
            names[segment] = child_path
        return [self._node_for_path(path) for _, path in sorted(names.items())]

    def _node_for_path(self, node_path: str) -> ResourceNode:
        if node_path in self._members:
            member = self._members[node_path]
            return ResourceNode(
                resource_id=ResourceId(self._source_uri, member.node_path),
                name=member.display_name,
                node_kind=NodeKind.RESOURCE,
                domain=DataDomain.ARRAY,
                has_children=False,
                summary=f"array shape={member.shape} dtype={member.dtype}",
            )
        return ResourceNode(
            resource_id=ResourceId(self._source_uri, node_path),
            name=node_path.rsplit("/", 1)[-1],
            node_kind=NodeKind.CONTAINER,
            domain=DataDomain.HIERARCHICAL_ARRAY,
            has_children=True,
            summary="synthetic NPZ member group",
        )

    def _load_member_array(
        self,
        member: NPZMember,
        *,
        operation: str,
    ) -> np.ndarray[Any, np.dtype[np.generic]]:
        if self._archive is None:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="NPZ archive handle is unavailable.",
                operation=operation,
                details={"source_uri": self._source_uri},
            )
        try:
            with self._archive.open(member.archive_name, "r") as handle:
                payload = _read_member_payload(handle, member, operation=operation)
        except KeyError as exc:
            raise _resource_not_found(
                ResourceId(self._source_uri, member.node_path),
                operation=operation,
            ) from exc
        return _load_npy_payload(payload, member, operation=operation)

    @staticmethod
    def _load_member_array_from_path(
        path: Path,
        member: NPZMember,
        *,
        operation: str,
    ) -> np.ndarray[Any, np.dtype[np.generic]]:
        with zipfile.ZipFile(path, "r") as archive:
            with archive.open(member.archive_name, "r") as handle:
                payload = _read_member_payload(handle, member, operation=operation)
        return _load_npy_payload(payload, member, operation=operation)

    def _assert_unchanged(self, expected: SourceFingerprint) -> None:
        current = _fingerprint(self._path)
        if current != expected or self._fingerprint != expected:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CHANGED,
                message="NPZ source changed before save; refusing to overwrite.",
                operation="source.npz.apply_change_set",
                details={
                    "expected_fingerprint": expected.to_json(),
                    "observed_fingerprint": current.to_json(),
                    "session_fingerprint": self._fingerprint.to_json(),
                },
                retryable=True,
            )


def _inspect_archive(path: Path) -> tuple[NPZMember, ...]:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            return _inspect_open_archive(archive, path)
    except DataViewerError:
        raise
    except zipfile.BadZipFile as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="NPZ archive is malformed.",
            operation="source.npz.inspect_archive",
            details={"path": str(path)},
            cause=exc,
        ) from exc


def _inspect_open_archive(archive: zipfile.ZipFile, path: Path) -> tuple[NPZMember, ...]:
    infos = [info for info in archive.infolist() if not info.is_dir()]
    if not infos:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="NPZ archive contains no array members.",
            operation="source.npz.inspect_archive",
            details={"path": str(path)},
        )
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        raise DataViewerError(
            code=ErrorCode.BUDGET_EXCEEDED,
            message="NPZ archive contains too many members.",
            operation="source.npz.inspect_archive",
            details={
                "path": str(path),
                "member_count": len(infos),
                "max_member_count": MAX_ARCHIVE_ENTRIES,
            },
        )

    members: list[NPZMember] = []
    seen: dict[str, str] = {}
    total_uncompressed = 0
    for info in infos:
        _validate_zip_info(info, path)
        total_uncompressed += int(info.file_size)
        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="NPZ archive exceeds the total uncompressed-size budget.",
                operation="source.npz.inspect_archive",
                details={
                    "path": str(path),
                    "budget": "total_uncompressed_bytes",
                    "max_total_uncompressed_bytes": MAX_TOTAL_UNCOMPRESSED_BYTES,
                },
            )
        node_path = _normalize_member_name(info.filename, path)
        previous = seen.get(node_path)
        if previous is not None:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="NPZ archive contains duplicate normalized member paths.",
                operation="source.npz.inspect_archive",
                details={
                    "path": str(path),
                    "archive_member": info.filename,
                    "previous_archive_member": previous,
                    "node_path": node_path,
                },
            )
        seen[node_path] = info.filename
        with archive.open(info, "r") as handle:
            shape, fortran_order, dtype = _read_npy_header(handle, info.filename, path)
        if dtype.hasobject:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="Object dtype NPZ members are rejected in v1.",
                operation="source.npz.inspect_archive",
                details={
                    "path": str(path),
                    "archive_member": info.filename,
                    "allow_pickle": False,
                },
            )
        members.append(
            NPZMember(
                archive_name=info.filename,
                node_path=node_path,
                display_name=node_path.rsplit("/", 1)[-1],
                shape=tuple(int(dim) for dim in shape),
                dtype=np.dtype(dtype),
                fortran_order=bool(fortran_order),
                logical_size_bytes=int(np.prod(shape, dtype=np.int64)) * int(dtype.itemsize)
                if shape
                else int(dtype.itemsize),
                compressed_size_bytes=int(info.compress_size),
            )
        )
    return tuple(sorted(members, key=lambda member: member.node_path))


def _validate_zip_info(info: zipfile.ZipInfo, path: Path) -> None:
    if info.flag_bits & 0x1:
        raise DataViewerError(
            code=ErrorCode.SOURCE_ENCRYPTED,
            message="Encrypted NPZ members are not supported.",
            operation="source.npz.inspect_archive",
            details={"path": str(path), "archive_member": info.filename},
        )
    if info.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES:
        raise DataViewerError(
            code=ErrorCode.BUDGET_EXCEEDED,
            message="NPZ member exceeds the uncompressed-size budget.",
            operation="source.npz.inspect_archive",
            details={
                "path": str(path),
                "archive_member": info.filename,
                "budget": "member_uncompressed_bytes",
                "file_size": int(info.file_size),
                "max_member_uncompressed_bytes": MAX_MEMBER_UNCOMPRESSED_BYTES,
            },
        )
    if info.compress_size == 0 and info.file_size > 0:
        ratio = float("inf")
    elif info.compress_size == 0:
        ratio = 1.0
    else:
        ratio = info.file_size / info.compress_size
    if ratio > MAX_COMPRESSION_RATIO:
        raise DataViewerError(
            code=ErrorCode.BUDGET_EXCEEDED,
            message="NPZ member compression ratio exceeds the safety budget.",
            operation="source.npz.inspect_archive",
            details={
                "path": str(path),
                "archive_member": info.filename,
                "budget": "compression_ratio",
                "compression_ratio": float(ratio),
                "max_compression_ratio": MAX_COMPRESSION_RATIO,
            },
        )


def _normalize_member_name(filename: str, path: Path) -> str:
    if "\\" in filename or filename.startswith("/"):
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="NPZ member name is not a safe relative POSIX path.",
            operation="source.npz.inspect_archive",
            details={"path": str(path), "archive_member": filename},
        )
    normalized = posixpath.normpath(filename)
    if normalized in {".", ""} or normalized.startswith("../") or normalized == "..":
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="NPZ member path escapes the archive root.",
            operation="source.npz.inspect_archive",
            details={"path": str(path), "archive_member": filename},
        )
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="NPZ member path contains unsafe path segments.",
            operation="source.npz.inspect_archive",
            details={"path": str(path), "archive_member": filename},
        )
    if not normalized.endswith(".npy"):
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="NPZ member is not an embedded NPY array.",
            operation="source.npz.inspect_archive",
            details={"path": str(path), "archive_member": filename},
        )
    without_suffix = normalized.removesuffix(".npy")
    if not without_suffix:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="NPZ member name is empty after removing .npy suffix.",
            operation="source.npz.inspect_archive",
            details={"path": str(path), "archive_member": filename},
        )
    return "/" + without_suffix


def _read_npy_header(
    handle: Any,
    archive_member: str,
    path: Path,
) -> tuple[tuple[int, ...], bool, np.dtype[Any]]:
    try:
        version = np.lib.format.read_magic(handle)
        if version == (1, 0):
            shape, fortran_order, dtype = np.lib.format.read_array_header_1_0(handle)
        elif version == (2, 0):
            shape, fortran_order, dtype = np.lib.format.read_array_header_2_0(handle)
        elif version == (3, 0):
            shape, fortran_order, dtype = np.lib.format.read_array_header_2_0(handle)
        else:
            raise ValueError(f"unsupported NPY header version {version!r}")
    except Exception as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="NPZ member is not a readable NPY payload.",
            operation="source.npz.inspect_archive",
            details={"path": str(path), "archive_member": archive_member},
            cause=exc,
        ) from exc
    return tuple(int(dim) for dim in shape), bool(fortran_order), np.dtype(dtype)


def _derive_containers(node_paths: tuple[str, ...]) -> frozenset[str]:
    containers: set[str] = set()
    for node_path in node_paths:
        parts = node_path.strip("/").split("/")
        for depth in range(1, len(parts)):
            containers.add("/" + "/".join(parts[:depth]))
    return frozenset(containers)


def _array_attributes(
    member: NPZMember,
    fingerprint: SourceFingerprint,
) -> dict[str, JsonValue]:
    return {
        "format": "NPZ",
        "archive_member": member.archive_name,
        "source_fingerprint": fingerprint.to_json(),
        "byte_order": member.dtype.byteorder,
        "dtype_descriptor": str(member.dtype.descr if member.dtype.fields else member.dtype),
        "fortran_order": member.fortran_order,
        "compressed_size_bytes": member.compressed_size_bytes,
    }


def _estimate_nbytes(
    dtype: np.dtype[Any],
    selection: NormalizedSelection,
) -> int:
    shape = selection.result_shape
    item_count = int(np.prod(shape, dtype=np.int64)) if shape else 1
    return int(item_count * dtype.itemsize)


def _read_array_values(
    array: np.ndarray[Any, np.dtype[np.generic]],
    selection: NormalizedSelection,
) -> np.ndarray[Any, np.dtype[np.generic]]:
    raw = array[selection.to_numpy_key()]
    if selection.result_shape == ():
        return np.asarray(raw, dtype=array.dtype)
    return np.asarray(raw)


def _read_member_payload(handle: Any, member: NPZMember, *, operation: str) -> bytes:
    payload = handle.read(MAX_MEMBER_UNCOMPRESSED_BYTES + 1)
    if len(payload) > MAX_MEMBER_UNCOMPRESSED_BYTES:
        raise DataViewerError(
            code=ErrorCode.BUDGET_EXCEEDED,
            message="NPZ member exceeds the read budget.",
            operation=operation,
            details={
                "archive_member": member.archive_name,
                "max_member_uncompressed_bytes": MAX_MEMBER_UNCOMPRESSED_BYTES,
            },
        )
    return payload


def _load_npy_payload(
    payload: bytes,
    member: NPZMember,
    *,
    operation: str,
) -> np.ndarray[Any, np.dtype[np.generic]]:
    try:
        loaded = np.load(io.BytesIO(payload), allow_pickle=False)
    except ValueError as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="NPZ member cannot be loaded safely with allow_pickle=False.",
            operation=operation,
            details={"archive_member": member.archive_name, "allow_pickle": False},
            cause=exc,
        ) from exc
    if isinstance(loaded, np.lib.npyio.NpzFile):
        loaded.close()
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="Nested NPZ members are not supported.",
            operation=operation,
            details={"archive_member": member.archive_name},
        )
    array = np.asarray(loaded)
    if array.dtype.hasobject:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="Object dtype NPZ members are rejected.",
            operation=operation,
            details={"archive_member": member.archive_name, "allow_pickle": False},
        )
    return array


def _group_cell_patches(patches: tuple[EditPatch, ...]) -> dict[str, list[CellPatch]]:
    grouped: dict[str, list[CellPatch]] = {}
    for patch in patches:
        if not isinstance(patch, CellPatch):
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="NPZ persistence supports cell patches only in v1.",
                operation="source.npz.group_patches",
                resource_id=patch.resource_id,
                details={"patch_type": type(patch).__name__},
            )
        grouped.setdefault(patch.resource_id.node_path, []).append(patch)
    return grouped


def _verify_old_values(
    array: np.ndarray[Any, np.dtype[np.generic]],
    patches: tuple[CellPatch, ...],
    *,
    operation: str,
) -> None:
    for patch_index, patch in enumerate(patches):
        _validate_array_patch(array, patch, operation=operation)
        observed = fingerprint_value(_normalize_numpy_value(array[patch.coordinate]))
        if observed != patch.old_value_fingerprint:
            raise DataViewerError(
                code=ErrorCode.EDIT_CONFLICT,
                message="NPZ patch old value no longer matches the source.",
                operation=operation,
                resource_id=patch.resource_id,
                details={
                    "patch_index": patch_index,
                    "expected_fingerprint": patch.old_value_fingerprint,
                    "observed_fingerprint": observed,
                },
            )


def _apply_numpy_patches(
    array: np.ndarray[Any, np.dtype[np.generic]],
    patches: tuple[CellPatch, ...],
) -> None:
    for patch in patches:
        _validate_array_patch(array, patch, operation="source.npz.apply_patches")
        cast(Any, array)[patch.coordinate] = _cast_numpy_value(patch.new_value, array.dtype)


def _cast_numpy_value(value: object, dtype: np.dtype[Any]) -> object:
    target = np.dtype(dtype)
    if target.fields:
        if not isinstance(value, dict):
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Structured NPZ cells require a mapping patch value.",
                operation="source.npz.cast_value",
                details={"dtype": str(target)},
            )
        field_names = tuple(target.fields)
        if tuple(sorted(value)) != tuple(sorted(field_names)):
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Structured NPZ patch fields do not match target dtype.",
                operation="source.npz.cast_value",
                details={
                    "expected_fields": cast(list[JsonValue], [str(name) for name in field_names]),
                    "received_fields": cast(list[JsonValue], sorted(str(key) for key in value)),
                },
            )
        return np.array(tuple(value[name] for name in field_names), dtype=target)[()]
    return np.array(value, dtype=target)[()]


def _validate_array_patch(
    array: np.ndarray[Any, np.dtype[np.generic]],
    patch: CellPatch,
    *,
    operation: str,
) -> None:
    if len(patch.coordinate) != array.ndim:
        raise DataViewerError(
            code=ErrorCode.SELECTION_INVALID,
            message="NPZ patch coordinate rank does not match array rank.",
            operation=operation,
            resource_id=patch.resource_id,
            details={
                "coordinate_rank": len(patch.coordinate),
                "array_rank": array.ndim,
            },
        )
    for axis, index in enumerate(patch.coordinate):
        if index < 0 or index >= array.shape[axis]:
            raise DataViewerError(
                code=ErrorCode.SELECTION_INVALID,
                message="NPZ patch coordinate is outside array bounds.",
                operation=operation,
                resource_id=patch.resource_id,
                details={"axis": axis, "index": index, "dimension": int(array.shape[axis])},
            )


def _validate_changeset_source(changeset: ChangeSet, *, source_uri: str) -> None:
    for patch in changeset.patches:
        if patch.resource_id.source_uri != source_uri:
            raise DataViewerError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="NPZ changeset targets a different source.",
                operation="source.npz.apply_change_set",
                resource_id=patch.resource_id,
                details={"expected_source_uri": source_uri},
            )


def _validate_candidate_members(
    candidate: Path,
    candidate_members: tuple[NPZMember, ...],
    *,
    expected_members: tuple[NPZMember, ...],
    patched_arrays: dict[str, np.ndarray[Any, np.dtype[np.generic]]],
    source_arrays: dict[str, np.ndarray[Any, np.dtype[np.generic]]],
    patches: tuple[EditPatch, ...],
) -> None:
    expected_by_path = {member.node_path: member for member in expected_members}
    candidate_by_path = {member.node_path: member for member in candidate_members}
    if tuple(candidate_by_path) != tuple(expected_by_path):
        raise DataViewerError(
            code=ErrorCode.READ_FAILED,
            message="NPZ replacement validation found member path drift.",
            operation="source.npz.validate_payload",
            details={
                "expected_paths": cast(list[JsonValue], list(expected_by_path)),
                "candidate_paths": cast(list[JsonValue], list(candidate_by_path)),
            },
        )
    for node_path, patched in patched_arrays.items():
        member = candidate_by_path[node_path]
        node_patches = tuple(
            patch
            for patch in patches
            if isinstance(patch, CellPatch) and patch.resource_id.node_path == node_path
        )
        candidate_values = NPZSourceSession._load_member_array_from_path(
            candidate,
            member,
            operation="source.npz.validate_payload",
        )
        if candidate_values.shape != patched.shape or candidate_values.dtype != patched.dtype:
            raise DataViewerError(
                code=ErrorCode.READ_FAILED,
                message="NPZ replacement validation found shape or dtype drift.",
                operation="source.npz.validate_payload",
                details={
                    "node_path": node_path,
                    "expected_shape": _json_shape(patched.shape),
                    "candidate_shape": _json_shape(candidate_values.shape),
                    "expected_dtype": str(patched.dtype),
                    "candidate_dtype": str(candidate_values.dtype),
                },
            )
        _verify_new_values(candidate_values, patched, node_patches)
        _verify_representative_unchanged_value(
            candidate_values,
            source_arrays[node_path],
            node_patches,
        )


def _verify_new_values(
    candidate: np.ndarray[Any, np.dtype[np.generic]],
    expected: np.ndarray[Any, np.dtype[np.generic]],
    patches: tuple[EditPatch, ...],
) -> None:
    for patch_index, patch in enumerate(patches):
        if not isinstance(patch, CellPatch):
            continue
        if patch.coordinate and len(patch.coordinate) == candidate.ndim:
            observed = _normalize_numpy_value(candidate[patch.coordinate])
            expected_value = _normalize_numpy_value(expected[patch.coordinate])
            if observed != expected_value:
                raise DataViewerError(
                    code=ErrorCode.READ_FAILED,
                    message="NPZ post-write verification failed.",
                    operation="source.npz.verify_new_values",
                    resource_id=patch.resource_id,
                    details={"patch_index": patch_index},
                )


def _verify_representative_unchanged_value(
    candidate: np.ndarray[Any, np.dtype[np.generic]],
    original: np.ndarray[Any, np.dtype[np.generic]],
    patches: tuple[EditPatch, ...],
) -> None:
    if candidate.shape == () or 0 in candidate.shape:
        return
    changed = {patch.coordinate for patch in patches if isinstance(patch, CellPatch)}
    coordinate = tuple(0 for _ in candidate.shape)
    if coordinate in changed:
        return
    if _normalize_numpy_value(candidate[coordinate]) != _normalize_numpy_value(original[coordinate]):
        raise DataViewerError(
            code=ErrorCode.READ_FAILED,
            message="NPZ replacement validation found an unintended value change.",
            operation="source.npz.verify_unchanged",
            details={"coordinate": _json_shape(coordinate)},
        )


def _count_cell_patches(patches: tuple[EditPatch, ...]) -> int:
    return sum(1 for patch in patches if isinstance(patch, CellPatch))


def _normalize_numpy_value(value: object) -> object:
    if isinstance(value, np.void) and value.dtype.fields:
        return {
            field_name: _normalize_numpy_value(value[field_name])
            for field_name in value.dtype.fields
        }
    if isinstance(value, np.ndarray):
        if value.ndim == 0:
            return _normalize_numpy_value(value.item())
        return [_normalize_numpy_value(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _normalize_numpy_value(value.item())
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, tuple):
        return tuple(_normalize_numpy_value(item) for item in value)
    if isinstance(value, list):
        return [_normalize_numpy_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_numpy_value(item) for key, item in value.items()}
    return value


def _fingerprint(path: Path) -> SourceFingerprint:
    stat = path.stat()
    return SourceFingerprint(size_bytes=stat.st_size, modified_time_ns=stat.st_mtime_ns)


def _json_shape(shape: tuple[int, ...]) -> list[JsonValue]:
    return [int(item) for item in shape]


def _resource_not_found(resource_id: ResourceId, *, operation: str) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.RESOURCE_NOT_FOUND,
        message="Requested NPZ resource was not found.",
        operation=operation,
        resource_id=resource_id,
        details={"resource_id": resource_id.to_json()},
    )


def _raise_if_cancelled(cancellation: object, *, operation: str) -> None:
    if getattr(cancellation, "is_cancelled", False):
        raise DataViewerError(
            code=ErrorCode.READ_CANCELLED,
            message="NPZ source operation was cancelled.",
            operation=operation,
            retryable=True,
        )


__all__ = ["NPZSourceSession", "NPZPersistenceResult"]
