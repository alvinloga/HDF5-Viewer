"""Background export queue and diagnostics bundle contracts."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from data_viewer.app.diagnostics import (
    DiagnosticEvent,
    DiagnosticsBundleService,
    DiagnosticsRedactor,
    PluginInventoryItem,
)
from data_viewer.app.export_queue import ExportQueueService
from data_viewer.domain import (
    ArrayPayload,
    DataViewerError,
    ErrorCode,
    ResourceId,
    SelectionSpec,
    SourceFingerprint,
)
from data_viewer.exporting import (
    ExportOutcome,
    ExportScope,
    ExportTargetFormat,
    ExportValueMode,
    build_export_plan,
)
from data_viewer.exporting.receipt import receipt_from_plan
from data_viewer.tasks import TaskState


def _fingerprint() -> SourceFingerprint:
    return SourceFingerprint(size_bytes=12, modified_time_ns=34, content_tag="abc")


def _resource(tmp_path: Path) -> ResourceId:
    return ResourceId.from_file(tmp_path / "source.h5", "/array")


def _plan(tmp_path: Path, name: str = "out.npy"):
    return build_export_plan(
        source_fingerprint=_fingerprint(),
        resource_id=_resource(tmp_path),
        target_path=tmp_path / name,
        target_format=ExportTargetFormat.NPY,
        scope=ExportScope.FULL_RESOURCE,
        value_mode=ExportValueMode.RAW,
    )


def _array_payload(values: list[int]) -> ArrayPayload:
    array = np.array(values)
    return ArrayPayload(
        values=array,
        original_shape=array.shape,
        selection=SelectionSpec.all(),
    )


def test_export_queue_runs_multiple_jobs_and_retains_receipts(tmp_path: Path) -> None:
    queue = ExportQueueService(application_version="test-version")
    payload = _array_payload([1, 2, 3])

    first = queue.enqueue(_plan(tmp_path, "first.npy"), payload, owner_id="source:1")
    second = queue.enqueue(_plan(tmp_path, "second.npy"), payload, owner_id="source:1")

    assert first.state is TaskState.QUEUED
    assert second.state is TaskState.QUEUED

    first_result = queue.run_next()
    second_result = queue.run_next()

    assert first_result is not None
    assert second_result is not None
    assert first_result.state is TaskState.SUCCEEDED
    assert second_result.state is TaskState.SUCCEEDED
    assert queue.pending_count == 0
    assert [receipt.outcome for receipt in queue.receipts()] == [
        ExportOutcome.SUCCEEDED,
        ExportOutcome.SUCCEEDED,
    ]
    assert (tmp_path / "first.npy").exists()
    assert (tmp_path / "second.npy").exists()


def test_export_queue_cancels_queued_job_without_writing(tmp_path: Path) -> None:
    queue = ExportQueueService(application_version="test-version")
    snapshot = queue.enqueue(
        _plan(tmp_path, "cancelled.npy"),
        _array_payload([1]),
        owner_id="source:1",
    )

    cancelled = queue.cancel(snapshot.task_id)

    assert cancelled.state is TaskState.CANCELLED
    assert queue.run_next() is None
    assert not (tmp_path / "cancelled.npy").exists()
    assert queue.receipts() == ()


def test_export_queue_failure_links_problem_to_task_and_retry_succeeds(tmp_path: Path) -> None:
    failures = {"remaining": 1}

    class FlakyExportService:
        def export_payload(self, plan, payload, *, cancellation=None):
            if failures["remaining"]:
                failures["remaining"] -= 1
                return receipt_from_plan(
                    plan,
                    outcome=ExportOutcome.FAILED,
                    application_version="test-version",
                    error_code=ErrorCode.WORKSPACE_IO_FAILED,
                    error_message="temporary disk error",
                )
            return receipt_from_plan(
                plan,
                outcome=ExportOutcome.SUCCEEDED,
                application_version="test-version",
                bytes_written=4,
            )

    queue = ExportQueueService(
        application_version="test-version",
        export_service=FlakyExportService(),
    )
    first = queue.enqueue(
        _plan(tmp_path, "retry.npy"),
        _array_payload([1]),
        owner_id="source:1",
    )

    failed = queue.run_next()
    problems = queue.problems()
    retry = queue.retry(first.task_id)
    succeeded = queue.run_next()

    assert failed is not None and failed.state is TaskState.FAILED
    assert problems[0].task_id == first.task_id
    assert problems[0].source_uri.endswith("source.h5")
    assert problems[0].resource_path == "/array"
    assert problems[0].error_code is ErrorCode.WORKSPACE_IO_FAILED
    assert retry.attempt == 2
    assert succeeded is not None and succeeded.state is TaskState.SUCCEEDED
    assert [receipt.outcome for receipt in queue.receipts()] == [
        ExportOutcome.FAILED,
        ExportOutcome.SUCCEEDED,
    ]


def test_diagnostics_bundle_preview_redacts_paths_and_includes_inventory(tmp_path: Path) -> None:
    secret_root = tmp_path / "private"
    secret_file = secret_root / "source.h5"
    error = DataViewerError(
        code=ErrorCode.WORKSPACE_IO_FAILED,
        message="Could not open source.",
        operation="workspace.open",
        details={"path": str(secret_file), "sample": ["not source data"]},
    )
    event = DiagnosticEvent.from_error(
        error,
        context={"source": str(secret_file)},
        timestamp_utc="2026-07-15T00:00:00Z",
    )
    service = DiagnosticsBundleService(
        app_version="test-version",
        platform="Windows-test",
        python_version="3.test",
        redactor=DiagnosticsRedactor((str(secret_root),)),
    )
    bundle = service.build_bundle(
        plugins=(
            PluginInventoryItem(
                plugin_id="org.dataviewer.profile",
                name="Profile",
                version="1.0.0",
                api_version=1,
                enabled=True,
            ),
        ),
        recent_events=(event,),
    )

    preview = bundle.preview_json()
    payload = json.loads(preview)

    assert payload["app_version"] == "test-version"
    assert payload["platform"] == "Windows-test"
    assert payload["plugins"][0]["plugin_id"] == "org.dataviewer.profile"
    assert "<redacted>/source.h5" in preview
    assert str(secret_root).replace("\\", "/") not in preview
    assert payload["recent_events"][0]["error"]["details"]["sample"] == ["not source data"]
