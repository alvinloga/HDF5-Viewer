"""MATLAB MAT SourceAdapter descriptor for Data Viewer v1."""

from __future__ import annotations

from pathlib import Path

import h5py

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.sources.api import DATASOURCE_API_VERSION, ProbeResult
from data_viewer.sources.hdf5.adapter import HDF5_SIGNATURE

from .session import MATSourceSession

MATLAB_V5_HEADER_PREFIX = b"MATLAB"


class MATAdapter:
    """Stateless descriptor/factory for MATLAB ``.mat`` files."""

    adapter_id = "data-viewer.mat"
    api_version = DATASOURCE_API_VERSION
    extensions = (".mat",)

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        """Validate candidate MAT files by suffix and bounded signature checks."""

        if not path.exists() or not path.is_file():
            return None
        if path.suffix.lower() not in self.extensions:
            return None
        if header.startswith(HDF5_SIGNATURE):
            return ProbeResult(
                adapter_id=self.adapter_id,
                confidence=92,
                detected_format="MAT v7.3",
                reason=f"{path.name} has .mat suffix and an HDF5 container signature.",
            )
        if header.startswith(MATLAB_V5_HEADER_PREFIX):
            return ProbeResult(
                adapter_id=self.adapter_id,
                confidence=86,
                detected_format="MAT legacy",
                reason=f"{path.name} has .mat suffix and a MATLAB MAT-file header.",
            )
        return None

    def open(self, path: Path, *, cancellation) -> MATSourceSession:
        """Open one source-owned MAT session."""

        if getattr(cancellation, "is_cancelled", False):
            raise DataViewerError(
                code=ErrorCode.READ_CANCELLED,
                message="MAT open was cancelled.",
                operation="sources.mat.open",
                details={"path": str(path)},
                retryable=True,
            )
        raise_if_cancelled = getattr(cancellation, "raise_if_cancelled", None)
        if callable(raise_if_cancelled):
            raise_if_cancelled()
        try:
            return MATSourceSession(path, is_hdf5=h5py.is_hdf5(path))
        except DataViewerError:
            raise
        except Exception as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="Could not open MATLAB MAT source.",
                operation="sources.mat.open",
                details={"path": str(path), "adapter_id": self.adapter_id},
                cause=exc,
            ) from exc


__all__ = ["MATAdapter", "MATLAB_V5_HEADER_PREFIX"]
