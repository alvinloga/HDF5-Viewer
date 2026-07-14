"""NPY SourceAdapter descriptor for Data Viewer v1."""

from __future__ import annotations

from pathlib import Path

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.sources.api import DATASOURCE_API_VERSION, ProbeResult

from .session import NPYSourceSession

NPY_MAGIC_PREFIX = b"\x93NUMPY"


class NPYAdapter:
    """Stateless descriptor/factory for uncompressed NumPy ``.npy`` files."""

    adapter_id = "data-viewer.npy"
    api_version = DATASOURCE_API_VERSION
    extensions = (".npy",)

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        """Validate candidate NPY files by extension and magic prefix."""

        if path.suffix.lower() not in self.extensions:
            return None
        if not header.startswith(NPY_MAGIC_PREFIX):
            return None
        return ProbeResult(
            adapter_id=self.adapter_id,
            confidence=95,
            detected_format="NPY",
            reason=f"{path.name} has a valid NumPy .npy magic prefix.",
        )

    def open(self, path: Path, *, cancellation) -> NPYSourceSession:
        """Open one source-owned NPY session."""

        if getattr(cancellation, "is_cancelled", False):
            raise DataViewerError(
                code=ErrorCode.READ_CANCELLED,
                message="NPY open was cancelled.",
                operation="sources.npy.open",
                details={"path": str(path)},
                retryable=True,
            )

        raise_if_cancelled = getattr(cancellation, "raise_if_cancelled", None)
        if callable(raise_if_cancelled):
            raise_if_cancelled()

        try:
            return NPYSourceSession(path)
        except DataViewerError:
            raise
        except Exception as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Could not open NPY source.",
                operation="sources.npy.open",
                details={"path": str(path), "adapter_id": self.adapter_id},
                cause=exc,
            ) from exc


__all__ = ["NPYAdapter", "NPY_MAGIC_PREFIX"]
