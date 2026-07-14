"""JSON source adapter with strict UTF-8 probing."""

from __future__ import annotations

import json
from pathlib import Path

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.sources import api as source_api
from data_viewer.sources.api import ProbeResult

from .session import JSONSourceSession


class JSONAdapter:
    """Stateless adapter descriptor for `.json` sources."""

    adapter_id = "data-viewer.json"
    api_version = source_api.DATASOURCE_API_VERSION
    extensions = (".json",)

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        if path.suffix.lower() != ".json":
            return None
        encoding = "utf-8-sig" if header.startswith(b"\xef\xbb\xbf") else "utf-8"
        try:
            decoded = header.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            return None
        stripped = decoded.lstrip()
        if not stripped or stripped[0] not in '{["-0123456789tfn':
            return None
        if stripped[0] == "t" and not "true".startswith(stripped[:4]):
            return None
        if stripped[0] == "f" and not "false".startswith(stripped[:5]):
            return None
        if stripped[0] == "n" and not "null".startswith(stripped[:4]):
            return None
        return ProbeResult(
            adapter_id=self.adapter_id,
            confidence=75,
            detected_format="JSON",
            reason="file has .json suffix and a JSON-looking strict UTF-8 prefix",
        )

    def open(
        self,
        path: Path,
        *,
        cancellation: source_api.CancellationToken,
    ) -> JSONSourceSession:
        if cancellation.is_cancelled:
            raise DataViewerError(
                code=ErrorCode.READ_CANCELLED,
                message="JSON open was cancelled.",
                operation="source.json.open",
                retryable=True,
            )
        try:
            return JSONSourceSession(path)
        except json.JSONDecodeError as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="JSON source is malformed.",
                operation="source.json.open",
                details={
                    "path": str(path),
                    "line": exc.lineno,
                    "column": exc.colno,
                },
                cause=exc,
            ) from exc


__all__ = ["JSONAdapter"]
