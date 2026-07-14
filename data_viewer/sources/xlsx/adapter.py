"""Safe XLSX SourceAdapter descriptor for Data Viewer v1."""

from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile

import openpyxl

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.sources.api import DATASOURCE_API_VERSION, ProbeResult

from .constants import ZIP_SIGNATURE
from .session import XLSXSourceSession


class XLSXAdapter:
    """Stateless descriptor/factory for read-only `.xlsx` workbooks."""

    adapter_id = "data-viewer.xlsx"
    api_version = DATASOURCE_API_VERSION
    extensions = (".xlsx",)

    def probe(self, path: Path, header: bytes) -> ProbeResult | None:
        """Validate candidate XLSX files by suffix and OOXML ZIP signature."""

        if not path.exists() or not path.is_file():
            return None
        if path.suffix.lower() not in self.extensions:
            return None
        if not header.startswith(ZIP_SIGNATURE):
            return None
        return ProbeResult(
            adapter_id=self.adapter_id,
            confidence=82,
            detected_format="XLSX",
            reason=f"{path.name} has .xlsx suffix and an OOXML ZIP prefix.",
        )

    def open(self, path: Path, *, cancellation) -> XLSXSourceSession:
        """Open one source-owned safe workbook session."""

        if getattr(cancellation, "is_cancelled", False):
            raise DataViewerError(
                code=ErrorCode.READ_CANCELLED,
                message="XLSX open was cancelled.",
                operation="sources.xlsx.open",
                details={"path": str(path)},
                retryable=True,
            )
        raise_if_cancelled = getattr(cancellation, "raise_if_cancelled", None)
        if callable(raise_if_cancelled):
            raise_if_cancelled()
        try:
            return XLSXSourceSession(path)
        except DataViewerError:
            raise
        except BadZipFile as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="XLSX source is not a valid OOXML ZIP workbook.",
                operation="sources.xlsx.open",
                details={"path": str(path), "adapter_id": self.adapter_id},
                cause=exc,
            ) from exc
        except openpyxl.utils.exceptions.InvalidFileException as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="XLSX source is malformed or unsupported.",
                operation="sources.xlsx.open",
                details={"path": str(path), "adapter_id": self.adapter_id},
                cause=exc,
            ) from exc
        except Exception as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Could not open XLSX source.",
                operation="sources.xlsx.open",
                details={"path": str(path), "adapter_id": self.adapter_id},
                cause=exc,
            ) from exc


__all__ = ["XLSXAdapter"]
