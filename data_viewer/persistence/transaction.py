"""Verified atomic replacement transaction for editable formats."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import replace
from enum import StrEnum
from pathlib import Path
import os
import shutil
import tempfile
from typing import Any

from data_viewer.domain import SourceFingerprint
from data_viewer.domain.errors import DataViewerError, ErrorCode
from data_viewer.tasks import CancellationToken

from data_viewer.persistence.recovery import (
    RecoveryState,
    RecoveryRecord,
    clear_recovery_record,
    new_recovery_record,
    write_recovery_record,
)


class TransactionStep(StrEnum):
    """Named checkpoints for deterministic failure injection and diagnostics."""

    PRECHECK = "precheck"
    TEMP_CREATE = "temp_create"
    WRITE = "write"
    FLUSH = "flush"
    REOPEN_TEMP = "reopen_temp"
    VALIDATE_TEMP = "validate_temp"
    REPLACE = "replace"
    FSYNC_DIR = "fsync_dir"
    REOPEN_FINAL = "reopen_final"
    VALIDATE_FINAL = "validate_final"


class FilesystemAdapter:
    """Small filesystem abstraction for testability and future adapters."""

    def create_temp_in_dir(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=directory,
            delete=False,
            prefix=".dvtx-",
            suffix=".tmp",
        ) as handle:
            return Path(handle.name)

    def replace(self, source: Path, destination: Path) -> None:
        os.replace(source, destination)

    def sync_file(self, path: Path) -> None:
        with open(path, "rb+") as handle:
            handle.flush()
            os.fsync(handle.fileno())

    def sync_directory(self, path: Path) -> None:
        if os.name == "nt":
            return
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def free_bytes(self, path: Path) -> int:
        return shutil.disk_usage(path).free

    def unlink(self, path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            return


type WriteCallback = Callable[[Path], None]
type ValidateCallback = Callable[[Path], SourceFingerprint]
type FailureInjector = Callable[[TransactionStep], None]


@dataclass(frozen=True, slots=True)
class TransactionResult:
    """Result from a successful replacement transaction."""

    destination: Path
    output_bytes: int
    destination_fingerprint: SourceFingerprint
    temp_fingerprint: SourceFingerprint


def _record_error(error: BaseException | str | None) -> str | None:
    if error is None:
        return None
    if isinstance(error, str):
        return error
    return f"{type(error).__name__}: {error}"


def _raise(
    *,
    step: TransactionStep,
    operation: str,
    code: ErrorCode,
    message: str,
    cause: BaseException | None = None,
    destination: Path,
    temp: Path | None = None,
    retryable: bool | None = None,
) -> None:
    details: dict[str, Any] = {"transaction_step": step.value}
    if temp is not None:
        details["temp_path"] = str(temp)
    details["destination_path"] = str(destination)
    raise DataViewerError(
        code=code,
        message=message,
        operation=operation,
        details=details,
        retryable=retryable,
        cause=cause,
    )


class AtomicReplacementService:
    """Replacement service for v1-safe full-file writes."""

    def __init__(
        self,
        *,
        filesystem: FilesystemAdapter | None = None,
        require_same_directory: bool = True,
        safety_margin_ratio: float = 0.05,
    ) -> None:
        self._filesystem = filesystem or FilesystemAdapter()
        self._require_same_directory = require_same_directory
        self._safety_margin_ratio = safety_margin_ratio

    @property
    def safety_margin_ratio(self) -> float:
        return self._safety_margin_ratio

    def _invoke_injection(
        self,
        *,
        injector: FailureInjector | None,
        step: TransactionStep,
    ) -> None:
        if injector is None:
            return
        injector(step)

    @staticmethod
    def _fingerprint_path(path: Path) -> SourceFingerprint:
        stat = path.stat()
        return SourceFingerprint(size_bytes=stat.st_size, modified_time_ns=stat.st_mtime_ns)

    def _check_cancel(
        self,
        cancellation: CancellationToken | None,
        *,
        operation: str,
        step: TransactionStep,
    ) -> None:
        if cancellation is None:
            return
        cancellation.raise_if_cancelled(operation=f"{operation}:{step.value}")

    def _check_expected_fingerprint(
        self,
        *,
        source_path: Path | None,
        expected_source_fingerprint: SourceFingerprint | None,
        operation: str,
    ) -> None:
        if source_path is None or expected_source_fingerprint is None:
            return
        try:
            current = self._fingerprint_path(source_path)
        except OSError as exc:
            _raise(
                step=TransactionStep.PRECHECK,
                operation=operation,
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Unable to check source fingerprint before replacement.",
                cause=exc,
                destination=source_path,
            )
        if current != expected_source_fingerprint:
            _raise(
                step=TransactionStep.PRECHECK,
                operation=operation,
                code=ErrorCode.SOURCE_CHANGED,
                message="Source file changed before save; refusing to overwrite.",
                destination=source_path,
            )

    def _check_preflight_space(
        self,
        *,
        destination: Path,
        estimated_output_bytes: int | None,
        operation: str,
    ) -> None:
        if estimated_output_bytes is None:
            return
        if estimated_output_bytes < 0:
            raise ValueError("estimated_output_bytes must be non-negative")
        try:
            required = int(estimated_output_bytes * (1.0 + self._safety_margin_ratio)) + 1
            free = self._filesystem.free_bytes(destination.parent)
        except OSError as exc:
            _raise(
                step=TransactionStep.PRECHECK,
                operation=operation,
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Unable to verify free disk space before replacement.",
                cause=exc,
                destination=destination,
            )
        if free < required:
            _raise(
                step=TransactionStep.PRECHECK,
                operation=operation,
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Insufficient disk space for atomic replacement.",
                destination=destination,
            )

    def _record_step(
        self,
        destination: Path,
        record: RecoveryRecord,
        *,
        step: TransactionStep,
    ) -> RecoveryRecord:
        returned = record.with_state(
            state=RecoveryState.IN_PROGRESS,
            step=step.value,
            last_error=None,
        )
        write_recovery_record(destination, returned)
        return returned

    def _fail(
        self,
        destination: Path,
        current: RecoveryRecord | None,
        *,
        step: TransactionStep,
        message: str,
        error: BaseException | str,
        code: ErrorCode,
        temp_path: Path | None,
        retryable: bool | None = None,
        force_cleanup_temp: bool = True,
    ) -> None:
        if current is not None:
            failed = current.with_state(
                state=RecoveryState.FAILED,
                step=step.value,
                last_error=_record_error(error),
            )
            write_recovery_record(destination, failed)
            if force_cleanup_temp and temp_path is not None and temp_path.exists():
                self._filesystem.unlink(temp_path)
        _raise(
            step=step,
            operation="transaction.atomic_replace",
            code=code,
            message=message,
            cause=error if isinstance(error, BaseException) else None,
            destination=destination,
            temp=temp_path,
            retryable=retryable,
        )

    def run_replacement(
        self,
        source_path: Path | None,
        destination: Path,
        *,
        write_payload: WriteCallback,
        validate_payload: ValidateCallback,
        expected_source_fingerprint: SourceFingerprint | None = None,
        estimated_output_bytes: int | None = None,
        cancellation: CancellationToken | None = None,
        failure_injector: FailureInjector | None = None,
    ) -> TransactionResult:
        """Write payload to a sibling temporary file and atomically replace destination.

        The service writes startup-recovery markers before each critical step and
        only clears them after successful final validation.
        """

        operation = "transaction.atomic_replace"
        destination = destination.resolve()
        source_path = source_path.resolve() if source_path is not None else None
        parent = destination.parent
        parent.mkdir(parents=True, exist_ok=True)

        temp_path: Path | None = None
        record: RecoveryRecord | None = None

        self._invoke_injection(injector=failure_injector, step=TransactionStep.PRECHECK)
        self._check_cancel(cancellation, operation=operation, step=TransactionStep.PRECHECK)
        self._check_expected_fingerprint(
            source_path=source_path,
            expected_source_fingerprint=expected_source_fingerprint,
            operation=operation,
        )
        self._check_preflight_space(
            destination=destination,
            estimated_output_bytes=estimated_output_bytes,
            operation=operation,
        )

        record = new_recovery_record(
            destination=destination,
            step=TransactionStep.TEMP_CREATE.value,
            expected_fingerprint=expected_source_fingerprint,
        )

        def _fail_from_dataviewer(
            step: TransactionStep,
            error: DataViewerError,
        ) -> None:
            nonlocal record
            if record is not None:
                failed = record.with_state(
                    state=RecoveryState.FAILED,
                    step=step.value,
                    last_error=_record_error(error),
                )
                write_recovery_record(destination, failed)
                if temp_path is not None and temp_path.exists():
                    self._filesystem.unlink(temp_path)
            raise error

        def _run_step(
            *,
            step: TransactionStep,
            action: Callable[[], Any],
            code: ErrorCode,
            message: str,
            allow_cancel: bool,
            cleanup_temp: bool = True,
        ) -> Any:
            nonlocal record, temp_path
            try:
                if allow_cancel:
                    self._check_cancel(
                        cancellation,
                        operation=operation,
                        step=step,
                    )
                self._invoke_injection(injector=failure_injector, step=step)
                if allow_cancel:
                    self._check_cancel(
                        cancellation,
                        operation=operation,
                        step=step,
                    )
                result = action()
            except DataViewerError as exc:
                _fail_from_dataviewer(step, exc)
            except Exception as exc:
                self._fail(
                    destination=destination,
                    current=record,
                    step=step,
                    message=message,
                    code=code,
                    error=exc,
                    temp_path=temp_path,
                    force_cleanup_temp=cleanup_temp,
                )
            if (
                record is not None
                and step is TransactionStep.TEMP_CREATE
                and temp_path is not None
            ):
                record = replace(
                    record.with_state(
                        state=RecoveryState.IN_PROGRESS,
                        step=TransactionStep.TEMP_CREATE.value,
                        last_error=None,
                    ),
                    temp_uri=str(temp_path),
                )
                record = self._record_step(
                    destination,
                    record,
                    step=TransactionStep.TEMP_CREATE,
                )
            elif record is not None:
                record = self._record_step(destination, record, step=step)
            return result

        temp_path = _run_step(
            step=TransactionStep.TEMP_CREATE,
            action=lambda: self._filesystem.create_temp_in_dir(parent),
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Failed to create temporary replacement file.",
            allow_cancel=True,
        )
        if self._require_same_directory and temp_path.parent != parent:
            self._fail(
                destination=destination,
                current=record,
                step=TransactionStep.TEMP_CREATE,
                message="Replacement temp file could not be created in destination directory.",
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                error=RuntimeError(
                    "temporary replacement file is not in destination directory",
                ),
                temp_path=temp_path,
            )

        _run_step(
            step=TransactionStep.WRITE,
            action=lambda: write_payload(temp_path),
            code=ErrorCode.READ_FAILED,
            message="Failed to write replacement payload.",
            allow_cancel=True,
        )

        _run_step(
            step=TransactionStep.FLUSH,
            action=lambda: self._filesystem.sync_file(temp_path),
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Failed to flush temporary replacement file.",
            allow_cancel=True,
        )

        def _reopen_temp() -> None:
            if temp_path is None or not temp_path.exists():
                raise FileNotFoundError("temporary replacement file is missing")
            temp_path.stat()

        _run_step(
            step=TransactionStep.REOPEN_TEMP,
            action=_reopen_temp,
            code=ErrorCode.READ_FAILED,
            message="Temporary replacement file could not be reopened.",
            allow_cancel=True,
        )

        temp_fingerprint = _run_step(
            step=TransactionStep.VALIDATE_TEMP,
            action=lambda: validate_payload(temp_path),
            code=ErrorCode.READ_FAILED,
            message="Temporary payload validation failed.",
            allow_cancel=True,
        )
        if not isinstance(temp_fingerprint, SourceFingerprint):
            self._fail(
                destination=destination,
                current=record,
                step=TransactionStep.VALIDATE_TEMP,
                message="Validation callback returned an invalid fingerprint type.",
                code=ErrorCode.READ_FAILED,
                error=TypeError("validate_payload must return SourceFingerprint"),
                temp_path=temp_path,
            )

        _run_step(
            step=TransactionStep.REPLACE,
            action=lambda: self._filesystem.replace(temp_path, destination),
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Atomic replace failed.",
            allow_cancel=True,
        )

        _run_step(
            step=TransactionStep.FSYNC_DIR,
            action=lambda: self._filesystem.sync_directory(parent),
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Directory fsync failed after replace.",
            allow_cancel=False,
        )

        def _reopen_final() -> None:
            if not destination.exists():
                raise FileNotFoundError("destination missing after replacement")
            destination.stat()

        _run_step(
            step=TransactionStep.REOPEN_FINAL,
            action=_reopen_final,
            code=ErrorCode.READ_FAILED,
            message="Destination replacement file could not be reopened.",
            allow_cancel=False,
        )

        destination_fingerprint = _run_step(
            step=TransactionStep.VALIDATE_FINAL,
            action=lambda: validate_payload(destination),
            code=ErrorCode.READ_FAILED,
            message="Destination validation failed after replace.",
            allow_cancel=False,
        )
        if not isinstance(destination_fingerprint, SourceFingerprint):
            self._fail(
                destination=destination,
                current=record,
                step=TransactionStep.VALIDATE_FINAL,
                message="Validation callback returned an invalid destination fingerprint type.",
                code=ErrorCode.READ_FAILED,
                error=TypeError("validate_payload must return SourceFingerprint"),
                temp_path=destination,
            )

        complete = record.with_state(
            state=RecoveryState.COMPLETE,
            step=TransactionStep.VALIDATE_FINAL.value,
            last_error=None,
        )
        write_recovery_record(destination, complete)
        clear_recovery_record(destination)
        return TransactionResult(
            destination=destination,
            output_bytes=destination.stat().st_size,
            destination_fingerprint=destination_fingerprint,
            temp_fingerprint=temp_fingerprint,
        )
