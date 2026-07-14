"""TXT source adapter with strict UTF-8 text defaults."""

from __future__ import annotations

from pathlib import Path

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.sources import api as source_api
from data_viewer.sources.api import ProbeResult

from .session import TextSourceSession


class TXTAdapter:
    """Stateless adapter descriptor for `.txt` sources."""

    adapter_id = "data-viewer.txt"
    api_version = source_api.DATASOURCE_API_VERSION
    extensions = (".txt",)

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        if path.suffix.lower() != ".txt":
            return None
        encoding = "utf-8-sig" if header.startswith(b"\xef\xbb\xbf") else "utf-8"
        try:
            header.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            return None
        return ProbeResult(
            adapter_id=self.adapter_id,
            confidence=70,
            detected_format="TXT",
            reason="file has .txt suffix and a strict UTF-8-compatible prefix",
        )

    def open(
        self,
        path: Path,
        *,
        cancellation: source_api.CancellationToken,
    ) -> TextSourceSession:
        if cancellation.is_cancelled:
            raise DataViewerError(
                code=ErrorCode.READ_CANCELLED,
                message="TXT open was cancelled.",
                operation="source.txt.open",
                retryable=True,
            )
        return TextSourceSession(path)


__all__ = ["TXTAdapter"]
