"""Export execution service for reviewed Data Viewer export plans."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import numpy as np

from data_viewer import __version__
from data_viewer.domain import (
    ArrayPayload,
    DataPayload,
    DataViewerError,
    ErrorCode,
    StructuredPayload,
    TablePayload,
    TextPayload,
    VolumePayload,
)

from .plan import ExportPlan, ExportTargetFormat
from .receipt import ExportOutcome, ExportReceipt, receipt_from_plan


class ExportService:
    """Execute reviewed export plans and always return an outcome receipt."""

    def __init__(self, *, application_version: str = __version__) -> None:
        self._application_version = application_version

    def export_payload(
        self,
        plan: ExportPlan,
        payload: DataPayload | bytes | str | dict[str, Any] | list[Any],
        *,
        cancellation: object | None = None,
    ) -> ExportReceipt:
        """Write an export payload according to a reviewed plan."""

        try:
            _raise_if_cancelled(cancellation, operation="export.payload")
            if plan.target_path.exists() and not plan.overwrite:
                raise DataViewerError(
                    code=ErrorCode.EDIT_CONFLICT,
                    message="Export target already exists and overwrite is disabled.",
                    operation="export.payload",
                    details={"target_path": str(plan.target_path)},
                )
            bytes_written = self._write_atomically(plan, payload, cancellation=cancellation)
            return receipt_from_plan(
                plan,
                outcome=ExportOutcome.SUCCEEDED,
                application_version=self._application_version,
                bytes_written=bytes_written,
            )
        except DataViewerError as exc:
            outcome = (
                ExportOutcome.CANCELLED
                if exc.code in {ErrorCode.READ_CANCELLED, ErrorCode.TASK_CANCELLED}
                else ExportOutcome.FAILED
            )
            return receipt_from_plan(
                plan,
                outcome=outcome,
                application_version=self._application_version,
                error_code=exc.code,
                error_message=exc.message,
            )
        except Exception as exc:
            return receipt_from_plan(
                plan,
                outcome=ExportOutcome.FAILED,
                application_version=self._application_version,
                error_code=ErrorCode.WORKSPACE_IO_FAILED,
                error_message=str(exc),
            )

    def _write_atomically(
        self,
        plan: ExportPlan,
        payload: DataPayload | bytes | str | dict[str, Any] | list[Any],
        *,
        cancellation: object | None,
    ) -> int:
        target = plan.target_path.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.dv-export-",
            suffix=".tmp",
            dir=target.parent,
        )
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            _raise_if_cancelled(cancellation, operation="export.write")
            self._write_payload(temp_path, plan, payload)
            _fsync_path(temp_path)
            _raise_if_cancelled(cancellation, operation="export.replace")
            os.replace(temp_path, target)
            _fsync_directory(target.parent)
            return target.stat().st_size
        except Exception:
            _unlink_if_exists(temp_path)
            raise

    def _write_payload(
        self,
        path: Path,
        plan: ExportPlan,
        payload: DataPayload | bytes | str | dict[str, Any] | list[Any],
    ) -> None:
        if plan.target_format is ExportTargetFormat.NPY:
            with path.open("wb") as handle:
                np.save(handle, _payload_to_array(payload), allow_pickle=False)
            return
        if plan.target_format is ExportTargetFormat.CSV:
            _write_csv(path, payload)
            return
        if plan.target_format is ExportTargetFormat.JSON:
            path.write_text(
                json.dumps(_payload_to_json(payload), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return
        if plan.target_format is ExportTargetFormat.TXT:
            path.write_text(_payload_to_text(payload), encoding="utf-8")
            return
        if plan.target_format in {ExportTargetFormat.PNG, ExportTargetFormat.BINARY}:
            path.write_bytes(_payload_to_bytes(payload))
            return
        raise DataViewerError(
            code=ErrorCode.CAPABILITY_UNAVAILABLE,
            message="Unsupported export target format.",
            operation="export.write_payload",
            details={"target_format": plan.target_format.value},
        )


def _payload_to_array(payload: DataPayload | bytes | str | dict[str, Any] | list[Any]) -> np.ndarray:
    if isinstance(payload, (ArrayPayload, VolumePayload)):
        return np.asarray(payload.values)
    if isinstance(payload, TablePayload):
        return np.column_stack(payload.column_values)
    raise DataViewerError(
        code=ErrorCode.CAPABILITY_UNAVAILABLE,
        message="Only array-like payloads can be exported to NPY.",
        operation="export.payload_to_array",
    )


def _payload_to_json(payload: DataPayload | bytes | str | dict[str, Any] | list[Any]) -> Any:
    if isinstance(payload, (ArrayPayload, VolumePayload)):
        return np.asarray(payload.values).tolist()
    if isinstance(payload, TablePayload):
        return [
            {
                column.name: _json_scalar(values[row])
                for column, values in zip(payload.columns, payload.column_values, strict=True)
            }
            for row in range(payload.row_count)
        ]
    if isinstance(payload, TextPayload):
        return {"text": payload.text, "offset": payload.offset, "is_complete": payload.is_complete}
    if isinstance(payload, StructuredPayload):
        return payload.value
    if isinstance(payload, (dict, list)):
        return payload
    if isinstance(payload, str):
        return payload
    if isinstance(payload, bytes):
        return {"bytes_hex": payload.hex()}
    raise DataViewerError(
        code=ErrorCode.CAPABILITY_UNAVAILABLE,
        message="Payload cannot be converted to JSON.",
        operation="export.payload_to_json",
    )


def _payload_to_text(payload: DataPayload | bytes | str | dict[str, Any] | list[Any]) -> str:
    if isinstance(payload, TextPayload):
        return payload.text
    if isinstance(payload, str):
        return payload
    return json.dumps(_payload_to_json(payload), ensure_ascii=False, indent=2)


def _payload_to_bytes(payload: DataPayload | bytes | str | dict[str, Any] | list[Any]) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(_payload_to_json(payload), ensure_ascii=False).encode("utf-8")


def _write_csv(path: Path, payload: DataPayload | bytes | str | dict[str, Any] | list[Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if isinstance(payload, TablePayload):
            writer.writerow([column.name for column in payload.columns])
            for row in range(payload.row_count):
                writer.writerow(
                    [
                        _csv_safe_cell(values[row])
                        for values in payload.column_values
                    ]
                )
            return
        array = _payload_to_array(payload)
        if array.ndim == 0:
            writer.writerow([_csv_safe_cell(array.item())])
        elif array.ndim == 1:
            for item in array:
                writer.writerow([_csv_safe_cell(item)])
        elif array.ndim == 2:
            for row in array:
                writer.writerow([_csv_safe_cell(item) for item in row])
        else:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="CSV export supports scalar, 1D, 2D arrays, and table payloads.",
                operation="export.write_csv",
                details={"ndim": int(array.ndim)},
            )


def _csv_safe_cell(value: object) -> object:
    scalar = _json_scalar(value)
    if isinstance(scalar, str) and scalar.startswith(("=", "+", "-", "@")):
        return f"'{scalar}"
    return scalar


def _json_scalar(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _raise_if_cancelled(cancellation: object | None, *, operation: str) -> None:
    if cancellation is None:
        return
    if getattr(cancellation, "is_cancelled", False):
        raise DataViewerError(
            code=ErrorCode.TASK_CANCELLED,
            message="Export operation was cancelled.",
            operation=operation,
            retryable=True,
        )
    raise_if_cancelled = getattr(cancellation, "raise_if_cancelled", None)
    if callable(raise_if_cancelled):
        try:
            raise_if_cancelled(operation=operation)
        except TypeError:
            raise_if_cancelled()


def _fsync_path(path: Path) -> None:
    with path.open("rb+") as handle:
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


__all__ = ["ExportService"]
