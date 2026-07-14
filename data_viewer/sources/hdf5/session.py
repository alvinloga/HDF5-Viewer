"""Session implementation for HDF5 resources in Data Viewer v1."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from data_viewer.domain import (
    ArrayPayload,
    DataDomain,
    DataMetadata,
    DataViewerError,
    ErrorCode,
    NodeKind,
    NormalizedSelection,
    OperationScope,
    ReadResult,
    ResourceId,
    SourceCapability,
    SourceFingerprint,
)
from data_viewer.sources.api import NodePage, ProgressCallback, ReadRequest, ResourceNode


class HDF5SourceSession:
    """One owned HDF5 file session."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._source_uri = path.resolve(strict=False).as_uri()
        self._closed = False
        self._file: h5py.File | None = None
        self._fingerprint = _fingerprint(path)
        self._open_file()

    @property
    def source_uri(self) -> str:
        return self._source_uri

    @property
    def fingerprint(self) -> SourceFingerprint:
        return self._fingerprint

    @property
    def capabilities(self) -> SourceCapability:
        return SourceCapability.HIERARCHY | SourceCapability.SEARCH

    def root(self) -> ResourceNode:
        self._ensure_open(operation="source.hdf5.root")
        return ResourceNode(
            resource_id=ResourceId(self._source_uri, "/"),
            name=self._path.name,
            node_kind=NodeKind.ROOT,
            domain=DataDomain.HIERARCHICAL_ARRAY,
            has_children=bool(self._file.keys()),
            summary=self._path.name,
        )

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: object,
    ) -> NodePage:
        self._ensure_open(operation="source.hdf5.list_children")
        _raise_if_cancelled(cancellation, operation="source.hdf5.list_children")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")

        if parent.source_uri != self._source_uri:
            raise _resource_not_found(
                parent,
                operation="source.hdf5.list_children",
                details={"expected_source_uri": self._source_uri},
            )

        parent_object = self._resolve_object(parent.node_path)
        if not isinstance(parent_object, h5py.Group):
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="Only group resources can list direct children.",
                operation="source.hdf5.list_children",
                resource_id=parent,
            )

        child_names = tuple(sorted(parent_object.keys()))
        try:
            start = int(cursor or 0)
        except ValueError as exc:
            raise ValueError("cursor must be a non-negative integer string") from exc
        if start < 0:
            raise ValueError("cursor must be a non-negative integer")

        _raise_if_cancelled(cancellation, operation="source.hdf5.list_children")
        stop = min(start + page_size, len(child_names))
        items = tuple(
            _link_to_node(
                parent_path=parent.node_path,
                parent_object=parent_object,
                child_name=child_name,
                source_uri=self._source_uri,
            )
            for child_name in child_names[start:stop]
        )
        return NodePage(
            items=items,
            next_cursor=str(stop) if stop < len(child_names) else None,
            total_count=len(child_names),
        )

    def get_metadata(
        self,
        resource: ResourceId,
        *,
        cancellation: object,
    ) -> DataMetadata:
        self._ensure_open(operation="source.hdf5.get_metadata")
        _raise_if_cancelled(cancellation, operation="source.hdf5.get_metadata")

        if resource.source_uri != self._source_uri:
            raise _resource_not_found(
                resource,
                operation="source.hdf5.get_metadata",
                details={"expected_source_uri": self._source_uri},
            )

        if resource.node_path == "/":
            return DataMetadata(
                resource_id=resource,
                name=self._path.name,
                domain=DataDomain.HIERARCHICAL_ARRAY,
                node_kind=NodeKind.ROOT,
                shape=(),
                capabilities=self.capabilities | SourceCapability.SEARCH,
                attributes=_read_attributes(self._file.attrs),
                storage_size_bytes=self._path.stat().st_size,
            )

        parent_group = _parent_group(self._file, resource.node_path)
        child_name = _node_name(resource.node_path)
        link = parent_group.get(child_name, getlink=True)
        if link is None:
            raise _resource_not_found(resource, operation="source.hdf5.get_metadata")

        if isinstance(link, h5py.ExternalLink):
            return DataMetadata(
                resource_id=resource,
                name=child_name,
                domain=DataDomain.METADATA,
                node_kind=NodeKind.RESOURCE,
                has_children=False,
                capabilities=SourceCapability.NONE,
                summary=f"external link -> {link.filename}:{link.path}",
            )

        if isinstance(link, h5py.SoftLink):
            try:
                parent_group[child_name]
            except (KeyError, OSError):
                summary = f"broken soft link -> {link.path}"
            else:
                summary = f"soft link -> {link.path}"
            return DataMetadata(
                resource_id=resource,
                name=child_name,
                domain=DataDomain.METADATA,
                node_kind=NodeKind.RESOURCE,
                has_children=False,
                capabilities=SourceCapability.NONE,
                summary=summary,
            )

        try:
            child = parent_group[child_name]
        except (KeyError, OSError) as exc:
            raise _resource_not_found(
                resource,
                operation="source.hdf5.get_metadata",
            ) from exc

        if isinstance(child, h5py.Group):
            return DataMetadata(
                resource_id=resource,
                name=child_name,
                domain=DataDomain.HIERARCHICAL_ARRAY,
                node_kind=NodeKind.CONTAINER,
                has_children=bool(child.keys()),
                summary=f"group ({len(child.keys())} direct children)",
                capabilities=SourceCapability.HIERARCHY | SourceCapability.SEARCH,
                attributes=_read_attributes(child.attrs),
            )

        if isinstance(child, h5py.Dataset):
            return DataMetadata(
                resource_id=resource,
                name=child_name,
                domain=DataDomain.ARRAY,
                node_kind=NodeKind.RESOURCE,
                shape=tuple(int(dim) for dim in child.shape),
                dtype=str(child.dtype),
                logical_size_bytes=_safe_nbytes(child),
                storage_size_bytes=_safe_dataset_storage_bytes(child),
                capabilities=SourceCapability.RANDOM_SLICE | SourceCapability.SEARCH,
                attributes=_read_attributes(child.attrs),
            )

        return DataMetadata(
            resource_id=resource,
            name=child_name,
            domain=DataDomain.METADATA,
            node_kind=NodeKind.RESOURCE,
            has_children=False,
            capabilities=SourceCapability.NONE,
            attributes={"kind": str(type(child).__name__)},
        )

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: object,
        progress: ProgressCallback,
    ) -> ReadResult:
        self._ensure_open(operation="source.hdf5.read")
        _raise_if_cancelled(cancellation, operation="source.hdf5.read")

        if request.row_offset is not None or request.row_limit is not None:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="row-based reads are not supported for HDF5 arrays.",
                operation="source.hdf5.read",
                resource_id=request.resource_id,
                details={"selected_rows_supported": False},
            )

        if request.selected_columns:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="column-based reads are not supported for HDF5 arrays.",
                operation="source.hdf5.read",
                resource_id=request.resource_id,
                details={"selected_columns_supported": False},
            )

        if request.scope not in {OperationScope.SLICE, OperationScope.FULL}:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="Unsupported HDF5 read scope.",
                operation="source.hdf5.read",
                resource_id=request.resource_id,
                details={"scope": request.scope.value},
            )

        parent_group = _parent_group(self._file, request.resource_id.node_path)
        child_name = _node_name(request.resource_id.node_path)
        link = parent_group.get(child_name, getlink=True)
        if link is None:
            raise _resource_not_found(request.resource_id, operation="source.hdf5.read")

        if not isinstance(link, h5py.HardLink):
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="Only directly linked HDF5 datasets can be read.",
                operation="source.hdf5.read",
                resource_id=request.resource_id,
                details={"link_type": type(link).__name__},
            )

        try:
            child = parent_group[child_name]
        except (KeyError, OSError) as exc:
            raise _resource_not_found(
                request.resource_id,
                operation="source.hdf5.read",
            ) from exc

        if not isinstance(child, h5py.Dataset):
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="Only array datasets can be read as HDF5 values.",
                operation="source.hdf5.read",
                resource_id=request.resource_id,
            )

        normalized = request.selection.normalize(child.shape)
        if not normalized.ok:
            raise DataViewerError(
                code=ErrorCode.SELECTION_INVALID,
                message="Selection is invalid for this dataset shape.",
                operation="source.hdf5.read",
                resource_id=request.resource_id,
                details={"errors": [error.to_json() for error in normalized.errors]},
            )
        selection = normalized.unwrap()

        _raise_if_cancelled(cancellation, operation="source.hdf5.read")
        estimated_bytes = _estimate_nbytes(child, selection)
        if estimated_bytes > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Requested selection exceeds read budget.",
                operation="source.hdf5.read",
                resource_id=request.resource_id,
                details={
                    "estimated_bytes": estimated_bytes,
                    "max_bytes": request.max_bytes,
                },
                retryable=False,
            )

        progress(0, 1, "start")
        values = np.asarray(child[selection.to_numpy_key()])
        _raise_if_cancelled(cancellation, operation="source.hdf5.read")
        progress(1, 1, "done")

        read_bytes = int(values.nbytes)
        if read_bytes > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Read payload exceeds configured budget.",
                operation="source.hdf5.read",
                resource_id=request.resource_id,
                details={
                    "bytes_read": read_bytes,
                    "max_bytes": request.max_bytes,
                },
            )

        return ReadResult(
            payload=ArrayPayload(
                values=values,
                original_shape=tuple(int(dim) for dim in child.shape),
                selection=selection,
            ),
            scope=request.scope,
            bytes_read=read_bytes,
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
        self._ensure_open(operation="source.hdf5.search")
        _raise_if_cancelled(cancellation, operation="source.hdf5.search")

        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")

        normalized_query = query.strip().lower()
        if not normalized_query:
            return NodePage(items=(), next_cursor=None, total_count=0)

        root = self.root()
        root_items = self.list_children(
            root.resource_id,
            cursor=None,
            page_size=10_000,
            cancellation=cancellation,
        ).items
        matches = tuple(
            child
            for child in root_items
            if (
                normalized_query in child.name.lower()
                or normalized_query in child.summary.lower()
            )
        )
        _raise_if_cancelled(cancellation, operation="source.hdf5.search")

        try:
            start = int(cursor or 0)
        except ValueError as exc:
            raise ValueError("cursor must be a non-negative integer string") from exc
        if start < 0:
            raise ValueError("cursor must be a non-negative integer")

        stop = min(start + page_size, len(matches))
        return NodePage(
            items=matches[start:stop],
            next_cursor=str(stop) if stop < len(matches) else None,
            total_count=len(matches),
        )

    def refresh_fingerprint(self) -> SourceFingerprint:
        self._ensure_open(operation="source.hdf5.refresh_fingerprint")
        self._fingerprint = _fingerprint(self._path)
        return self._fingerprint

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._file is not None:
            self._file.close()
            self._file = None

    def _ensure_open(self, operation: str) -> None:
        if self._closed:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CLOSED,
                message="HDF5 source session is closed.",
                operation=operation,
                details={"source_uri": self._source_uri},
            )
        if self._file is None:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="HDF5 file handle is unavailable.",
                operation=operation,
                details={"source_uri": self._source_uri},
            )

    def _open_file(self) -> None:
        try:
            self._file = h5py.File(self._path, "r")
        except OSError as exc:
            self._closed = True
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Unable to open HDF5 source.",
                operation="source.hdf5.open",
                details={"path": str(self._path)},
                cause=exc,
            ) from exc

    def _resolve_object(self, node_path: str) -> h5py.Group | h5py.Dataset:
        if node_path == "/":
            return self._file["/"]
        try:
            return self._file[node_path]
        except (KeyError, OSError) as exc:
            raise _resource_not_found(
                ResourceId(self._source_uri, node_path),
                operation="source.hdf5.resolve_object",
            ) from exc


