"""Session implementation for read-only NIfTI volume resources."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import nibabel as nib
from nibabel.orientations import aff2axcodes
import numpy as np

from data_viewer.domain import (
    DataDomain,
    DataMetadata,
    DataViewerError,
    ErrorCode,
    NodeKind,
    OperationScope,
    ReadResult,
    ResourceId,
    SourceCapability,
    SourceFingerprint,
    SpatialMetadata,
    VolumePayload,
)
from data_viewer.sources.api import NodePage, ProgressCallback, ReadRequest, ResourceNode

DEFAULT_MAX_VOXELS = 1_000_000_000
VOLUME_NODE_PATH = "/volume"


class NIFTISourceSession:
    """One owned, read-only NIfTI source session."""

    def __init__(
        self,
        path: Path,
        *,
        max_voxels: int = DEFAULT_MAX_VOXELS,
    ) -> None:
        self._path = path
        self._source_uri = path.resolve(strict=False).as_uri()
        self._closed = False
        self._fingerprint = _fingerprint(path)
        self._max_voxels = _positive(max_voxels, "max_voxels")
        try:
            self._image: Any = cast(Any, nib.load(str(path), mmap=True))
        except nib.filebasedimages.ImageFileError:
            raise
        except Exception as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="NIfTI source is malformed or unsupported.",
                operation="source.nifti.open",
                details={"path": str(path)},
                cause=exc,
            ) from exc
        self._shape = tuple(int(dim) for dim in self._image.shape)
        voxel_count = _voxel_count(self._shape)
        if voxel_count > self._max_voxels:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="NIfTI volume dimensions exceed the configured voxel budget.",
                operation="source.nifti.validate_budget",
                details={"voxel_count": voxel_count, "max_voxels": self._max_voxels},
            )
        self._spatial = _spatial_metadata(self._image)

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
            | SourceCapability.SAVE_AS
            | SourceCapability.SPATIAL_METADATA
        )

    def root(self) -> ResourceNode:
        self._ensure_open(operation="source.nifti.root")
        return ResourceNode(
            resource_id=ResourceId(self._source_uri, "/"),
            name=self._path.name,
            node_kind=NodeKind.ROOT,
            domain=DataDomain.VOLUME,
            has_children=True,
            summary=f"NIfTI volume {self._path.name}",
        )

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: object,
    ) -> NodePage:
        self._ensure_open(operation="source.nifti.list_children")
        _raise_if_cancelled(cancellation, operation="source.nifti.list_children")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        if parent != ResourceId(self._source_uri, "/"):
            raise _resource_not_found(parent, operation="source.nifti.list_children")
        start = _cursor_to_index(cursor)
        children = (
            ResourceNode(
                resource_id=ResourceId(self._source_uri, VOLUME_NODE_PATH),
                name="volume",
                node_kind=NodeKind.RESOURCE,
                domain=DataDomain.VOLUME,
                has_children=False,
                summary=f"NIfTI volume shape {self._shape}",
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
        cancellation: object,
    ) -> DataMetadata:
        self._ensure_open(operation="source.nifti.get_metadata")
        _raise_if_cancelled(cancellation, operation="source.nifti.get_metadata")
        if resource.source_uri != self._source_uri:
            raise _resource_not_found(resource, operation="source.nifti.get_metadata")
        if resource.node_path == "/":
            return DataMetadata(
                resource_id=resource,
                name=self._path.name,
                domain=DataDomain.VOLUME,
                node_kind=NodeKind.ROOT,
                shape=self._shape,
                dtype=str(self._image.get_data_dtype()),
                storage_size_bytes=self._path.stat().st_size,
                capabilities=self.capabilities,
                attributes=self._metadata_attributes(root=True),
                spatial=self._spatial,
            )
        if resource.node_path != VOLUME_NODE_PATH:
            raise _resource_not_found(resource, operation="source.nifti.get_metadata")
        return DataMetadata(
            resource_id=resource,
            name="volume",
            domain=DataDomain.VOLUME,
            node_kind=NodeKind.RESOURCE,
            shape=self._shape,
            dtype=str(self._image.get_data_dtype()),
            logical_size_bytes=_estimate_nbytes(np.dtype(self._image.get_data_dtype()), self._shape),
            storage_size_bytes=self._path.stat().st_size,
            capabilities=(
                SourceCapability.RANDOM_SLICE
                | SourceCapability.SEARCH
                | SourceCapability.SAVE_AS
                | SourceCapability.SPATIAL_METADATA
            ),
            attributes=self._metadata_attributes(root=False),
            spatial=self._spatial,
        )

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: object,
        progress: ProgressCallback,
    ) -> ReadResult:
        self._ensure_open(operation="source.nifti.read")
        _raise_if_cancelled(cancellation, operation="source.nifti.read")
        if request.resource_id != ResourceId(self._source_uri, VOLUME_NODE_PATH):
            raise _resource_not_found(request.resource_id, operation="source.nifti.read")
        if request.row_offset is not None or request.row_limit is not None or request.selected_columns:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="Row/column reads are not supported for NIfTI volumes.",
                operation="source.nifti.read",
                resource_id=request.resource_id,
            )
        if request.scope not in {OperationScope.SLICE, OperationScope.FULL}:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="NIfTI reads support SLICE or FULL scope only.",
                operation="source.nifti.read",
                resource_id=request.resource_id,
                details={"scope": request.scope.value},
            )
        normalized_result = request.selection.normalize(self._shape)
        if not normalized_result.ok:
            raise DataViewerError(
                code=ErrorCode.SELECTION_INVALID,
                message="Selection is invalid for this NIfTI volume shape.",
                operation="source.nifti.read",
                resource_id=request.resource_id,
                details={"errors": [error.to_json() for error in normalized_result.errors]},
            )
        selection = normalized_result.unwrap()
        estimated = _estimate_nbytes(np.dtype(np.float64), selection.result_shape)
        if estimated > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Requested NIfTI selection exceeds read budget.",
                operation="source.nifti.read",
                resource_id=request.resource_id,
                details={"estimated_bytes": estimated, "max_bytes": request.max_bytes},
            )
        progress(0, 1, "start")
        values = np.asarray(self._image.dataobj[selection.to_numpy_key()])
        progress(1, 1, "done")
        return ReadResult(
            payload=VolumePayload(values=values, selection=selection, spatial=self._spatial),
            scope=request.scope,
            bytes_read=int(values.nbytes),
            is_sampled=False,
            sample=request.sample,
            warnings=self._read_warnings(),
        )

    def search(
        self,
        query: str,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: object,
    ) -> NodePage:
        self._ensure_open(operation="source.nifti.search")
        _raise_if_cancelled(cancellation, operation="source.nifti.search")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        normalized = query.strip().lower()
        if not normalized:
            return NodePage(items=(), next_cursor=None, total_count=0)
        nodes: tuple[ResourceNode, ...] = (self.root(),)
        volume = ResourceNode(
            resource_id=ResourceId(self._source_uri, VOLUME_NODE_PATH),
            name="volume",
            node_kind=NodeKind.RESOURCE,
            domain=DataDomain.VOLUME,
            has_children=False,
            summary=f"NIfTI volume shape {self._shape}",
        )
        nodes = nodes + (volume,)
        matches = tuple(
            node
            for node in nodes
            if normalized in node.name.lower() or normalized in node.resource_id.node_path.lower()
        )
        start = _cursor_to_index(cursor)
        stop = min(start + page_size, len(matches))
        return NodePage(
            items=matches[start:stop],
            next_cursor=str(stop) if stop < len(matches) else None,
            total_count=len(matches),
        )

    def refresh_fingerprint(self) -> SourceFingerprint:
        self._ensure_open(operation="source.nifti.refresh_fingerprint")
        self._fingerprint = _fingerprint(self._path)
        return self._fingerprint

    def voxel_to_world(self, voxel: tuple[float, float, float]) -> tuple[float, float, float]:
        self._ensure_open(operation="source.nifti.voxel_to_world")
        vector = np.array([voxel[0], voxel[1], voxel[2], 1.0], dtype=np.float64)
        world = np.asarray(self._image.affine, dtype=np.float64) @ vector
        return (float(world[0]), float(world[1]), float(world[2]))

    def world_to_voxel(self, world: tuple[float, float, float]) -> tuple[float, float, float]:
        self._ensure_open(operation="source.nifti.world_to_voxel")
        vector = np.array([world[0], world[1], world[2], 1.0], dtype=np.float64)
        voxel = np.linalg.inv(np.asarray(self._image.affine, dtype=np.float64)) @ vector
        return (float(voxel[0]), float(voxel[1]), float(voxel[2]))

    def close(self) -> None:
        self._closed = True
        file_map = getattr(self._image, "file_map", {})
        for holder in file_map.values():
            fileobj = getattr(holder, "fileobj", None)
            if fileobj is not None:
                fileobj.close()

    def _metadata_attributes(self, *, root: bool) -> dict[str, Any]:
        header_slope, header_inter = self._image.header.get_slope_inter()
        proxy = self._image.dataobj
        proxy_slope = getattr(proxy, "slope", None)
        proxy_inter = getattr(proxy, "inter", None)
        intent_label, intent_params, intent_name = self._image.header.get_intent()
        intent_code = int(self._image.header["intent_code"])
        return {
            "format": "NIfTI",
            "native_nifti_gzip": self._path.name.lower().endswith(".nii.gz"),
            "read_only": True,
            "source_fingerprint": self._fingerprint.to_json(),
            "proxy_type": type(proxy).__name__,
            "raw_dtype": str(self._image.get_data_dtype()),
            "display_values": "scaled_proxy",
            "slope_intercept": {
                "slope": _optional_float(proxy_slope),
                "intercept": _optional_float(proxy_inter),
            },
            "header_slope_intercept": {
                "slope": _optional_float(header_slope),
                "intercept": _optional_float(header_inter),
            },
            "intent": {
                "code": intent_code,
                "label": str(intent_label),
                "name": str(intent_name),
                "parameters": [float(item) for item in intent_params],
            },
            "dimensionality": len(self._shape),
            "header": _header_summary(self._image),
            "no_resampling": True,
            "orientation_source": "affine",
            "synthetic_root": root,
        }

    def _read_warnings(self) -> tuple[str, ...]:
        proxy = self._image.dataobj
        slope = getattr(proxy, "slope", None)
        intercept = getattr(proxy, "inter", None)
        if slope not in (None, 1, 1.0) or intercept not in (None, 0, 0.0):
            return ("NIfTI values are scaled by the source proxy.",)
        return ()

    def _ensure_open(self, operation: str) -> None:
        if self._closed:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CLOSED,
                message="NIfTI source session is closed.",
                operation=operation,
                details={"source_uri": self._source_uri},
            )


def _spatial_metadata(image: Any) -> SpatialMetadata:
    affine = np.asarray(image.affine, dtype=np.float64)
    zooms = tuple(float(item) for item in image.header.get_zooms())
    units = image.header.get_xyzt_units()
    axis_codes = tuple(str(code) for code in aff2axcodes(affine))
    return SpatialMetadata(
        affine=tuple(tuple(float(value) for value in row) for row in affine),
        voxel_sizes=zooms,
        axis_codes=axis_codes,
        units=(str(units[0] or "unknown"), str(units[1] or "unknown")),
    )


def _header_summary(image: Any) -> dict[str, Any]:
    header = image.header
    return {
        "sizeof_hdr": int(header["sizeof_hdr"]),
        "datatype": int(header["datatype"]),
        "bitpix": int(header["bitpix"]),
        "dim": [int(item) for item in header["dim"].tolist()],
        "pixdim": [float(item) for item in header["pixdim"].tolist()],
        "qform_code": int(header["qform_code"]),
        "sform_code": int(header["sform_code"]),
        "xyzt_units": list(header.get_xyzt_units()),
    }


def _estimate_nbytes(dtype: np.dtype[Any], shape: tuple[int, ...]) -> int:
    count = _voxel_count(shape)
    return int(count * dtype.itemsize)


def _voxel_count(shape: tuple[int, ...]) -> int:
    count = 1
    for dim in shape:
        count *= int(dim)
    return count


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(cast(Any, value))


def _positive(value: int, label: str) -> int:
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return int(value)


def _cursor_to_index(cursor: str | None) -> int:
    try:
        start = int(cursor or 0)
    except ValueError as exc:
        raise ValueError("cursor must be a non-negative integer string") from exc
    if start < 0:
        raise ValueError("cursor must be a non-negative integer")
    return start


def _resource_not_found(resource_id: ResourceId, *, operation: str) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.RESOURCE_NOT_FOUND,
        message="Requested NIfTI resource was not found.",
        operation=operation,
        resource_id=resource_id,
        details={"resource_id": resource_id.to_json()},
    )


def _raise_if_cancelled(cancellation: object, *, operation: str) -> None:
    if getattr(cancellation, "is_cancelled", False):
        raise DataViewerError(
            code=ErrorCode.READ_CANCELLED,
            message="NIfTI source operation was cancelled.",
            operation=operation,
            retryable=True,
        )


def _fingerprint(path: Path) -> SourceFingerprint:
    try:
        stat = path.stat()
    except OSError as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Unable to stat NIfTI source.",
            operation="source.nifti.fingerprint",
            details={"path": str(path)},
            cause=exc,
        ) from exc
    return SourceFingerprint(size_bytes=stat.st_size, modified_time_ns=stat.st_mtime_ns)


__all__ = ["NIFTISourceSession"]
