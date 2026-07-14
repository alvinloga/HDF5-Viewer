"""YAML source adapter with strict UTF-8 probing and safe loading."""

from __future__ import annotations

from pathlib import Path

import yaml

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.sources import api as source_api
from data_viewer.sources.api import ProbeResult

from .session import YAMLSourceSession


class YAMLAdapter:
    """Stateless adapter descriptor for `.yaml` and `.yml` sources."""

    adapter_id = "data-viewer.yaml"
    api_version = source_api.DATASOURCE_API_VERSION
    extensions = (".yaml", ".yml")

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        if path.suffix.lower() not in self.extensions:
            return None
        encoding = "utf-8-sig" if header.startswith(b"\xef\xbb\xbf") else "utf-8"
        try:
            header.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            return None
        return ProbeResult(
            adapter_id=self.adapter_id,
            confidence=70,
            detected_format="YAML",
            reason="file has YAML suffix and a strict UTF-8 prefix",
        )

    def open(
        self,
        path: Path,
        *,
        cancellation: source_api.CancellationToken,
    ) -> YAMLSourceSession:
        if cancellation.is_cancelled:
            raise DataViewerError(
                code=ErrorCode.READ_CANCELLED,
                message="YAML open was cancelled.",
                operation="source.yaml.open",
                retryable=True,
            )
        try:
            return YAMLSourceSession(path)
        except yaml.YAMLError as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="YAML source is malformed or uses unsupported tags.",
                operation="source.yaml.open",
                details={"path": str(path)},
                cause=exc,
            ) from exc


__all__ = ["YAMLAdapter"]