def _parent_group(file: h5py.File, node_path: str) -> h5py.Group:
    if node_path == "/":
        raise ValueError("root has no parent group")
    if "/" not in node_path.strip("/"):
        return file["/"]
    return file[_parent_path(node_path)]


def _parent_path(node_path: str) -> str:
    stripped = node_path.strip("/")
    return "/" if "/" not in stripped else f"/{'/'.join(stripped.split('/')[:-1])}"


def _node_name(node_path: str) -> str:
    stripped = node_path.strip("/")
    if not stripped:
        raise ValueError("resource node path must reference a child node")
    return stripped.split("/")[-1]


def _link_to_node(
    *,
    parent_path: str,
    parent_object: h5py.Group,
    child_name: str,
    source_uri: str,
) -> ResourceNode:
    child_path = f"{parent_path}/{child_name}" if parent_path != "/" else f"/{child_name}"
    link = parent_object.get(child_name, getlink=True)
    if link is None:
        raise _missing_child_error(child_path)

    if isinstance(link, h5py.ExternalLink):
        return ResourceNode(
            resource_id=ResourceId(source_uri, child_path),
            name=child_name,
            node_kind=NodeKind.RESOURCE,
            domain=DataDomain.METADATA,
            has_children=False,
            summary=f"external link -> {link.filename}:{link.path}",
        )

    if isinstance(link, h5py.SoftLink):
        try:
            parent_object[child_name]
        except (KeyError, OSError, TypeError):
            summary = f"broken soft link -> {link.path}"
        else:
            summary = f"soft link -> {link.path}"
        return ResourceNode(
            resource_id=ResourceId(source_uri, child_path),
            name=child_name,
            node_kind=NodeKind.RESOURCE,
            domain=DataDomain.METADATA,
            has_children=False,
            summary=summary,
        )

    try:
        target = parent_object[child_name]
    except (KeyError, OSError, TypeError):
        return ResourceNode(
            resource_id=ResourceId(source_uri, child_path),
            name=child_name,
            node_kind=NodeKind.RESOURCE,
            domain=DataDomain.METADATA,
            has_children=False,
            summary="broken link",
        )

    if isinstance(target, h5py.Dataset):
        return ResourceNode(
            resource_id=ResourceId(source_uri, child_path),
            name=child_name,
            node_kind=NodeKind.RESOURCE,
            domain=DataDomain.ARRAY,
            has_children=False,
            summary=f"array shape={target.shape} dtype={target.dtype}",
        )
    if isinstance(target, h5py.Group):
        return ResourceNode(
            resource_id=ResourceId(source_uri, child_path),
            name=child_name,
            node_kind=NodeKind.CONTAINER,
            domain=DataDomain.HIERARCHICAL_ARRAY,
            has_children=bool(target.keys()),
            summary=f"group ({len(target.keys())} direct children)",
        )

    return ResourceNode(
        resource_id=ResourceId(source_uri, child_path),
        name=child_name,
        node_kind=NodeKind.RESOURCE,
        domain=DataDomain.METADATA,
        has_children=False,
        summary=f"resource type: {type(target).__name__}",
    )


