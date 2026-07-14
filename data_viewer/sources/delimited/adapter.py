"""Delimited CSV/TSV SourceAdapter descriptor for Data Viewer v1."""

from __future__ import annotations

from pathlib import Path

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.sources.api import DATASOURCE_API_VERSION, ProbeResult

from .options import DelimitedTextOptions
from .session import DelimitedSourceSession


class DelimitedTextAdapter:
    """Stateless descriptor/factory for CSV and TSV table files."""

    adapter_id = "data-viewer.delimited"
    api_version = DATASOURCE_API_VERSION
    extensions = (".csv", ".tsv")

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        """Accept only known extensions whose bounded header decodes strictly."""

        suffix = path.suffix.lower()
        if suffix not in self.extensions:
            return None
        encoding = "utf-8-sig" if header.startswith(b"\xef\xbb\xbf") else "utf-8"
        try:
            header.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            return None
        detected = "TSV" if suffix == ".tsv" else "CSV"
        return ProbeResult(
            adapter_id=self.adapter_id,
            confidence=80,
            detected_format=detected,
            reason=f"{path.name} has a supported delimited extension and strict UTF-8 header.",
        )

    def open(self, path: Path, *, cancellation) -> DelimitedSourceSession:
        """Open one source-owned delimited table session with default options."""

        if getattr(cancellation, "is_cancelled", False):
            raise DataViewerError(
                code=ErrorCode.READ_CANCELLED,
                message="Delimited open was cancelled.",
                operation="sources.delimited.open",
                details={"path": str(path)},
                retryable=True,
            )

        raise_if_cancelled = getattr(cancellation, "raise_if_cancelled", None)
        if callable(raise_if_cancelled):
            raise_if_cancelled()

        try:
            return DelimitedSourceSession(
                path,
                options=DelimitedTextOptions.for_path(path),
            )
        except DataViewerError:
            raise
        except Exception as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Could not open delimited source.",
                operation="sources.delimited.open",
                details={"path": str(path), "adapter_id": self.adapter_id},
                cause=exc,
            ) from exc


__all__ = ["DelimitedTextAdapter"]
