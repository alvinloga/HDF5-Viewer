"""Application-level background export queue and receipt history."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Protocol

from data_viewer.domain import DataPayload, DataViewerError, ErrorCode, JsonValue
from data_viewer.exporting import ExportService
from data_viewer.exporting.plan import ExportPlan
from data_viewer.exporting.receipt import ExportOutcome, ExportReceipt
from data_viewer.tasks import TaskRecord, TaskSnapshot, TaskState


class ExportExecutor(Protocol):
    """Executor protocol used by the queue and tests."""

    def export_payload(
        self,
        plan: ExportPlan,
        payload: DataPayload | bytes | str | dict[str, Any] | list[Any],
        *,
        cancellation: object | None = None,
    ) -> ExportReceipt:
        """Execute a reviewed export plan and return a terminal receipt."""


@dataclass(frozen=True, slots=True)
class ExportQueueEntry:
    """A queued or historical export job."""

    task_id: str
    plan: ExportPlan
    owner_id: str
    attempt: int

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "task_id": self.task_id,
            "owner_id": self.owner_id,
            "attempt": self.attempt,
            "plan": self.plan.to_json(),
        }


@dataclass(frozen=True, slots=True)
class ExportProblem:
    """Problem-panel link produced by a failed export."""

    task_id: str
    source_uri: str
    resource_path: str | None
    target_path: str
    error_code: ErrorCode
    message: str

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "task_id": self.task_id,
            "source_uri": self.source_uri,
            "resource_path": self.resource_path,
            "target_path": self.target_path,
            "error_code": self.error_code.value,
            "message": self.message,
        }


@dataclass(slots=True)
class _QueuedExport:
    entry: ExportQueueEntry
    task: TaskRecord
    payload: DataPayload | bytes | str | dict[str, Any] | list[Any]


class ExportQueueService:
    """Deterministic export queue with task progress, cancellation, retry, and history."""

    def __init__(
        self,
        *,
        application_version: str,
        export_service: ExportExecutor | None = None,
    ) -> None:
        self._application_version = application_version
        self._export_service = export_service or ExportService(
            application_version=application_version
        )
        self._queue: deque[_QueuedExport] = deque()
        self._jobs: dict[str, _QueuedExport] = {}
        self._history: list[ExportQueueEntry] = []
        self._receipts: list[ExportReceipt] = []
        self._problems: list[ExportProblem] = []

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    @property
    def retained_task_count(self) -> int:
        """Number of non-pending task records still retained for retry/inspection."""

        return len(self._jobs)

    def enqueue(
        self,
        plan: ExportPlan,
        payload: DataPayload | bytes | str | dict[str, Any] | list[Any],
        *,
        owner_id: str,
        attempt: int = 1,
    ) -> TaskSnapshot:
        if attempt < 1:
            raise ValueError("export attempt must be positive")
        task = TaskRecord.create(
            operation="export",
            owner_id=owner_id,
            request_generation=attempt,
        )
        entry = ExportQueueEntry(
            task_id=task.task_id,
            plan=plan,
            owner_id=owner_id,
            attempt=attempt,
        )
        queued = _QueuedExport(entry=entry, task=task, payload=payload)
        self._queue.append(queued)
        self._jobs[task.task_id] = queued
        self._history.append(entry)
        return task.snapshot()

    def cancel(self, task_id: str) -> TaskSnapshot:
        queued = self._get_job(task_id)
        snapshot = queued.task.request_cancel()
        if snapshot.state is TaskState.CANCELLED:
            self._queue = deque(
                item for item in self._queue if item.entry.task_id != task_id
            )
        return snapshot

    def run_next(self) -> TaskSnapshot | None:
        while self._queue:
            queued = self._queue.popleft()
            snapshot = queued.task.snapshot()
            if snapshot.state is TaskState.CANCELLED:
                continue
            queued.task.start()
            queued.task.report_progress(completed=0, total=1, message="Exporting")
            receipt = self._export_service.export_payload(
                queued.entry.plan,
                queued.payload,
                cancellation=queued.task.cancellation,
            )
            self._receipts.append(receipt)
            queued.task.report_progress(completed=1, total=1, message="Finished")
            if receipt.outcome is ExportOutcome.SUCCEEDED:
                snapshot = queued.task.succeed(receipt)
                self._jobs.pop(queued.entry.task_id, None)
                return snapshot
            if receipt.outcome is ExportOutcome.CANCELLED:
                return queued.task.cancelled()
            error = DataViewerError(
                code=receipt.error_code or ErrorCode.WORKSPACE_IO_FAILED,
                message=receipt.error_message or "Export failed.",
                operation="export.queue",
                details={"task_id": queued.entry.task_id},
            )
            self._problems.append(_problem_from_receipt(queued.entry, receipt))
            return queued.task.fail(error)
        return None

    def retry(self, task_id: str) -> ExportQueueEntry:
        queued = self._get_job(task_id)
        snapshot = queued.task.snapshot()
        if snapshot.state not in {TaskState.FAILED, TaskState.CANCELLED}:
            raise ValueError("only failed or cancelled exports can be retried")
        self.enqueue(
            queued.entry.plan,
            queued.payload,
            owner_id=queued.entry.owner_id,
            attempt=queued.entry.attempt + 1,
        )
        return self._history[-1]

    def receipts(self) -> tuple[ExportReceipt, ...]:
        return tuple(self._receipts)

    def problems(self) -> tuple[ExportProblem, ...]:
        return tuple(self._problems)

    def entries(self) -> tuple[ExportQueueEntry, ...]:
        return tuple(self._history)

    def _get_job(self, task_id: str) -> _QueuedExport:
        try:
            return self._jobs[task_id]
        except KeyError as exc:
            raise KeyError(f"unknown export task: {task_id}") from exc


def _problem_from_receipt(
    entry: ExportQueueEntry,
    receipt: ExportReceipt,
) -> ExportProblem:
    resource = entry.plan.resource_id
    return ExportProblem(
        task_id=entry.task_id,
        source_uri=resource.source_uri if resource else "",
        resource_path=resource.node_path if resource else None,
        target_path=str(receipt.target_path),
        error_code=receipt.error_code or ErrorCode.WORKSPACE_IO_FAILED,
        message=receipt.error_message or "Export failed.",
    )


__all__ = [
    "ExportExecutor",
    "ExportProblem",
    "ExportQueueEntry",
    "ExportQueueService",
]
