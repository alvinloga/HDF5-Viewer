"""Unit tests for verified atomic replacement transactions."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_viewer.domain import DataViewerError, ErrorCode, SourceFingerprint
from data_viewer.persistence.recovery import RecoveryState, load_recovery_record
from data_viewer.persistence.transaction import (
    AtomicReplacementService,
    FilesystemAdapter,
    TransactionStep,
)
from data_viewer.tasks import CancellationToken


def _fingerprint(path: Path) -> SourceFingerprint:
    stat = path.stat()
    return SourceFingerprint(size_bytes=stat.st_size, modified_time_ns=stat.st_mtime_ns)


def _write_payload(path: Path, payload: bytes = b"replaced") -> None:
    path.write_bytes(payload)


def _validate_payload(path: Path) -> SourceFingerprint:
    if path.stat().st_size == 0:
        raise AssertionError("payload cannot be empty")
    return _fingerprint(path)


def test_run_replacement_success_updates_destination_and_clears_marker(tmp_path: Path) -> None:
    destination = tmp_path / "workspace.bin"
    source = tmp_path / "source.bin"
    source.write_bytes(b"original")
    expected = _fingerprint(source)

    service = AtomicReplacementService()
    result = service.run_replacement(
        source_path=source,
        destination=destination,
        write_payload=lambda p: _write_payload(p, b"payload"),
        validate_payload=_validate_payload,
        expected_source_fingerprint=expected,
        estimated_output_bytes=7,
    )

    assert result.destination == destination.resolve()
    assert destination.read_bytes() == b"payload"
    assert result.output_bytes == destination.stat().st_size
    assert result.destination_fingerprint == _fingerprint(destination)
    assert result.temp_fingerprint == result.destination_fingerprint
    assert load_recovery_record(destination) is None


def test_run_replacement_enforces_same_directory_temp_by_default(tmp_path: Path) -> None:
    class RemoteDirectoryFS(FilesystemAdapter):
        def __init__(self, remote_dir: Path) -> None:
            self._remote_dir = remote_dir

        def create_temp_in_dir(self, directory: Path) -> Path:
            return super().create_temp_in_dir(self._remote_dir)

    destination = tmp_path / "workspace.bin"
    source = tmp_path / "source.bin"
    source.write_bytes(b"original")
    expected = _fingerprint(source)

    service = AtomicReplacementService(filesystem=RemoteDirectoryFS(tmp_path / "staging"))
    (tmp_path / "staging").mkdir()

    with pytest.raises(DataViewerError) as exc_info:
        service.run_replacement(
            source_path=source,
            destination=destination,
            write_payload=lambda p: _write_payload(p, b"payload"),
            validate_payload=_validate_payload,
            expected_source_fingerprint=expected,
            estimated_output_bytes=7,
    )

    assert exc_info.value.code is ErrorCode.CAPABILITY_UNAVAILABLE
    assert destination.exists() is False


def test_run_replacement_allows_cross_directory_when_disabled(tmp_path: Path) -> None:
    class RemoteDirectoryFS(FilesystemAdapter):
        def __init__(self, remote_dir: Path) -> None:
            self._remote_dir = remote_dir

        def create_temp_in_dir(self, directory: Path) -> Path:
            return super().create_temp_in_dir(self._remote_dir)

    destination = tmp_path / "workspace.bin"
    source = tmp_path / "source.bin"
    source.write_bytes(b"original")
    expected = _fingerprint(source)

    service = AtomicReplacementService(
        filesystem=RemoteDirectoryFS(tmp_path / "staging"),
        require_same_directory=False,
    )
    (tmp_path / "staging").mkdir()

    result = service.run_replacement(
        source_path=source,
        destination=destination,
        write_payload=lambda p: _write_payload(p, b"payload"),
        validate_payload=_validate_payload,
        expected_source_fingerprint=expected,
        estimated_output_bytes=7,
    )

    assert result.destination == destination.resolve()
    assert destination.read_bytes() == b"payload"
    assert result.destination_fingerprint == _fingerprint(destination)


def test_run_replacement_canceled_before_precheck_does_not_create_marker(tmp_path: Path) -> None:
    destination = tmp_path / "workspace.bin"
    source = tmp_path / "source.bin"
    source.write_bytes(b"original")
    expected = _fingerprint(source)
    token = CancellationToken()
    token.cancel()

    service = AtomicReplacementService()
    with pytest.raises(DataViewerError) as exc_info:
        service.run_replacement(
            source_path=source,
            destination=destination,
            write_payload=lambda p: _write_payload(p, b"payload"),
            validate_payload=_validate_payload,
            expected_source_fingerprint=expected,
            estimated_output_bytes=7,
            cancellation=token,
        )

    assert exc_info.value.code is ErrorCode.TASK_CANCELLED
    assert load_recovery_record(destination) is None


@pytest.mark.parametrize(
    ("failure_step", "expected_code"),
    [
        (TransactionStep.TEMP_CREATE, ErrorCode.SOURCE_OPEN_FAILED),
        (TransactionStep.WRITE, ErrorCode.READ_FAILED),
        (TransactionStep.FLUSH, ErrorCode.SOURCE_OPEN_FAILED),
        (TransactionStep.REOPEN_TEMP, ErrorCode.READ_FAILED),
        (TransactionStep.VALIDATE_TEMP, ErrorCode.READ_FAILED),
        (TransactionStep.REPLACE, ErrorCode.SOURCE_OPEN_FAILED),
        (TransactionStep.FSYNC_DIR, ErrorCode.SOURCE_OPEN_FAILED),
        (TransactionStep.REOPEN_FINAL, ErrorCode.READ_FAILED),
        (TransactionStep.VALIDATE_FINAL, ErrorCode.READ_FAILED),
    ],
)
def test_run_replacement_failure_matrix_records_failed_marker_and_cleans_temporary_file(
    tmp_path: Path,
    failure_step: TransactionStep,
    expected_code: ErrorCode,
) -> None:
    destination = tmp_path / "workspace.bin"
    source = tmp_path / "source.bin"
    source.write_bytes(b"original")
    expected = _fingerprint(source)

    def inject(step: TransactionStep) -> None:
        if step == failure_step:
            raise RuntimeError(f"injection at {step.value}")

    service = AtomicReplacementService()
    with pytest.raises(DataViewerError) as exc_info:
        service.run_replacement(
            source_path=source,
            destination=destination,
            write_payload=lambda p: _write_payload(p, b"payload"),
            validate_payload=_validate_payload,
            expected_source_fingerprint=expected,
            estimated_output_bytes=7,
            failure_injector=inject,
        )

    assert exc_info.value.code is expected_code
    record = load_recovery_record(destination)
    assert record is not None
    assert record.state is RecoveryState.FAILED
    assert record.step == failure_step.value

    if failure_step in (TransactionStep.REOPEN_FINAL, TransactionStep.VALIDATE_FINAL, TransactionStep.FSYNC_DIR):
        assert destination.exists() is True
    else:
        assert destination.exists() is False
    assert not any(item.name.startswith(".dvtx-") for item in destination.parent.iterdir())


def test_run_replacement_rejects_unexpected_source_fingerprint(tmp_path: Path) -> None:
    destination = tmp_path / "workspace.bin"
    source = tmp_path / "source.bin"
    source.write_bytes(b"original")
    expected = SourceFingerprint(size_bytes=8, modified_time_ns=1)

    service = AtomicReplacementService()
    with pytest.raises(DataViewerError) as exc_info:
        service.run_replacement(
            source_path=source,
            destination=destination,
            write_payload=lambda p: _write_payload(p, b"payload"),
            validate_payload=_validate_payload,
            expected_source_fingerprint=expected,
            estimated_output_bytes=7,
        )

    assert exc_info.value.code is ErrorCode.SOURCE_CHANGED
    assert load_recovery_record(destination) is None


def test_run_replacement_respects_disk_budget_preflight(tmp_path: Path) -> None:
    class NoSpaceFilesystem(FilesystemAdapter):
        def free_bytes(self, path: Path) -> int:  # noqa: ARG002
            return 0

    destination = tmp_path / "workspace.bin"
    source = tmp_path / "source.bin"
    source.write_bytes(b"original")
    expected = _fingerprint(source)

    service = AtomicReplacementService(filesystem=NoSpaceFilesystem())
    with pytest.raises(DataViewerError) as exc_info:
        service.run_replacement(
            source_path=source,
            destination=destination,
            write_payload=lambda p: _write_payload(p, b"payload"),
            validate_payload=_validate_payload,
            expected_source_fingerprint=expected,
            estimated_output_bytes=7,
        )

    assert exc_info.value.code is ErrorCode.BUDGET_EXCEEDED


def test_run_replacement_stops_at_replace_when_cancelled(tmp_path: Path) -> None:
    destination = tmp_path / "workspace.bin"
    source = tmp_path / "source.bin"
    source.write_bytes(b"original")
    expected = _fingerprint(source)
    token = CancellationToken()

    def inject(step: TransactionStep) -> None:
        if step is TransactionStep.REPLACE:
            token.cancel()

    service = AtomicReplacementService()
    with pytest.raises(DataViewerError) as exc_info:
        service.run_replacement(
            source_path=source,
            destination=destination,
            write_payload=lambda p: _write_payload(p, b"payload"),
            validate_payload=_validate_payload,
            expected_source_fingerprint=expected,
            estimated_output_bytes=7,
            failure_injector=inject,
            cancellation=token,
        )

    assert exc_info.value.code is ErrorCode.TASK_CANCELLED
    assert destination.exists() is False


def test_run_replacement_requires_fingerprint_return_type(tmp_path: Path) -> None:
    destination = tmp_path / "workspace.bin"
    source = tmp_path / "source.bin"
    source.write_bytes(b"original")
    expected = _fingerprint(source)

    def validate_invalid_type(path: Path) -> Path:
        return path

    service = AtomicReplacementService()
    with pytest.raises(DataViewerError) as exc_info:
        service.run_replacement(
            source_path=source,
            destination=destination,
            write_payload=lambda p: _write_payload(p, b"payload"),
            validate_payload=validate_invalid_type,  # type: ignore[arg-type]
            expected_source_fingerprint=expected,
            estimated_output_bytes=7,
        )

    assert exc_info.value.code is ErrorCode.READ_FAILED
    assert "invalid fingerprint type" in exc_info.value.message
