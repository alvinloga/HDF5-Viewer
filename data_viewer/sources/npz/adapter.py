"""NPZ SourceAdapter descriptor for Data Viewer v1."""

from __future__ import annotations

from pathlib import Path

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.sources.api import DATASOURCE_API_VERSION, ProbeResult

from .session import NPZSourceSession

NPZ_MAGIC_PREFIX = b"PK\x03"


class NPZAdapter:
    """Stateless descriptor/factory for uncompressed NumPy ``.npz`` archives."""

    adapter_id = "data-viewer.npz"
    api_version = DATASOURCE_API_VERSION
    extensions = (".npz",)

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        """Validate candidate NPZ files by extension and bounded ZIP signature."""

        if not path.exists() or not path.is_file():
            return None
        if path.suffix.lower() not in self.extensions:
            return None
        if not header.startswith(NPZ_MAGIC_PREFIX):
            return None
        return ProbeResult(
            adapter_id=self.adapter_id,
            confidence=90,
            detected_format="NPZ",
            reason=f"{path.name} has a ZIP signature and .npz extension.",
        )

    def open(self, path: Path, *, cancellation) -> NPZSourceSession:
        """Open one source-owned NPZ session."""

        if getattr(cancellation, "is_cancelled", False):
            raise DataViewerError(
                code=ErrorCode.READ_CANCELLED,
                message="NPZ open was cancelled.",
                operation="sources.npz.open",
                details={"path": str(path)},
                retryable=True,
            )

        raise_if_cancelled = getattr(cancellation, "raise_if_cancelled", None)
        if callable(raise_if_cancelled):
            raise_if_cancelled()

        try:
            return NPZSourceSession(path)
        except DataViewerError:
            raise
        except Exception as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Could not open NPZ source.",
                operation="sources.npz.open",
                details={"path": str(path), "adapter_id": self.adapter_id},
                cause=exc,
            ) from exc


__all__ = ["NPZAdapter", "NPZ_MAGIC_PREFIX"]

