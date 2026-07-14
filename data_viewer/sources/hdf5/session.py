"""Session implementation for HDF5 resources in Data Viewer v1."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
import posixpath
from pathlib import Path
import shutil
import tempfile
from typing import cast

import h5py
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
    SourceCapability,
    SourceFingerprint,
)
from data_viewer.editing import (
    AttributePatch,
    CellPatch,
    ChangeSet,
    EditPatch,
    fingerprint_value,
)
from data_viewer.editing.review import SaveStrategy
from data_viewer.persistence.transaction import AtomicReplacementService
from data_viewer.tasks import CancellationToken as TaskCancellationToken
from data_viewer.sources.api import NodePage, ProgressCallback, ReadRequest, ResourceNode

type HDF5PersistenceFailureInjector = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class HDF5PersistenceResult:
    """Result of applying one HDF5 changeset."""

    strategy: SaveStrategy
    source_fingerprint: SourceFingerprint
    changed_coordinates: int
    warnings: tuple[str, ...] = ()
    recovery_backup_path: Path | None = None


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
        return (
            SourceCapability.HIERARCHY
            | SourceCapability.SEARCH
            | SourceCapability.EDIT_PATCH
            | SourceCapability.ATOMIC_REWRITE
        )

    def root(self) -> ResourceNode:
        self._ensure_open(operation="source.hdf5.root")
        file = self._h5_file()
        return ResourceNode(
            resource_id=ResourceId(self._source_uri, "/"),
            name=self._path.name,
            node_kind=NodeKind.ROOT,
            domain=DataDomain.HIERARCHICAL_ARRAY,
            has_children=bool(file.keys()),
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
        file = self._h5_file()
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
                attributes=_read_attributes(file.attrs),
                storage_size_bytes=self._path.stat().st_size,
            )

        parent_group = _parent_group(file, resource.node_path)
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
                capabilities=SourceCapability.NONE,
                attributes={
                    "link_type": "external",
                    "link_filename": link.filename or "",
                    "link_path": link.path,
                    "target_found": False,
                },
            )

        if isinstance(link, h5py.SoftLink):
            target_found = _soft_link_has_target(
                parent_group.file,
                parent_path=parent_group.name or "/",
                link=link,
                child_name=child_name,
            )
            return DataMetadata(
                resource_id=resource,
                name=child_name,
                domain=DataDomain.METADATA,
                node_kind=NodeKind.RESOURCE,
                capabilities=SourceCapability.NONE,
                attributes={
                    "link_type": "soft",
                    "link_path": link.path,
                    "target_found": target_found,
                },
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
                capabilities=SourceCapability.HIERARCHY | SourceCapability.SEARCH,
                attributes=_read_attributes(child.attrs),
            )

        if isinstance(child, h5py.Dataset):
            attributes = dict(_read_attributes(child.attrs))
            attributes["hdf5_layout"] = _read_dataset_layout(child)
            return DataMetadata(
                resource_id=resource,
                name=child_name,
                domain=DataDomain.ARRAY,
                node_kind=NodeKind.RESOURCE,
                shape=tuple(int(dim) for dim in child.shape),
                dtype=str(child.dtype),
                logical_size_bytes=_safe_nbytes(child),
                storage_size_bytes=_safe_dataset_storage_bytes(child),
                capabilities=(
                    SourceCapability.RANDOM_SLICE
                    | SourceCapability.SEARCH
                    | SourceCapability.EDIT_PATCH
                ),
                attributes=attributes,
            )

        return DataMetadata(
            resource_id=resource,
            name=child_name,
            domain=DataDomain.METADATA,
            node_kind=NodeKind.RESOURCE,
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
        file = self._h5_file()
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

        parent_group = _parent_group(file, request.resource_id.node_path)
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
        values = _read_dataset_values(
            dataset=child,
            selection=selection,
        )
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

    def apply_change_set(
        self,
        changeset: ChangeSet,
        *,
        cancellation: object,
        replacement_service: AtomicReplacementService | None = None,
        failure_injector: HDF5PersistenceFailureInjector | None = None,
    ) -> HDF5PersistenceResult:
        """Apply one reviewed changeset using the safest valid HDF5 strategy."""

        self._ensure_open(operation="source.hdf5.apply_change_set")
        _raise_if_cancelled(cancellation, operation="source.hdf5.apply_change_set")
        _validate_changeset_source(changeset, source_uri=self._source_uri)
        if changeset.is_clean:
            raise ValueError("changeset must contain at least one patch")

        self._assert_unchanged(changeset.source_fingerprint)
        strategy = self._select_persistence_strategy(changeset)
        if strategy is SaveStrategy.IN_PLACE:
            return self._apply_in_place(
                changeset,
                cancellation=cancellation,
                failure_injector=failure_injector,
            )
        return self._apply_by_replacement(
            changeset,
            cancellation=cancellation,
            replacement_service=replacement_service or AtomicReplacementService(),
            failure_injector=failure_injector,
        )

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

    def _h5_file(self) -> h5py.File:
        if self._file is None:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="HDF5 file handle is unavailable.",
                operation="source.hdf5.file_handle",
                details={"source_uri": self._source_uri},
            )
        return self._file

    def _open_file(self, mode: str = "r") -> None:
        try:
            self._file = h5py.File(self._path, mode)
        except OSError as exc:
            self._closed = True
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Unable to open HDF5 source.",
                operation="source.hdf5.open",
                details={"path": str(self._path)},
                cause=exc,
            ) from exc

    def _close_file_handle(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def _reopen_read_only(self) -> None:
        self._close_file_handle()
        self._open_file("r")

    def _resolve_object(self, node_path: str) -> h5py.Group | h5py.Dataset:
        file = self._h5_file()
        if node_path == "/":
            return file["/"]
        try:
            return file[node_path]
        except (KeyError, OSError) as exc:
            raise _resource_not_found(
                ResourceId(self._source_uri, node_path),
                operation="source.hdf5.resolve_object",
            ) from exc

    def _assert_unchanged(self, expected: SourceFingerprint) -> None:
        current = _fingerprint(self._path)
        if current != expected or self._fingerprint != expected:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CHANGED,
                message="HDF5 source changed before save; refusing to overwrite.",
                operation="source.hdf5.apply_change_set",
                details={
                    "expected_fingerprint": expected.to_json(),
                    "observed_fingerprint": current.to_json(),
                    "session_fingerprint": self._fingerprint.to_json(),
                },
                retryable=True,
            )

    def _select_persistence_strategy(self, changeset: ChangeSet) -> SaveStrategy:
        if all(isinstance(patch, CellPatch) for patch in changeset.patches):
            for patch in changeset.patches:
                assert isinstance(patch, CellPatch)
                if not self._can_cell_patch_in_place(patch):
                    return SaveStrategy.REPLACEMENT
            return SaveStrategy.IN_PLACE
        return SaveStrategy.REPLACEMENT

    def _apply_in_place(
        self,
        changeset: ChangeSet,
        *,
        cancellation: object,
        failure_injector: HDF5PersistenceFailureInjector | None,
    ) -> HDF5PersistenceResult:
        backup_path = self._create_in_place_backup()
        changed_coordinates = sum(isinstance(patch, CellPatch) for patch in changeset.patches)
        try:
            _invoke_hdf5_injector(failure_injector, "in_place_precheck")
            self._close_file_handle()
            self._open_file("r+")
            file = self._h5_file()
            _raise_if_cancelled(cancellation, operation="source.hdf5.apply_in_place")
            _verify_old_values(file, changeset.patches)
            _invoke_hdf5_injector(failure_injector, "in_place_write")
            _apply_hdf5_patches(file, changeset.patches)
            file.flush()
            _fsync_path(self._path)
            _invoke_hdf5_injector(failure_injector, "in_place_verify")
            _verify_new_values(file, changeset.patches)
            self._reopen_read_only()
            self._fingerprint = _fingerprint(self._path)
            _unlink_if_exists(backup_path)
            return HDF5PersistenceResult(
                strategy=SaveStrategy.IN_PLACE,
                source_fingerprint=self._fingerprint,
                changed_coordinates=changed_coordinates,
                warnings=(
                    "HDF5 was updated in place after same-directory backup and coordinate verification.",
                ),
            )
        except DataViewerError as exc:
            self._recover_after_failed_in_place(backup_path)
            raise _integrity_warning_error(
                exc,
                backup_path=backup_path,
                strategy=SaveStrategy.IN_PLACE,
            ) from exc
        except Exception as exc:
            self._recover_after_failed_in_place(backup_path)
            raise _integrity_warning_error(
                exc,
                backup_path=backup_path,
                strategy=SaveStrategy.IN_PLACE,
            ) from exc

    def _apply_by_replacement(
        self,
        changeset: ChangeSet,
        *,
        cancellation: object,
        replacement_service: AtomicReplacementService,
        failure_injector: HDF5PersistenceFailureInjector | None,
    ) -> HDF5PersistenceResult:
        changed_coordinates = sum(isinstance(patch, CellPatch) for patch in changeset.patches)
        estimated_output_bytes = self._path.stat().st_size

        def write_payload(temp_path: Path) -> None:
            _invoke_hdf5_injector(failure_injector, "replacement_write")
            shutil.copy2(self._path, temp_path)
            with h5py.File(temp_path, "r+") as target:
                _verify_old_values(target, changeset.patches)
                _apply_hdf5_patches(target, changeset.patches)
                target.flush()

        def validate_payload(path: Path) -> SourceFingerprint:
            _invoke_hdf5_injector(failure_injector, "replacement_validate")
            with h5py.File(path, "r") as target:
                _verify_new_values(target, changeset.patches)
                _verify_representative_unchanged_values(target, changeset.patches)
            return _fingerprint(path)

        self._close_file_handle()
        try:
            result = replacement_service.run_replacement(
                source_path=self._path,
                destination=self._path,
                write_payload=write_payload,
                validate_payload=validate_payload,
                expected_source_fingerprint=changeset.source_fingerprint,
                estimated_output_bytes=estimated_output_bytes,
                cancellation=cast(TaskCancellationToken, cancellation),
            )
        finally:
            self._open_file("r")

        self._fingerprint = result.destination_fingerprint
        return HDF5PersistenceResult(
            strategy=SaveStrategy.REPLACEMENT,
            source_fingerprint=self._fingerprint,
            changed_coordinates=changed_coordinates,
            warnings=("HDF5 was rewritten through verified atomic replacement.",),
        )

    def _can_cell_patch_in_place(self, patch: CellPatch) -> bool:
        operation = "source.hdf5.plan_in_place"
        dataset = _require_direct_dataset(
            self._h5_file(),
            patch.resource_id,
            operation=operation,
        )
        _validate_coordinate(
            dataset,
            patch.coordinate,
            resource_id=patch.resource_id,
            operation=operation,
        )
        return not dataset.dtype.fields and dataset.dtype.kind != "O"

    def _create_in_place_backup(self) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=self._path.parent,
            delete=False,
            prefix=f".{self._path.name}.dv-h5ip-",
            suffix=".bak",
        ) as handle:
            backup_path = Path(handle.name)
        shutil.copy2(self._path, backup_path)
        _fsync_path(backup_path)
        return backup_path

    def _recover_after_failed_in_place(self, backup_path: Path) -> None:
        try:
            self._reopen_read_only()
            self._fingerprint = _fingerprint(self._path)
        except Exception:
            self._close_file_handle()
        if not backup_path.exists():
            return


def _validate_changeset_source(changeset: ChangeSet, *, source_uri: str) -> None:
    for patch in changeset.patches:
        if patch.resource_id.source_uri != source_uri:
            raise ValueError("all HDF5 patches must target this source session")


def _invoke_hdf5_injector(
    injector: HDF5PersistenceFailureInjector | None,
    step: str,
) -> None:
    if injector is not None:
        injector(step)


def _require_direct_dataset(
    file: h5py.File,
    resource: ResourceId,
    *,
    operation: str,
) -> h5py.Dataset:
    if resource.node_path == "/":
        raise DataViewerError(
            code=ErrorCode.CAPABILITY_UNAVAILABLE,
            message="HDF5 root is not an editable dataset.",
            operation=operation,
            resource_id=resource,
        )

    try:
        parent = _parent_group(file, resource.node_path)
        child_name = _node_name(resource.node_path)
        link = parent.get(child_name, getlink=True)
    except (KeyError, OSError, ValueError) as exc:
        raise _resource_not_found(resource, operation=operation) from exc

    if not isinstance(link, h5py.HardLink):
        raise DataViewerError(
            code=ErrorCode.CAPABILITY_UNAVAILABLE,
            message="Only directly linked HDF5 datasets can be edited.",
            operation=operation,
            resource_id=resource,
            details={"link_type": type(link).__name__},
        )

    try:
        target = parent[child_name]
    except (KeyError, OSError) as exc:
        raise _resource_not_found(resource, operation=operation) from exc
    if not isinstance(target, h5py.Dataset):
        raise DataViewerError(
            code=ErrorCode.CAPABILITY_UNAVAILABLE,
            message="Only HDF5 datasets can receive cell patches.",
            operation=operation,
            resource_id=resource,
            details={"target_type": type(target).__name__},
        )
    return target


def _require_attribute_target(
    file: h5py.File,
    resource: ResourceId,
    *,
    operation: str,
) -> h5py.File | h5py.Group | h5py.Dataset:
    if resource.node_path == "/":
        return file
    try:
        target = file[resource.node_path]
    except (KeyError, OSError) as exc:
        raise _resource_not_found(resource, operation=operation) from exc
    if not isinstance(target, (h5py.Group, h5py.Dataset)):
        raise DataViewerError(
            code=ErrorCode.CAPABILITY_UNAVAILABLE,
            message="Only HDF5 files, groups, or datasets can receive attribute patches.",
            operation=operation,
            resource_id=resource,
            details={"target_type": type(target).__name__},
        )
    return target


def _validate_coordinate(
    dataset: h5py.Dataset,
    coordinate: tuple[int, ...],
    *,
    resource_id: ResourceId,
    operation: str,
) -> None:
    shape = tuple(int(dim) for dim in dataset.shape)
    if len(coordinate) != len(shape):
        raise DataViewerError(
            code=ErrorCode.SELECTION_INVALID,
            message="Patch coordinate rank does not match HDF5 dataset rank.",
            operation=operation,
            resource_id=resource_id,
            details={"coordinate": list(coordinate), "shape": list(shape)},
        )
    for axis, (index, size) in enumerate(zip(coordinate, shape, strict=True)):
        if index < 0 or index >= size:
            raise DataViewerError(
                code=ErrorCode.SELECTION_INVALID,
                message="Patch coordinate is outside HDF5 dataset bounds.",
                operation=operation,
                resource_id=resource_id,
                details={
                    "axis": axis,
                    "index": index,
                    "size": size,
                    "shape": list(shape),
                },
            )


def _verify_old_values(file: h5py.File, patches: tuple[EditPatch, ...]) -> None:
    for patch_index, patch in enumerate(patches):
        observed: str | None
        expected: str | None
        if isinstance(patch, CellPatch):
            dataset = _require_direct_dataset(
                file,
                patch.resource_id,
                operation="source.hdf5.verify_old_cell",
            )
            _validate_coordinate(
                dataset,
                patch.coordinate,
                resource_id=patch.resource_id,
                operation="source.hdf5.verify_old_cell",
            )
            observed = _fingerprint_hdf5_value(dataset[patch.coordinate])
            expected = patch.old_value_fingerprint
        elif isinstance(patch, AttributePatch):
            target = _require_attribute_target(
                file,
                patch.resource_id,
                operation="source.hdf5.verify_old_attribute",
            )
            has_attribute = patch.name in target.attrs
            observed = (
                _fingerprint_hdf5_value(target.attrs[patch.name])
                if has_attribute
                else None
            )
            expected = patch.old_value_fingerprint
        else:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="HDF5 persistence does not support text patches.",
                operation="source.hdf5.verify_old_values",
                resource_id=patch.resource_id,
                details={"patch_type": type(patch).__name__},
            )

        if observed != expected:
            raise DataViewerError(
                code=ErrorCode.EDIT_CONFLICT,
                message="HDF5 patch old value no longer matches the source.",
                operation="source.hdf5.verify_old_values",
                resource_id=patch.resource_id,
                details={
                    "patch_index": patch_index,
                    "expected_fingerprint": expected,
                    "observed_fingerprint": observed,
                    "patch_type": type(patch).__name__,
                },
            )


def _verify_new_values(file: h5py.File, patches: tuple[EditPatch, ...]) -> None:
    for patch_index, patch in enumerate(patches):
        if isinstance(patch, CellPatch):
            dataset = _require_direct_dataset(
                file,
                patch.resource_id,
                operation="source.hdf5.verify_new_cell",
            )
            observed = _normalize_hdf5_value(dataset[patch.coordinate])
            expected = _normalize_hdf5_value(
                _cast_cell_value(patch.new_value, dataset.dtype)
            )
        elif isinstance(patch, AttributePatch):
            target = _require_attribute_target(
                file,
                patch.resource_id,
                operation="source.hdf5.verify_new_attribute",
            )
            if patch.new_value is None:
                if patch.name not in target.attrs:
                    continue
                observed = _normalize_hdf5_value(target.attrs[patch.name])
                expected = None
            else:
                observed = _normalize_hdf5_value(target.attrs[patch.name])
                expected = _normalize_hdf5_value(patch.new_value)
        else:
            continue

        if observed != expected:
            raise DataViewerError(
                code=ErrorCode.READ_FAILED,
                message="HDF5 post-write verification failed.",
                operation="source.hdf5.verify_new_values",
                resource_id=patch.resource_id,
                details={
                    "patch_index": patch_index,
                    "patch_type": type(patch).__name__,
                },
            )


def _verify_representative_unchanged_values(
    file: h5py.File,
    patches: tuple[EditPatch, ...],
) -> None:
    changed_cells = {
        (patch.resource_id.node_path, patch.coordinate)
        for patch in patches
        if isinstance(patch, CellPatch)
    }
    affected_paths = sorted({patch.resource_id.node_path for patch in patches})
    for node_path in affected_paths:
        if node_path == "/":
            continue
        try:
            target = file[node_path]
        except (KeyError, OSError) as exc:
            raise DataViewerError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="HDF5 validation could not reopen an affected resource.",
                operation="source.hdf5.verify_unchanged",
                details={"node_path": node_path},
                cause=exc,
            ) from exc
        if not isinstance(target, h5py.Dataset) or target.shape == ():
            continue
        coordinate = tuple(0 for _ in target.shape)
        if (node_path, coordinate) in changed_cells:
            continue
        _ = target[coordinate]


def _apply_hdf5_patches(file: h5py.File, patches: tuple[EditPatch, ...]) -> None:
    for patch in patches:
        if isinstance(patch, CellPatch):
            dataset = _require_direct_dataset(
                file,
                patch.resource_id,
                operation="source.hdf5.apply_cell_patch",
            )
            dataset[patch.coordinate] = _cast_cell_value(patch.new_value, dataset.dtype)
        elif isinstance(patch, AttributePatch):
            target = _require_attribute_target(
                file,
                patch.resource_id,
                operation="source.hdf5.apply_attribute_patch",
            )
            if patch.new_value is None:
                if patch.name in target.attrs:
                    del target.attrs[patch.name]
            else:
                target.attrs[patch.name] = _cast_attribute_value(patch.new_value)
        else:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="HDF5 persistence does not support text patches.",
                operation="source.hdf5.apply_patches",
                resource_id=patch.resource_id,
                details={"patch_type": type(patch).__name__},
            )


def _cast_cell_value(value: object, dtype: np.dtype) -> object:
    target = np.dtype(dtype)
    if target.fields:
        if not isinstance(value, dict):
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Compound HDF5 cells require a mapping patch value.",
                operation="source.hdf5.cast_cell_value",
                details={"dtype": str(target)},
            )
        field_names = tuple(target.fields)
        if tuple(sorted(value)) != tuple(sorted(field_names)):
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Compound HDF5 patch fields do not match target dtype.",
                operation="source.hdf5.cast_cell_value",
                details={
                    "expected_fields": cast(
                        list[JsonValue],
                        [str(field_name) for field_name in field_names],
                    ),
                    "received_fields": cast(
                        list[JsonValue],
                        sorted(str(key) for key in value),
                    ),
                },
            )
        return np.array(tuple(value[name] for name in field_names), dtype=target)[()]
    return np.array(value, dtype=target)[()]


def _cast_attribute_value(value: object) -> object:
    if isinstance(value, dict):
        return np.array(tuple(value[key] for key in sorted(value)))
    if isinstance(value, (list, tuple)):
        return np.array(value)
    return value


def _fingerprint_hdf5_value(value: object) -> str:
    return fingerprint_value(_normalize_hdf5_value(value))


def _normalize_hdf5_value(value: object) -> object:
    if isinstance(value, np.void) and value.dtype.fields:
        return {
            field_name: _normalize_hdf5_value(value[field_name])
            for field_name in value.dtype.fields
        }
    if isinstance(value, np.ndarray):
        if value.ndim == 0:
            return _normalize_hdf5_value(value.item())
        return [_normalize_hdf5_value(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _normalize_hdf5_value(value.item())
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, tuple):
        return tuple(_normalize_hdf5_value(item) for item in value)
    if isinstance(value, list):
        return [_normalize_hdf5_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_hdf5_value(item) for key, item in value.items()}
    return value


def _integrity_warning_error(
    error: BaseException,
    *,
    backup_path: Path,
    strategy: SaveStrategy,
) -> DataViewerError:
    if isinstance(error, DataViewerError):
        code = error.code
        message = error.message
        operation = error.operation
        resource_id = error.resource_id
        cause = error.cause
    else:
        code = ErrorCode.READ_FAILED
        message = "HDF5 in-place persistence failed; source requires integrity inspection."
        operation = "source.hdf5.apply_change_set"
        resource_id = None
        cause = error

    details = {
        "strategy": strategy.value,
        "integrity_warning": True,
        "change_log_retained": True,
        "recovery_backup_path": str(backup_path),
    }
    if isinstance(error, DataViewerError):
        details["cause_code"] = error.code.value
    return DataViewerError(
        code=code,
        message=message,
        operation=operation,
        resource_id=resource_id,
        details=details,
        cause=cause,
    )


def _fsync_path(path: Path) -> None:
    with path.open("rb+") as handle:
        handle.flush()
        handle_fd = handle.fileno()
        os.fsync(handle_fd)


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


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
        if not _soft_link_has_target(
            parent_object.file,
            parent_path=parent_object.name or "/",
            link=link,
            child_name=child_name,
        ):
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
        child_count = len(tuple(target.keys()))
        return ResourceNode(
            resource_id=ResourceId(source_uri, child_path),
            name=child_name,
            node_kind=NodeKind.CONTAINER,
            domain=DataDomain.HIERARCHICAL_ARRAY,
            has_children=child_count > 0,
            summary=f"group ({child_count} direct children)",
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


def _read_dataset_values(
    *,
    dataset: h5py.Dataset,
    selection: NormalizedSelection,
) -> np.ndarray:
    """Read one bounded dataset slice using one direct dataset indexing call."""

    key = selection.to_numpy_key()
    data = dataset[key]
    return np.asarray(data)


def _read_attributes(attributes: h5py.AttributeManager) -> dict[str, JsonValue]:
    return {key: _serialize_attribute(value) for key, value in attributes.items()}


def _read_dataset_layout(dataset: h5py.Dataset) -> dict[str, JsonValue]:
    return {
        "chunks": _serialize_shape(dataset.chunks),
        "compression": _serialize_attribute(dataset.compression),
        "compression_opts": _serialize_attribute(dataset.compression_opts),
        "fill_value": _serialize_attribute(dataset.fillvalue),
    }


def _serialize_shape(shape: tuple[int, ...] | None) -> list[JsonValue] | None:
    if shape is None:
        return None
    return [int(dim) for dim in shape]


def _soft_link_has_target(
    source_file: h5py.File,
    *,
    parent_path: str,
    child_name: str,
    link: h5py.SoftLink,
) -> bool:
    base_path = _parent_path(f"{parent_path.rstrip('/')}/{child_name}")
    target_path = _join_h5_paths(base_path, link.path)
    return _path_has_target(source_file, target_path)


def _path_has_target(
    source_file: h5py.File,
    path: str,
    *,
    depth_remaining: int = 32,
    seen: set[str] | None = None,
) -> bool:
    normalized = _normalize_h5_path(path)
    if normalized == "/":
        return True
    if depth_remaining <= 0:
        return False

    if seen is None:
        seen = set()

    if not normalized.startswith("/"):
        return False
    segments = _split_h5_path(normalized)
    current_group = source_file["/"]
    current_path = "/"

    for index, segment in enumerate(segments):
        child_path = _join_h5_paths(current_path, segment)
        if child_path in seen:
            return False

        try:
            link = current_group.get(segment, getlink=True)
        except (KeyError, OSError, TypeError):
            return False
        if link is None:
            return False
        if isinstance(link, h5py.ExternalLink):
            return False

        if isinstance(link, h5py.SoftLink):
            next_seen = seen | {child_path}
            resolved = _join_h5_paths(_parent_path(child_path), link.path)
            if index + 1 < len(segments):
                resolved = _join_h5_paths(resolved, "/".join(segments[index + 1 :]))
            return _path_has_target(
                source_file,
                resolved,
                depth_remaining=depth_remaining - 1,
                seen=next_seen,
            )

        if index == len(segments) - 1:
            return True

        try:
            next_object = current_group[segment]
        except (KeyError, OSError, TypeError):
            return False
        if not isinstance(next_object, h5py.Group):
            return False

        current_group = next_object
        current_path = child_path
        seen = seen | {child_path}

    return True


def _normalize_h5_path(path: str) -> str:
    normalized = posixpath.normpath(path.replace("\\", "/"))
    if normalized == ".":
        return "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized


def _split_h5_path(path: str) -> tuple[str, ...]:
    normalized = _normalize_h5_path(path)
    if normalized == "/":
        return ()
    return tuple(segment for segment in normalized.split("/") if segment not in {"", "."})


def _join_h5_paths(*parts: str) -> str:
    joined = "/".join(part.strip("/") for part in parts if part)
    if not joined:
        return "/"
    return _normalize_h5_path(joined)


def _serialize_attribute(value: object) -> JsonValue:
    if isinstance(value, np.ndarray):
        if value.ndim == 0:
            value = value.item()
        else:
            return [_serialize_attribute(item) for item in value.tolist()]

    if isinstance(value, np.generic):
        try:
            return value.item()
        except (TypeError, ValueError):
            return str(value)

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", errors="replace")
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
    details: dict[str, JsonValue] | None = None,
) -> DataViewerError:
    payload: dict[str, JsonValue] = {"resource_id": resource_id.to_json()}
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