def _safe_nbytes(dataset: h5py.Dataset) -> int | None:
    try:
        return int(dataset.nbytes)
    except TypeError:
        return None


def _safe_dataset_storage_bytes(dataset: h5py.Dataset) -> int:
    try:
        return int(dataset.id.get_storage_size())
    except (AttributeError, OSError):
        return _safe_nbytes(dataset) or 0


def _read_attributes(attributes: h5py.AttributeManager) -> dict[str, object]:
    return {key: _serialize_attribute(value) for key, value in attributes.items()}


def _serialize_attribute(value: object) -> object:
    if isinstance(value, np.ndarray):
        if value.ndim == 0:
            value = value.item()
        else:
            return value.tolist()

    if isinstance(value, np.generic):
        try:
            return value.item()
        except (TypeError, ValueError):
            return str(value)

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (tuple, list)):
        return [_serialize_attribute(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_attribute(item) for key, item in value.items()}

    return str(value)


def _estimate_nbytes(dataset: h5py.Dataset, selection: NormalizedSelection) -> int:
    selected_shape = selection.result_shape
    return int(np.prod(selected_shape, dtype=np.int64) * dataset.dtype.itemsize)


def _fingerprint(path: Path) -> SourceFingerprint:
    stat = path.stat()
    return SourceFingerprint(
        size_bytes=stat.st_size,
        modified_time_ns=stat.st_mtime_ns,
    )


def _resource_not_found(
    resource_id: ResourceId,
    *,
    operation: str,
    details: dict[str, object] | None = None,
) -> DataViewerError:
    payload = {"resource_id": resource_id.to_json()}
    if details is not None:
        payload.update(details)
    return DataViewerError(
        code=ErrorCode.RESOURCE_NOT_FOUND,
        message="Requested HDF5 resource was not found.",
        operation=operation,
        resource_id=resource_id,
        details=payload,
    )


def _missing_child_error(path: str) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.INTERNAL_ERROR,
        message="Internal inconsistency while building HDF5 node metadata.",
        operation="source.hdf5.list_children",
        details={"path": path},
    )


def _raise_if_cancelled(
    cancellation: object,
    *,
    operation: str,
) -> None:
    if getattr(cancellation, "is_cancelled", False):
        raise DataViewerError(
            code=ErrorCode.READ_CANCELLED,
            message="HDF5 source operation was cancelled.",
            operation=operation,
            retryable=True,
        )


__all__ = ["HDF5SourceSession"]
