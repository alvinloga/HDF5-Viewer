"""Session implementation for NumPy ``.npy`` resources in Data Viewer v1."""

from __future__ import annotations

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

type NumpyPersistenceFailureInjector = Callable[[Any], None]

ARRAY_NODE_PATH = "/array"


@dataclass(frozen=True, slots=True)
class NumpyPersistenceResult:
    """Result of applying one NPY changeset."""

    strategy: SaveStrategy
    source_fingerprint: SourceFingerprint
    changed_coordinates: int
    warnings: tuple[str, ...] = ()


class NPYSourceSession:
    """One owned NPY file session with a single synthetic array resource."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._source_uri = path.resolve(strict=False).as_uri()
        self._closed = False
        self._fingerprint = _fingerprint(path)
        self._array: np.ndarray[Any, np.dtype[np.generic]] | None = None
        self._open_array()

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
        self._ensure_open(operation="source.npy.root")
        return ResourceNode(
            resource_id=ResourceId(self._source_uri, "/"),
            name=self._path.name,
            node_kind=NodeKind.ROOT,
            domain=DataDomain.HIERARCHICAL_ARRAY,
            has_children=True,
            summary=f"NPY array source {self._path.name}",
        )

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: object,
    ) -> NodePage:
        self._ensure_open(operation="source.npy.list_children")
        _raise_if_cancelled(cancellation, operation="source.npy.list_children")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        if parent != ResourceId(self._source_uri, "/"):
            raise _resource_not_found(parent, operation="source.npy.list_children")

        try:
            start = int(cursor or 0)
        except ValueError as exc:
            raise ValueError("cursor must be a non-negative integer string") from exc
        if start < 0:
            raise ValueError("cursor must be a non-negative integer")

        children = (self._array_node(),)
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
        self._ensure_open(operation="source.npy.get_metadata")
        _raise_if_cancelled(cancellation, operation="source.npy.get_metadata")
        array = self._require_array()

        if resource == ResourceId(self._source_uri, "/"):
            return DataMetadata(
                resource_id=resource,
                name=self._path.name,
                domain=DataDomain.HIERARCHICAL_ARRAY,
                node_kind=NodeKind.ROOT,
                shape=(),
                capabilities=self.capabilities,
                attributes={
                    "source_fingerprint": self._fingerprint.to_json(),
                    "synthetic_root": True,
                },
                storage_size_bytes=self._path.stat().st_size,
            )
        if resource != ResourceId(self._source_uri, ARRAY_NODE_PATH):
            raise _resource_not_found(resource, operation="source.npy.get_metadata")

        return DataMetadata(
            resource_id=resource,
            name="array",
            domain=DataDomain.ARRAY,
            node_kind=NodeKind.RESOURCE,
            shape=tuple(int(dim) for dim in array.shape),
            dtype=str(array.dtype),
            logical_size_bytes=int(array.nbytes),
            storage_size_bytes=self._path.stat().st_size,
            capabilities=(
                SourceCapability.RANDOM_SLICE
                | SourceCapability.SEARCH
                | SourceCapability.EDIT_PATCH
                | SourceCapability.ATOMIC_REWRITE
                | SourceCapability.SAVE_AS
            ),
            attributes=_array_attributes(array, self._fingerprint),
        )

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: object,
        progress: ProgressCallback,
    ) -> ReadResult:
        self._ensure_open(operation="source.npy.read")
        _raise_if_cancelled(cancellation, operation="source.npy.read")
        array = self._require_array()

        if request.resource_id != ResourceId(self._source_uri, ARRAY_NODE_PATH):
            raise _resource_not_found(request.resource_id, operation="source.npy.read")
        if request.row_offset is not None or request.row_limit is not None:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="row-based reads are not supported for NPY arrays.",
                operation="source.npy.read",
                resource_id=request.resource_id,
            )
        if request.selected_columns:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="column-based reads are not supported for NPY arrays.",
                operation="source.npy.read",
                resource_id=request.resource_id,
            )
        if request.scope not in {OperationScope.SLICE, OperationScope.FULL}:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="Unsupported NPY read scope.",
                operation="source.npy.read",
                resource_id=request.resource_id,
                details={"scope": request.scope.value},
            )

        normalized = request.selection.normalize(tuple(int(dim) for dim in array.shape))
        if not normalized.ok:
            raise DataViewerError(
                code=ErrorCode.SELECTION_INVALID,
                message="Selection is invalid for this NPY array shape.",
                operation="source.npy.read",
                resource_id=request.resource_id,
                details={"errors": [error.to_json() for error in normalized.errors]},
            )
        selection = normalized.unwrap()

        estimated_bytes = _estimate_nbytes(array.dtype, selection)
        if estimated_bytes > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Requested NPY selection exceeds read budget.",
                operation="source.npy.read",
                resource_id=request.resource_id,
                details={
                    "estimated_bytes": estimated_bytes,
                    "max_bytes": request.max_bytes,
                },
            )

        progress(0, 1, "start")
        values = _read_array_values(array, selection)
        _raise_if_cancelled(cancellation, operation="source.npy.read")
        progress(1, 1, "done")

        if values.nbytes > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Read NPY payload exceeds configured budget.",
                operation="source.npy.read",
                resource_id=request.resource_id,
                details={
                    "bytes_read": int(values.nbytes),
                    "max_bytes": request.max_bytes,
                },
            )

        return ReadResult(
            payload=ArrayPayload(
                values=values,
                original_shape=tuple(int(dim) for dim in array.shape),
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
        self._ensure_open(operation="source.npy.search")
        _raise_if_cancelled(cancellation, operation="source.npy.search")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        normalized_query = query.strip().lower()
        if not normalized_query or "array".startswith(normalized_query):
            return self.list_children(
                ResourceId(self._source_uri, "/"),
                cursor=cursor,
                page_size=page_size,
                cancellation=cancellation,
            ) if normalized_query else NodePage(items=(), next_cursor=None, total_count=0)
        return NodePage(items=(), next_cursor=None, total_count=0)

    def refresh_fingerprint(self) -> SourceFingerprint:
        self._ensure_open(operation="source.npy.refresh_fingerprint")
        self._fingerprint = _fingerprint(self._path)
        return self._fingerprint

    def apply_change_set(
        self,
        changeset: ChangeSet,
        *,
        cancellation: object,
        replacement_service: AtomicReplacementService | None = None,
        failure_injector: NumpyPersistenceFailureInjector | None = None,
    ) -> NumpyPersistenceResult:
        """Apply one reviewed changeset through a verified replacement write."""

        self._ensure_open(operation="source.npy.apply_change_set")
        _raise_if_cancelled(cancellation, operation="source.npy.apply_change_set")
        _validate_changeset_source(changeset, source_uri=self._source_uri)
        if changeset.is_clean:
            raise ValueError("changeset must contain at least one patch")
        self._assert_unchanged(changeset.source_fingerprint)

        source_values = np.array(self._require_array(), copy=True, order="K")
        patched_values = np.array(source_values, copy=True, order="K")
        _verify_old_values(source_values, changeset.patches)
        _apply_numpy_patches(patched_values, changeset.patches)

        self._close_array_handle()
        service = replacement_service or AtomicReplacementService()
        token = (
            cancellation
            if isinstance(cancellation, TaskCancellationToken)
            else None
        )

        def write_payload(temp_path: Path) -> None:
            with temp_path.open("wb") as handle:
                np.save(handle, patched_values, allow_pickle=False)

        def validate_payload(candidate: Path) -> SourceFingerprint:
            candidate_values = _load_candidate(candidate)
            try:
                _validate_candidate_array(
                    candidate_values,
                    expected=patched_values,
                    original=source_values,
                    patches=changeset.patches,
                )
            finally:
                self._close_array_object(candidate_values)
            return _fingerprint(candidate)

        try:
            result = service.run_replacement(
                self._path,
                self._path,
                write_payload=write_payload,
                validate_payload=validate_payload,
                expected_source_fingerprint=changeset.source_fingerprint,
                estimated_output_bytes=max(self._path.stat().st_size, patched_values.nbytes),
                cancellation=token,
                failure_injector=failure_injector,
            )
        finally:
            if self._array is None and self._path.exists():
                self._open_array()

        self._fingerprint = result.destination_fingerprint
        self._close_array_handle()
        self._open_array()
        return NumpyPersistenceResult(
            strategy=SaveStrategy.REPLACEMENT,
            source_fingerprint=self._fingerprint,
            changed_coordinates=_count_cell_patches(changeset.patches),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._close_array_handle()

    def _array_node(self) -> ResourceNode:
        array = self._require_array()
        return ResourceNode(
            resource_id=ResourceId(self._source_uri, ARRAY_NODE_PATH),
            name="array",
            node_kind=NodeKind.RESOURCE,
            domain=DataDomain.ARRAY,
            has_children=False,
            summary=f"array shape={array.shape} dtype={array.dtype}",
        )

    def _ensure_open(self, operation: str) -> None:
        if self._closed:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CLOSED,
                message="NPY source session is closed.",
                operation=operation,
                details={"source_uri": self._source_uri},
            )
        if self._array is None:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="NPY array handle is unavailable.",
                operation=operation,
                details={"source_uri": self._source_uri},
            )

    def _require_array(self) -> np.ndarray[Any, np.dtype[np.generic]]:
        if self._array is None:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="NPY array handle is unavailable.",
                operation="source.npy.array_handle",
                details={"source_uri": self._source_uri},
            )
        return self._array

    def _open_array(self) -> None:
        try:
            loaded = np.load(self._path, allow_pickle=False, mmap_mode="r")
        except ValueError as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="NPY source cannot be loaded safely with allow_pickle=False.",
                operation="source.npy.open",
                details={"path": str(self._path), "allow_pickle": False},
                cause=exc,
            ) from exc
        except OSError as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Unable to open NPY source.",
                operation="source.npy.open",
                details={"path": str(self._path)},
                cause=exc,
            ) from exc
        if isinstance(loaded, np.lib.npyio.NpzFile):
            loaded.close()
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="Expected a single NPY array, not an NPZ archive.",
                operation="source.npy.open",
                details={"path": str(self._path)},
            )
        array = np.asarray(loaded)
        if array.dtype.hasobject:
            self._close_array_object(array)
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="Object dtype NPY arrays are rejected in v1.",
                operation="source.npy.open",
                details={"path": str(self._path), "allow_pickle": False},
            )
        self._array = array

    def _close_array_handle(self) -> None:
        if self._array is None:
            return
        self._close_array_object(self._array)
        self._array = None

    @staticmethod
    def _close_array_object(array: np.ndarray[Any, np.dtype[np.generic]]) -> None:
        seen: set[int] = set()
        current: object | None = array
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            mmap = getattr(current, "_mmap", None)
            close = getattr(mmap, "close", None)
            if callable(close):
                close()
                return
            current = getattr(current, "base", None)

    def _assert_unchanged(self, expected: SourceFingerprint) -> None:
        current = _fingerprint(self._path)
        if current != expected or self._fingerprint != expected:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CHANGED,
                message="NPY source changed before save; refusing to overwrite.",
                operation="source.npy.apply_change_set",
                details={
                    "expected_fingerprint": expected.to_json(),
                    "observed_fingerprint": current.to_json(),
                    "session_fingerprint": self._fingerprint.to_json(),
                },
                retryable=True,
            )


def _array_attributes(
    array: np.ndarray[Any, np.dtype[np.generic]],
    fingerprint: SourceFingerprint,
) -> dict[str, JsonValue]:
    return {
        "format": "NPY",
        "source_fingerprint": fingerprint.to_json(),
        "byte_order": array.dtype.byteorder,
        "dtype_descriptor": str(array.dtype.descr if array.dtype.fields else array.dtype),
        "fortran_order": bool(array.flags.f_contiguous and not array.flags.c_contiguous),
        "c_contiguous": bool(array.flags.c_contiguous),
        "f_contiguous": bool(array.flags.f_contiguous),
        "memory_mapped": isinstance(array, np.memmap),
    }


def _estimate_nbytes(
    dtype: np.dtype[np.generic],
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


def _load_candidate(path: Path) -> np.ndarray[Any, np.dtype[np.generic]]:
    try:
        loaded = np.load(path, allow_pickle=False, mmap_mode="r")
    except ValueError as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="Candidate NPY payload cannot be loaded safely.",
            operation="source.npy.validate_payload",
            details={"path": str(path), "allow_pickle": False},
            cause=exc,
        ) from exc
    if isinstance(loaded, np.lib.npyio.NpzFile):
        loaded.close()
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="Candidate payload is not a single NPY array.",
            operation="source.npy.validate_payload",
            details={"path": str(path)},
        )
    candidate = np.asarray(loaded)
    if candidate.dtype.hasobject:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="Object dtype NPY payload is rejected.",
            operation="source.npy.validate_payload",
            details={"path": str(path), "allow_pickle": False},
        )
    return candidate


def _validate_candidate_array(
    candidate: np.ndarray[Any, np.dtype[np.generic]],
    *,
    expected: np.ndarray[Any, np.dtype[np.generic]],
    original: np.ndarray[Any, np.dtype[np.generic]],
    patches: tuple[EditPatch, ...],
) -> None:
    if candidate.shape != expected.shape or candidate.dtype != expected.dtype:
        raise DataViewerError(
            code=ErrorCode.READ_FAILED,
            message="NPY replacement validation found shape or dtype drift.",
            operation="source.npy.validate_payload",
            details={
                "expected_shape": _json_shape(expected.shape),
                "candidate_shape": _json_shape(candidate.shape),
                "expected_dtype": str(expected.dtype),
                "candidate_dtype": str(candidate.dtype),
            },
        )
    _verify_new_values(candidate, expected, patches)
    _verify_representative_unchanged_value(candidate, original, patches)


def _verify_old_values(
    array: np.ndarray[Any, np.dtype[np.generic]],
    patches: tuple[EditPatch, ...],
) -> None:
    for patch_index, patch in enumerate(patches):
        if not isinstance(patch, CellPatch):
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="NPY persistence supports cell patches only in v1.",
                operation="source.npy.verify_old_values",
                resource_id=patch.resource_id,
                details={"patch_type": type(patch).__name__},
            )
        _validate_array_patch(array, patch, operation="source.npy.verify_old_values")
        observed = fingerprint_value(_normalize_numpy_value(array[patch.coordinate]))
        if observed != patch.old_value_fingerprint:
            raise DataViewerError(
                code=ErrorCode.EDIT_CONFLICT,
                message="NPY patch old value no longer matches the source.",
                operation="source.npy.verify_old_values",
                resource_id=patch.resource_id,
                details={
                    "patch_index": patch_index,
                    "expected_fingerprint": patch.old_value_fingerprint,
                    "observed_fingerprint": observed,
                },
            )


def _verify_new_values(
    candidate: np.ndarray[Any, np.dtype[np.generic]],
    expected: np.ndarray[Any, np.dtype[np.generic]],
    patches: tuple[EditPatch, ...],
) -> None:
    for patch_index, patch in enumerate(patches):
        if not isinstance(patch, CellPatch):
            continue
        observed = _normalize_numpy_value(candidate[patch.coordinate])
        expected_value = _normalize_numpy_value(expected[patch.coordinate])
        if observed != expected_value:
            raise DataViewerError(
                code=ErrorCode.READ_FAILED,
                message="NPY post-write verification failed.",
                operation="source.npy.verify_new_values",
                resource_id=patch.resource_id,
                details={"patch_index": patch_index},
            )


def _verify_representative_unchanged_value(
    candidate: np.ndarray[Any, np.dtype[np.generic]],
    original: np.ndarray[Any, np.dtype[np.generic]],
    patches: tuple[EditPatch, ...],
) -> None:
    if candidate.shape == ():
        return
    if 0 in candidate.shape:
        return
    changed = {
        patch.coordinate
        for patch in patches
        if isinstance(patch, CellPatch)
    }
    coordinate = tuple(0 for _ in candidate.shape)
    if coordinate in changed:
        return
    if _normalize_numpy_value(candidate[coordinate]) != _normalize_numpy_value(original[coordinate]):
        raise DataViewerError(
            code=ErrorCode.READ_FAILED,
            message="NPY replacement validation found an unintended value change.",
            operation="source.npy.verify_unchanged",
            details={"coordinate": _json_shape(coordinate)},
        )


def _apply_numpy_patches(
    array: np.ndarray[Any, np.dtype[np.generic]],
    patches: tuple[EditPatch, ...],
) -> None:
    for patch in patches:
        if not isinstance(patch, CellPatch):
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="NPY persistence supports cell patches only in v1.",
                operation="source.npy.apply_patches",
                resource_id=patch.resource_id,
                details={"patch_type": type(patch).__name__},
            )
        _validate_array_patch(array, patch, operation="source.npy.apply_patches")
        cast(Any, array)[patch.coordinate] = _cast_numpy_value(
            patch.new_value,
            array.dtype,
        )


def _cast_numpy_value(value: object, dtype: np.dtype[Any]) -> object:
    target = np.dtype(dtype)
    if target.fields:
        if not isinstance(value, dict):
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Structured NPY cells require a mapping patch value.",
                operation="source.npy.cast_value",
                details={"dtype": str(target)},
            )
        field_names = tuple(target.fields)
        if tuple(sorted(value)) != tuple(sorted(field_names)):
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Structured NPY patch fields do not match target dtype.",
                operation="source.npy.cast_value",
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
    if patch.resource_id.node_path != ARRAY_NODE_PATH:
        raise _resource_not_found(patch.resource_id, operation=operation)
    if len(patch.coordinate) != array.ndim:
        raise DataViewerError(
            code=ErrorCode.SELECTION_INVALID,
            message="NPY patch coordinate rank does not match array rank.",
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
                message="NPY patch coordinate is outside array bounds.",
                operation=operation,
                resource_id=patch.resource_id,
                details={"axis": axis, "index": index, "dimension": int(array.shape[axis])},
            )


def _validate_changeset_source(changeset: ChangeSet, *, source_uri: str) -> None:
    for patch in changeset.patches:
        if patch.resource_id.source_uri != source_uri:
            raise DataViewerError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="NPY changeset targets a different source.",
                operation="source.npy.apply_change_set",
                resource_id=patch.resource_id,
                details={"expected_source_uri": source_uri},
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
    return SourceFingerprint(
        size_bytes=stat.st_size,
        modified_time_ns=stat.st_mtime_ns,
    )


def _json_shape(shape: tuple[int, ...]) -> list[JsonValue]:
    return [int(item) for item in shape]


def _resource_not_found(
    resource_id: ResourceId,
    *,
    operation: str,
) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.RESOURCE_NOT_FOUND,
        message="Requested NPY resource was not found.",
        operation=operation,
        resource_id=resource_id,
        details={"resource_id": resource_id.to_json()},
    )


def _raise_if_cancelled(
    cancellation: object,
    *,
    operation: str,
) -> None:
    if getattr(cancellation, "is_cancelled", False):
        raise DataViewerError(
            code=ErrorCode.READ_CANCELLED,
            message="NPY source operation was cancelled.",
            operation=operation,
            retryable=True,
        )


__all__ = ["NPYSourceSession", "NumpyPersistenceResult"]
