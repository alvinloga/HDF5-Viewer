"""HDF5 SourceAdapter descriptor for Data Viewer v1."""

from __future__ import annotations

from pathlib import Path

import h5py

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.sources.api import DATASOURCE_API_VERSION, ProbeResult

from .session import HDF5SourceSession

HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"


class HDF5Adapter:
    """HDF5 adapter descriptor."""

    adapter_id = "data-viewer.hdf5"
    api_version = DATASOURCE_API_VERSION
    extensions = (".h5", ".hdf5", ".hdf", ".h5py")

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        """Validate candidate HDF5 files by signature."""

        suffix = path.suffix.lower()
        if suffix not in self.extensions:
            return None
        if not header.startswith(HDF5_SIGNATURE):
            return None
        return ProbeResult(
            adapter_id=self.adapter_id,
            confidence=95,
            detected_format="HDF5",
            reason=f"{path.name} has a valid HDF5 container signature.",
        )

    def open(self, path: Path, *, cancellation) -> HDF5SourceSession:
        """Open one source-owned HDF5 session."""

        if getattr(cancellation, "is_cancelled", False):
            raise DataViewerError(
                code=ErrorCode.READ_CANCELLED,
                message="HDF5 open was cancelled.",
                operation="sources.hdf5.open",
                details={"path": str(path)},
                retryable=True,
            )

        if getattr(cancellation, "raise_if_cancelled", None) is not None:
            cancellation.raise_if_cancelled()

        try:
            if not h5py.is_hdf5(path):
                raise DataViewerError(
                    code=ErrorCode.SOURCE_MALFORMED,
                    message="File is not a valid HDF5 container.",
                    operation="sources.hdf5.open",
                    details={"path": str(path)},
                )
            return HDF5SourceSession(path)
        except DataViewerError:
            raise
        except OSError as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Unable to open HDF5 source.",
                operation="sources.hdf5.open",
                details={
                    "path": str(path),
                    "adapter_id": self.adapter_id,
                },
                cause=exc,
            ) from exc
        except Exception as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Could not open HDF5 source.",
                operation="sources.hdf5.open",
                details={"path": str(path)},
                cause=exc,
            ) from exc


__all__ = ["HDF5Adapter", "HDF5_SIGNATURE"]
