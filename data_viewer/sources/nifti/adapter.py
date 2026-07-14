"""NIfTI SourceAdapter descriptor for Data Viewer v1."""

from __future__ import annotations

import gzip
from pathlib import Path

import nibabel as nib

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.sources.api import DATASOURCE_API_VERSION, ProbeResult

from .session import NIFTISourceSession

NIFTI_MAGIC_OFFSET = 344
NIFTI_MAGIC_VALUES = (b"n+1\x00", b"ni1\x00", b"n+2\x00", b"ni2\x00")


class NIFTIAdapter:
    """Stateless descriptor/factory for native NIfTI files."""

    adapter_id = "data-viewer.nifti"
    api_version = DATASOURCE_API_VERSION
    extensions = (".nii", ".nii.gz")

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        """Validate candidate NIfTI files by compound suffix and magic."""

        if not path.exists() or not path.is_file():
            return None
        suffix = _nifti_suffix(path)
        if suffix is None:
            return None
        prefix = _decompressed_prefix(path) if suffix == ".nii.gz" else header[:352]
        if len(prefix) < NIFTI_MAGIC_OFFSET + 4:
            return None
        if prefix[NIFTI_MAGIC_OFFSET : NIFTI_MAGIC_OFFSET + 4] not in NIFTI_MAGIC_VALUES:
            return None
        return ProbeResult(
            adapter_id=self.adapter_id,
            confidence=94,
            detected_format="NIfTI",
            reason=f"{path.name} has {suffix} suffix and a valid NIfTI magic.",
        )

    def open(self, path: Path, *, cancellation) -> NIFTISourceSession:
        """Open one source-owned NIfTI session."""

        if getattr(cancellation, "is_cancelled", False):
            raise DataViewerError(
                code=ErrorCode.READ_CANCELLED,
                message="NIfTI open was cancelled.",
                operation="sources.nifti.open",
                details={"path": str(path)},
                retryable=True,
            )
        raise_if_cancelled = getattr(cancellation, "raise_if_cancelled", None)
        if callable(raise_if_cancelled):
            raise_if_cancelled()
        try:
            return NIFTISourceSession(path)
        except DataViewerError:
            raise
        except nib.filebasedimages.ImageFileError as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="NIfTI source is malformed or unsupported.",
                operation="sources.nifti.open",
                details={"path": str(path), "adapter_id": self.adapter_id},
                cause=exc,
            ) from exc
        except Exception as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Could not open NIfTI source.",
                operation="sources.nifti.open",
                details={"path": str(path), "adapter_id": self.adapter_id},
                cause=exc,
            ) from exc


def _nifti_suffix(path: Path) -> str | None:
    lower = path.name.lower()
    if lower.endswith(".nii.gz"):
        return ".nii.gz"
    if lower.endswith(".nii"):
        return ".nii"
    return None


def _decompressed_prefix(path: Path) -> bytes:
    try:
        with gzip.open(path, "rb") as handle:
            return handle.read(352)
    except OSError:
        return b""


__all__ = ["NIFTIAdapter"]
