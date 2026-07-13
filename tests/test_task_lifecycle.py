"""Contracts for cooperative task lifecycle and cancellation primitives."""

from __future__ import annotations

import threading

import pytest

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.tasks import (
    CallbackDispatcher,
    CancellationToken,
    TaskProgress,
    TaskRecord,
    TaskState,
    TaskTransitionError,
)


def test_task_runs_to_one_successful_terminal_result() -> None:
    task = TaskRecord.create(
        operation="read",
        owner_id="document-1",
        request_generation=3,
    )

    assert task.snapshot().state == TaskState.QUEUED

    running = task.start()
    terminal = task.succeed({"rows": 10})

    assert running.state == TaskState.RUNNING
    assert terminal.state == TaskState.SUCCEEDED
    assert terminal.result == {"rows": 10}
    assert terminal.matches(owner_id="document-1", request_generation=3)
    assert not terminal.matches(owner_id="document-1", request_generation=4)

    with pytest.raises(TaskTransitionError, match="terminal"):
        task.fail(DataViewerError(code=ErrorCode.TASK_FAILED, message="late", operation="read"))


def test_running_task_cancels_cooperatively() -> None:
    token = CancellationToken()
    task = TaskRecord.create(
        operation="read",
        owner_id="document-1",
        request_generation=1,
        cancellation=token,
    )

    task.start()
    cancelling = task.request_cancel()

    assert cancelling.state == TaskState.CANCELLING
    assert token.is_cancelled
    with pytest.raises(DataViewerError) as exc_info:
        token.raise_if_cancelled()
    assert exc_info.value.code == ErrorCode.TASK_CANCELLED

    terminal = task.cancelled()
    assert terminal.state == TaskState.CANCELLED

    with pytest.raises(TaskTransitionError, match="terminal"):
        task.succeed("late")


def test_queued_task_can_cancel_without_running() -> None:
    task = TaskRecord.create(
        operation="open",
        owner_id="document-1",
        request_generation=1,
    )

    terminal = task.request_cancel()

    assert terminal.state == TaskState.CANCELLED
    assert task.cancellation.is_cancelled


def test_illegal_transitions_are_rejected() -> None:
    task = TaskRecord.create(
        operation="read",
        owner_id="document-1",
        request_generation=1,
    )

    with pytest.raises(TaskTransitionError):
        task.succeed("not running")

    task.start()
    with pytest.raises(TaskTransitionError):
        task.start()

    with pytest.raises(ValueError, match="requires an error"):
        task.fail(None)  # type: ignore[arg-type]
    assert task.snapshot().state == TaskState.RUNNING

    task.fail(DataViewerError(code=ErrorCode.TASK_FAILED, message="failed", operation="read"))
    with pytest.raises(TaskTransitionError, match="terminal"):
        task.cancelled()


def test_progress_updates_are_thread_safe_and_validated() -> None:
    task = TaskRecord.create(
        operation="read",
        owner_id="document-1",
        request_generation=1,
    )
    task.start()

    errors: list[BaseException] = []

    def worker(offset: int) -> None:
        try:
            for index in range(10):
                task.report_progress(
                    completed=offset + index,
                    total=100,
                    message=f"chunk-{offset + index}",
                )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(index * 10,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    progress = task.snapshot().progress

    assert errors == []
    assert isinstance(progress, TaskProgress)
    assert 0 <= progress.completed < 40
    assert progress.total == 100

    with pytest.raises(ValueError, match="completed"):
        task.report_progress(completed=-1, total=100, message="bad")


def test_state_callbacks_are_marshaled_through_injected_dispatcher() -> None:
    queued_callbacks: list[object] = []
    dispatcher = CallbackDispatcher(queued_callbacks.append)
    task = TaskRecord.create(
        operation="read",
        owner_id="document-1",
        request_generation=1,
        dispatcher=dispatcher,
    )
    observed: list[TaskState] = []
    task.add_listener(lambda snapshot: observed.append(snapshot.state))

    task.start()

    assert observed == []
    assert len(queued_callbacks) == 1
    queued_callbacks.pop(0)()
    assert observed == [TaskState.RUNNING]

    task.succeed("done")
    queued_callbacks.pop(0)()
    assert observed == [TaskState.RUNNING, TaskState.SUCCEEDED]
