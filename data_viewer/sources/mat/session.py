"""Session implementation for read-only MATLAB MAT resources."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import h5py
import numpy as np
import scipy.io
import scipy.sparse as sp
from scipy.io.matlab import mat_struct

from data_viewer.domain import (
    ArrayPayload,
    DataDomain,
    DataMetadata,
    DataViewerError,
    ErrorCode,
    JsonValue,
    NodeKind,
    OperationScope,
    ReadResult,
    ResourceId,
    ResourceNode,
    SourceCapability,
    SourceFingerprint,
    StructuredPayload,
    TextPayload,
)
from data_viewer.sources.api import NodePage, ProgressCallback, ReadRequest

DEFAULT_MAX_LEGACY_VARIABLES = 100_000
DEFAULT_MAX_TREE_NODES = 100_000

_INTERNAL_LEGACY_KEYS = ("__globals__", "__header__", "__version__")
_HIDDEN_HDF5_NAMES = ("#refs#",)


@dataclass(slots=True)
class _MATNode:
    path: str
    name: str
    value: object
    matlab_class: str
    domain: DataDomain
    node_kind: NodeKind
    shape: tuple[int, ...] = ()
    dtype: str = ""
    attributes: dict[str, JsonValue] = field(default_factory=dict)
    children: dict[str, "_MATNode"] = field(default_factory=dict)

    @property
    def has_children(self) -> bool:
        return bool(self.children)


class MATSourceSession:
    """One owned, read-only MATLAB MAT source session."""

    def __init__(
        self,
        path: Path,
        *,
        is_hdf5: bool | None = None,
        max_legacy_variables: int = DEFAULT_MAX_LEGACY_VARIABLES,
        max_tree_nodes: int = DEFAULT_MAX_TREE_NODES,
    ) -> None:
        self._path = path
        self._source_uri = path.resolve(strict=False).as_uri()
        self._closed = False
        self._fingerprint = _fingerprint(path)
        self._max_legacy_variables = _positive(max_legacy_variables, "max_legacy_variables")
        self._max_tree_nodes = _positive(max_tree_nodes, "max_tree_nodes")
        self._h5_file: h5py.File | None = None
        self._version_family = "v7.3" if (h5py.is_hdf5(path) if is_hdf5 is None else is_hdf5) else "legacy"
        self._hidden_internal_keys: tuple[str, ...] = ()
        self._root = self._open_root()
        self._nodes = dict(_walk_nodes(self._root))

    @property
    def source_uri(self) -> str:
        return self._source_uri

    @property
    def fingerprint(self) -> SourceFingerprint:
        return self._fingerprint

    @property
    def capabilities(self) -> SourceCapability:
        return SourceCapability.HIERARCHY | SourceCapability.SEARCH | SourceCapability.SAVE_AS

    def root(self) -> ResourceNode:
        self._ensure_open(operation="source.mat.root")
        return self._resource_node(self._root)

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: object,
    ) -> NodePage:
        self._ensure_open(operation="source.mat.list_children")
        _raise_if_cancelled(cancellation, operation="source.mat.list_children")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        parent_node = self._node_for(parent, operation="source.mat.list_children")
        child_nodes = tuple(parent_node.children.values())
        start = _cursor_to_index(cursor)
        stop = min(start + page_size, len(child_nodes))
        return NodePage(
            items=tuple(self._resource_node(node) for node in child_nodes[start:stop]),
            next_cursor=str(stop) if stop < len(child_nodes) else None,
            total_count=len(child_nodes),
        )

    def get_metadata(
        self,
        resource: ResourceId,
        *,
        cancellation: object,
    ) -> DataMetadata:
        self._ensure_open(operation="source.mat.get_metadata")
        _raise_if_cancelled(cancellation, operation="source.mat.get_metadata")
        node = self._node_for(resource, operation="source.mat.get_metadata")
        attributes: dict[str, JsonValue] = {
            "format": "MAT",
            "mat_version_family": self._version_family,
            "matlab_class": node.matlab_class,
            "read_only": True,
            "source_fingerprint": self._fingerprint.to_json(),
        }
        attributes.update(node.attributes)
        if node.path == "/":
            attributes["hidden_internal_keys"] = list(self._hidden_internal_keys)
        return DataMetadata(
            resource_id=ResourceId(self._source_uri, node.path),
            name=node.name,
            domain=node.domain,
            node_kind=node.node_kind,
            shape=node.shape,
            dtype=node.dtype,
            logical_size_bytes=_logical_size(node.value),
            storage_size_bytes=self._path.stat().st_size,
            capabilities=self._capabilities_for(node),
            attributes=attributes,
        )

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: object,
        progress: ProgressCallback,
    ) -> ReadResult:
        self._ensure_open(operation="source.mat.read")
        _raise_if_cancelled(cancellation, operation="source.mat.read")
        node = self._node_for(request.resource_id, operation="source.mat.read")
        progress(0, 1, "start")
        if node.domain is DataDomain.ARRAY:
            result = self._read_array(node, request)
        elif node.domain is DataDomain.TEXT:
            result = self._read_text(node, request)
        elif node.domain is DataDomain.STRUCTURED:
            result = self._read_structured(node, request)
        else:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="MAT container resources cannot be read as payloads.",
                operation="source.mat.read",
                resource_id=request.resource_id,
            )
        progress(1, 1, "done")
        return result

    def search(
        self,
        query: str,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: object,
    ) -> NodePage:
        self._ensure_open(operation="source.mat.search")
        _raise_if_cancelled(cancellation, operation="source.mat.search")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        normalized = query.strip().lower()
        if not normalized:
            return NodePage(items=(), next_cursor=None, total_count=0)
        matches = tuple(
            self._resource_node(node)
            for path, node in self._nodes.items()
            if path != "/"
            and (normalized in path.lower() or normalized in node.name.lower())
            and not node.attributes.get("cycle_reference", False)
        )
        start = _cursor_to_index(cursor)
        stop = min(start + page_size, len(matches))
        return NodePage(
            items=matches[start:stop],
            next_cursor=str(stop) if stop < len(matches) else None,
            total_count=len(matches),
        )

    def refresh_fingerprint(self) -> SourceFingerprint:
        self._ensure_open(operation="source.mat.refresh_fingerprint")
        self._fingerprint = _fingerprint(self._path)
        return self._fingerprint

    def close(self) -> None:
        self._closed = True
        if self._h5_file is not None:
            self._h5_file.close()
            self._h5_file = None

    def _open_root(self) -> _MATNode:
        if self._version_family == "v7.3":
            return self._open_hdf5_root()
        return self._open_legacy_root()

    def _open_legacy_root(self) -> _MATNode:
        try:
            raw = scipy.io.loadmat(
                self._path,
                struct_as_record=False,
                squeeze_me=False,
                chars_as_strings=False,
                spmatrix=True,
            )
        except Exception as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="MAT source is malformed or unsupported by SciPy.",
                operation="source.mat.open_legacy",
                details={"path": str(self._path)},
                cause=exc,
            ) from exc
        self._hidden_internal_keys = tuple(key for key in _INTERNAL_LEGACY_KEYS if key in raw)
        variables = {
            key: value
            for key, value in raw.items()
            if not key.startswith("__")
        }
        if len(variables) > self._max_legacy_variables:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="MAT variable count exceeds the configured budget.",
                operation="source.mat.open_legacy",
                details={
                    "variable_count": len(variables),
                    "max_legacy_variables": self._max_legacy_variables,
                },
            )
        root = _MATNode(
            path="/",
            name=self._path.name,
            value=variables,
            matlab_class="mat-file",
            domain=DataDomain.HIERARCHICAL_ARRAY,
            node_kind=NodeKind.ROOT,
            attributes={"synthetic_root": True},
        )
        node_count = 1
        for name in sorted(variables):
            child, added = _legacy_node(
                name=name,
                path=_pointer_join("/", name),
                value=variables[name],
                active_ids=set(),
            )
            node_count += added
            if node_count > self._max_tree_nodes:
                raise _tree_budget_error(node_count, self._max_tree_nodes)
            root.children[name] = child
        return root

    def _open_hdf5_root(self) -> _MATNode:
        try:
            self._h5_file = h5py.File(self._path, "r")
        except OSError as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="MAT v7.3 source is not a readable HDF5 container.",
                operation="source.mat.open_hdf5",
                details={"path": str(self._path)},
                cause=exc,
            ) from exc
        root = _MATNode(
            path="/",
            name=self._path.name,
            value=self._h5_file,
            matlab_class="mat-v7.3-file",
            domain=DataDomain.HIERARCHICAL_ARRAY,
            node_kind=NodeKind.ROOT,
            attributes={
                "synthetic_root": True,
                "hdf5_backed": True,
            },
        )
        count = self._populate_hdf5_children(
            parent=root,
            h5_object=self._h5_file,
            active_addresses=set(),
            count=1,
        )
        if count > self._max_tree_nodes:
            raise _tree_budget_error(count, self._max_tree_nodes)
        self._hidden_internal_keys = tuple(
            name for name in _HIDDEN_HDF5_NAMES if name in self._h5_file
        )
        return root

    def _populate_hdf5_children(
        self,
        *,
        parent: _MATNode,
        h5_object: h5py.Group | h5py.File,
        active_addresses: set[int],
        count: int,
    ) -> int:
        address = _hdf5_address(h5_object)
        if address in active_addresses:
            parent.attributes["cycle_reference"] = True
            return count
        active_addresses.add(address)
        try:
            for name in sorted(h5_object.keys()):
                if name in _HIDDEN_HDF5_NAMES:
                    continue
                child_object = h5_object[name]
                child_path = _pointer_join(parent.path, name)
                child = _hdf5_node(name=name, path=child_path, value=child_object)
                parent.children[name] = child
                count += 1
                if count > self._max_tree_nodes:
                    raise _tree_budget_error(count, self._max_tree_nodes)
                if isinstance(child_object, h5py.Group):
                    count = self._populate_hdf5_children(
                        parent=child,
                        h5_object=child_object,
                        active_addresses=active_addresses,
                        count=count,
                    )
        finally:
            active_addresses.remove(address)
        return count

    def _node_for(self, resource: ResourceId, *, operation: str) -> _MATNode:
        if resource.source_uri != self._source_uri:
            raise _resource_not_found(resource, operation=operation)
        node = self._nodes.get(resource.node_path or "/")
        if node is None:
            raise _resource_not_found(resource, operation=operation)
        return node

    def _resource_node(self, node: _MATNode) -> ResourceNode:
        return ResourceNode(
            resource_id=ResourceId(self._source_uri, node.path),
            name=node.name,
            node_kind=node.node_kind,
            domain=node.domain,
            has_children=node.has_children,
            summary=f"MAT {node.matlab_class}",
        )

    def _capabilities_for(self, node: _MATNode) -> SourceCapability:
        base = SourceCapability.SEARCH | SourceCapability.SAVE_AS
        if node.has_children or node.node_kind in {NodeKind.ROOT, NodeKind.CONTAINER}:
            base |= SourceCapability.HIERARCHY
        if node.domain is DataDomain.ARRAY:
            base |= SourceCapability.RANDOM_SLICE
        return base

    def _read_array(self, node: _MATNode, request: ReadRequest) -> ReadResult:
        if request.scope not in {OperationScope.SLICE, OperationScope.FULL}:
            raise _unsupported_scope(request, operation="source.mat.read")
        if request.row_offset is not None or request.row_limit is not None or request.selected_columns:
            raise _unsupported_selection(request, operation="source.mat.read")
        array = _array_for_node(node)
        normalized = request.selection.normalize(tuple(int(dim) for dim in array.shape))
        if not normalized.ok:
            raise DataViewerError(
                code=ErrorCode.SELECTION_INVALID,
                message="Selection is invalid for this MAT array shape.",
                operation="source.mat.read",
                resource_id=request.resource_id,
                details={"errors": [error.to_json() for error in normalized.errors]},
            )
        selection = normalized.unwrap()
        estimated = _estimate_nbytes(array.dtype, selection.result_shape)
        if estimated > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Requested MAT selection exceeds read budget.",
                operation="source.mat.read",
                resource_id=request.resource_id,
                details={"estimated_bytes": estimated, "max_bytes": request.max_bytes},
            )
        numpy_key = selection.to_numpy_key()
        values = array[numpy_key] if numpy_key else array
        return ReadResult(
            payload=ArrayPayload(
                np.asarray(values),
                original_shape=tuple(int(dim) for dim in array.shape),
                selection=selection,
            ),
            scope=request.scope,
            bytes_read=int(np.asarray(values).nbytes),
            is_sampled=False,
            sample=request.sample,
        )

    def _read_text(self, node: _MATNode, request: ReadRequest) -> ReadResult:
        if request.scope is not OperationScope.FULL:
            raise _unsupported_scope(request, operation="source.mat.read")
        if request.selection.axes or request.row_offset is not None or request.row_limit is not None:
            raise _unsupported_selection(request, operation="source.mat.read")
        text = _text_for_node(node)
        size = len(text.encode("utf-8"))
        if size > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Requested MAT char payload exceeds read budget.",
                operation="source.mat.read",
                resource_id=request.resource_id,
                details={"bytes_read": size, "max_bytes": request.max_bytes},
            )
        return ReadResult(
            payload=TextPayload(text=text, offset=0, is_complete=True),
            scope=OperationScope.FULL,
            bytes_read=size,
            is_sampled=False,
            sample=request.sample,
        )

    def _read_structured(self, node: _MATNode, request: ReadRequest) -> ReadResult:
        if request.scope is not OperationScope.FULL:
            raise _unsupported_scope(request, operation="source.mat.read")
        if request.selection.axes or request.row_offset is not None or request.row_limit is not None:
            raise _unsupported_selection(request, operation="source.mat.read")
        value = _structured_for_node(node)
        size = len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        if size > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Requested MAT structured payload exceeds read budget.",
                operation="source.mat.read",
                resource_id=request.resource_id,
                details={"bytes_read": size, "max_bytes": request.max_bytes},
            )
        return ReadResult(
            payload=StructuredPayload(value),
            scope=OperationScope.FULL,
            bytes_read=size,
            is_sampled=False,
            sample=request.sample,
        )

    def _ensure_open(self, operation: str) -> None:
        if self._closed:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CLOSED,
                message="MAT source session is closed.",
                operation=operation,
                details={"source_uri": self._source_uri},
            )


def _legacy_node(
    *,
    name: str,
    path: str,
    value: object,
    active_ids: set[int],
) -> tuple[_MATNode, int]:
    value_id = id(value)
    if value_id in active_ids:
        return (
            _MATNode(
                path=path,
                name=name,
                value=None,
                matlab_class="unsupported",
                domain=DataDomain.STRUCTURED,
                node_kind=NodeKind.RESOURCE,
                attributes={"cycle_reference": True},
            ),
            1,
        )
    if isinstance(value, mat_struct):
        node = _MATNode(
            path=path,
            name=name,
            value=value,
            matlab_class="struct",
            domain=DataDomain.HIERARCHICAL_ARRAY,
            node_kind=NodeKind.CONTAINER,
            attributes={"matlab_struct_fields": list(value._fieldnames or [])},
        )
        count = 1
        active_ids.add(value_id)
        try:
            for field_name in sorted(value._fieldnames or []):
                child_value = getattr(value, field_name)
                child, added = _legacy_node(
                    name=field_name,
                    path=_pointer_join(path, field_name),
                    value=child_value,
                    active_ids=active_ids,
                )
                node.children[field_name] = child
                count += added
        finally:
            active_ids.remove(value_id)
        return node, count
    if sp.issparse(value):
        sparse = cast(sp.spmatrix, value)
        return (
            _MATNode(
                path=path,
                name=name,
                value=sparse,
                matlab_class="sparse",
                domain=DataDomain.STRUCTURED,
                node_kind=NodeKind.RESOURCE,
                shape=tuple(int(dim) for dim in sparse.shape),
                dtype=str(sparse.dtype),
                attributes={"nnz": int(sparse.nnz), "sparse_format": sparse.getformat()},
            ),
            1,
        )
    if isinstance(value, np.ndarray) and value.dtype == object:
        node = _MATNode(
            path=path,
            name=name,
            value=value,
            matlab_class="cell",
            domain=DataDomain.HIERARCHICAL_ARRAY,
            node_kind=NodeKind.CONTAINER,
            shape=tuple(int(dim) for dim in value.shape),
            dtype="object",
            attributes={"matlab_cell": True},
        )
        count = 1
        active_ids.add(value_id)
        try:
            for index in np.ndindex(value.shape):
                child_name = _index_name(index)
                child, added = _legacy_node(
                    name=child_name,
                    path=_pointer_join(path, child_name),
                    value=value[index],
                    active_ids=active_ids,
                )
                node.children[child_name] = child
                count += added
        finally:
            active_ids.remove(value_id)
        return node, count
    if isinstance(value, np.ndarray):
        matlab_class = _legacy_matlab_class(value)
        domain = DataDomain.TEXT if matlab_class == "char" else DataDomain.ARRAY
        return (
            _MATNode(
                path=path,
                name=name,
                value=value,
                matlab_class=matlab_class,
                domain=domain,
                node_kind=NodeKind.RESOURCE,
                shape=tuple(int(dim) for dim in value.shape),
                dtype=str(value.dtype),
            ),
            1,
        )
    if isinstance(value, str):
        return (
            _MATNode(
                path=path,
                name=name,
                value=value,
                matlab_class="char",
                domain=DataDomain.TEXT,
                node_kind=NodeKind.RESOURCE,
                shape=(),
                dtype="str",
            ),
            1,
        )
    scalar = np.asarray(value)
    return (
        _MATNode(
            path=path,
            name=name,
            value=scalar,
            matlab_class=_legacy_matlab_class(scalar),
            domain=DataDomain.ARRAY,
            node_kind=NodeKind.RESOURCE,
            shape=tuple(int(dim) for dim in scalar.shape),
            dtype=str(scalar.dtype),
        ),
        1,
    )


def _hdf5_node(name: str, path: str, value: h5py.Dataset | h5py.Group) -> _MATNode:
    matlab_class = _read_hdf5_class(value)
    if isinstance(value, h5py.Group):
        return _MATNode(
            path=path,
            name=name,
            value=value,
            matlab_class=matlab_class or "group",
            domain=DataDomain.HIERARCHICAL_ARRAY,
            node_kind=NodeKind.CONTAINER,
            attributes=_hdf5_attributes(value),
        )
    if value.dtype.kind == "O":
        return _MATNode(
            path=path,
            name=name,
            value=value,
            matlab_class=matlab_class or "reference",
            domain=DataDomain.STRUCTURED,
            node_kind=NodeKind.RESOURCE,
            shape=tuple(int(dim) for dim in value.shape),
            dtype=str(value.dtype),
            attributes=_hdf5_attributes(value) | {"unsupported_value_state": "hdf5_reference_dataset"},
        )
    domain = DataDomain.TEXT if matlab_class == "char" else DataDomain.ARRAY
    return _MATNode(
        path=path,
        name=name,
        value=value,
        matlab_class=matlab_class or _dtype_matlab_class(value.dtype),
        domain=domain,
        node_kind=NodeKind.RESOURCE,
        shape=tuple(int(dim) for dim in value.shape),
        dtype=str(value.dtype),
        attributes=_hdf5_attributes(value),
    )


def _read_hdf5_class(value: h5py.Dataset | h5py.Group) -> str:
    raw = value.attrs.get("MATLAB_class", "")
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    if isinstance(raw, np.bytes_):
        return bytes(raw).decode("utf-8", errors="replace")
    return str(raw) if raw is not None else ""


def _hdf5_attributes(value: h5py.Dataset | h5py.Group) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {"hdf5_path": value.name}
    for key, raw in value.attrs.items():
        if key == "MATLAB_class":
            continue
        result[f"hdf5_attr_{key}"] = _json_safe(raw)
    return result


def _walk_nodes(root: _MATNode) -> Iterator[tuple[str, _MATNode]]:
    yield root.path, root
    for child in root.children.values():
        yield from _walk_nodes(child)


def _array_for_node(node: _MATNode) -> np.ndarray[Any, np.dtype[np.generic]]:
    if isinstance(node.value, h5py.Dataset):
        return np.asarray(node.value)
    return np.asarray(node.value)


def _text_for_node(node: _MATNode) -> str:
    value = node.value
    if isinstance(value, h5py.Dataset):
        array = np.asarray(value)
        if array.dtype.kind in {"u", "i"}:
            return "".join(chr(int(codepoint)) for codepoint in array.ravel() if int(codepoint) != 0)
        return "".join(str(item) for item in array.ravel())
    if isinstance(value, str):
        return value
    array = np.asarray(value)
    if array.dtype.kind in {"U", "S"}:
        return "".join(str(item.decode("utf-8") if isinstance(item, bytes) else item) for item in array.ravel())
    return str(value)


def _structured_for_node(node: _MATNode) -> JsonValue:
    if sp.issparse(node.value):
        sparse = cast(sp.spmatrix, node.value)
        return {
            "matlab_class": "sparse",
            "shape": [int(dim) for dim in sparse.shape],
            "nnz": int(sparse.nnz),
            "format": sparse.getformat(),
            "dtype": str(sparse.dtype),
        }
    if isinstance(node.value, h5py.Dataset) and node.value.dtype.kind == "O":
        return {
            "matlab_class": node.matlab_class,
            "shape": list(node.shape),
            "dtype": str(node.value.dtype),
            "unsupported_value_state": "hdf5_reference_dataset",
        }
    return {
        "matlab_class": node.matlab_class,
        "unsupported_value_state": "not_directly_readable",
        "path": node.path,
    }


def _logical_size(value: object) -> int | None:
    if isinstance(value, np.ndarray):
        return int(value.nbytes)
    if isinstance(value, h5py.Dataset):
        return int(value.size * value.dtype.itemsize)
    if sp.issparse(value):
        sparse = cast(sp.spmatrix, value)
        return int(sparse.data.nbytes + sparse.indices.nbytes + sparse.indptr.nbytes)
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    return None


def _legacy_matlab_class(array: np.ndarray[Any, np.dtype[np.generic]]) -> str:
    if array.dtype.kind in {"U", "S"}:
        return "char"
    if array.dtype.kind == "b":
        return "logical"
    if array.dtype.kind == "c":
        return "complex"
    if array.dtype == np.uint8 and array.size and np.isin(array, [0, 1]).all():
        return "logical"
    return _dtype_matlab_class(array.dtype)


def _dtype_matlab_class(dtype: np.dtype[Any]) -> str:
    if dtype == np.dtype("float64"):
        return "double"
    if dtype == np.dtype("float32"):
        return "single"
    if dtype.kind == "b":
        return "logical"
    if dtype.kind == "c":
        return "complex"
    if dtype.kind in {"U", "S"}:
        return "char"
    return str(dtype)


def _estimate_nbytes(dtype: np.dtype[Any], shape: tuple[int, ...]) -> int:
    count = 1
    for dim in shape:
        count *= int(dim)
    return int(count * dtype.itemsize)


def _index_name(index: tuple[int, ...]) -> str:
    return ",".join(str(part) for part in index)


def _pointer_join(parent: str, token: str) -> str:
    escaped = token.replace("~", "~0").replace("/", "~1")
    if parent in {"", "/"}:
        return "/" + escaped
    return parent.rstrip("/") + "/" + escaped


def _pointer_unescape(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _cursor_to_index(cursor: str | None) -> int:
    try:
        start = int(cursor or 0)
    except ValueError as exc:
        raise ValueError("cursor must be a non-negative integer string") from exc
    if start < 0:
        raise ValueError("cursor must be a non-negative integer")
    return start


def _hdf5_address(value: h5py.Dataset | h5py.Group | h5py.File) -> int:
    return int(h5py.h5o.get_info(value.id).addr)


def _json_safe(value: object) -> JsonValue:
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _positive(value: int, label: str) -> int:
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return int(value)


def _tree_budget_error(count: int, maximum: int) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.BUDGET_EXCEEDED,
        message="MAT resource tree exceeds the configured traversal budget.",
        operation="source.mat.build_tree",
        details={"node_count": count, "max_tree_nodes": maximum},
    )


def _unsupported_scope(request: ReadRequest, *, operation: str) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.CAPABILITY_UNAVAILABLE,
        message="Unsupported MAT read scope.",
        operation=operation,
        resource_id=request.resource_id,
        details={"scope": request.scope.value},
    )


def _unsupported_selection(request: ReadRequest, *, operation: str) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.CAPABILITY_UNAVAILABLE,
        message="This MAT resource does not support the requested selection mode.",
        operation=operation,
        resource_id=request.resource_id,
    )


def _resource_not_found(resource_id: ResourceId, *, operation: str) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.RESOURCE_NOT_FOUND,
        message="Requested MAT resource was not found.",
        operation=operation,
        resource_id=resource_id,
        details={"resource_id": resource_id.to_json()},
    )


def _raise_if_cancelled(cancellation: object, *, operation: str) -> None:
    if getattr(cancellation, "is_cancelled", False):
        raise DataViewerError(
            code=ErrorCode.READ_CANCELLED,
            message="MAT source operation was cancelled.",
            operation=operation,
            retryable=True,
        )


def _fingerprint(path: Path) -> SourceFingerprint:
    try:
        stat = path.stat()
    except OSError as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Unable to stat MAT source.",
            operation="source.mat.fingerprint",
            details={"path": str(path)},
            cause=exc,
        ) from exc
    return SourceFingerprint(size_bytes=stat.st_size, modified_time_ns=stat.st_mtime_ns)


__all__ = ["MATSourceSession"]
