"""Task state machine, progress, and immutable snapshots."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from threading import RLock
from typing import Any
from uuid import uuid4

from data_viewer.domain.errors import DataViewerError

from .cancellation import CancellationToken
from .dispatcher import CallbackDispatcher


class TaskState(StrEnum):
    """Legal task lifecycle states."""

    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = frozenset(
    {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED}
)


class TaskTransitionError(RuntimeError):
    """Raised when a task state transition is illegal."""


@dataclass(frozen=True, slots=True)
class TaskProgress:
    """Immutable task progress value."""

    completed: int = 0
    total: int | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.completed, bool) or self.completed < 0:
            raise ValueError("progress completed must be non-negative")
        if self.total is not None and (
            isinstance(self.total, bool) or self.total < 0 or self.total < self.completed
        ):
            raise ValueError("progress total must be non-negative and >= completed")


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    """Immutable task state snapshot."""

    task_id: str
    operation: str
    owner_id: str
    request_generation: int
    state: TaskState
    progress: TaskProgress
    result: Any = None
    error: DataViewerError | None = None

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task ID must not be empty")
        if not self.operation:
            raise ValueError("task operation must not be empty")
        if not self.owner_id:
            raise ValueError("task owner ID must not be empty")
        if isinstance(self.request_generation, bool) or self.request_generation < 0:
            raise ValueError("task request generation must be non-negative")
        object.__setattr__(self, "state", TaskState(self.state))

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def matches(self, *, owner_id: str, request_generation: int) -> bool:
        return self.owner_id == owner_id and self.request_generation == request_generation


TaskListener = Callable[[TaskSnapshot], None]


class TaskRecord:
    """Thread-safe task state record."""

    def __init__(
        self,
        *,
        task_id: str,
        operation: str,
        owner_id: str,
        request_generation: int,
        cancellation: CancellationToken,
        dispatcher: CallbackDispatcher,
    ) -> None:
        if not task_id:
            raise ValueError("task ID must not be empty")
        if not operation:
            raise ValueError("task operation must not be empty")
        if not owner_id:
            raise ValueError("task owner ID must not be empty")
        if isinstance(request_generation, bool) or request_generation < 0:
            raise ValueError("task request generation must be non-negative")
        self.task_id = task_id
        self.operation = operation
        self.owner_id = owner_id
        self.request_generation = request_generation
        self.cancellation = cancellation
        self._dispatcher = dispatcher
        self._lock = RLock()
        self._state = TaskState.QUEUED
        self._progress = TaskProgress(message="Queued")
        self._result: Any = None
        self._error: DataViewerError | None = None
        self._listeners: list[TaskListener] = []

    @classmethod
    def create(
        cls,
        *,
        operation: str,
        owner_id: str,
        request_generation: int,
        task_id: str | None = None,
        cancellation: CancellationToken | None = None,
        dispatcher: CallbackDispatcher | None = None,
    ) -> "TaskRecord":
        return cls(
            task_id=task_id or str(uuid4()),
            operation=operation,
            owner_id=owner_id,
            request_generation=request_generation,
            cancellation=cancellation or CancellationToken(),
            dispatcher=dispatcher or CallbackDispatcher(),
        )

    def add_listener(self, listener: TaskListener) -> None:
        with self._lock:
            self._listeners.append(listener)

    def snapshot(self) -> TaskSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def start(self) -> TaskSnapshot:
        return self._transition(TaskState.RUNNING)

    def request_cancel(self) -> TaskSnapshot:
        with self._lock:
            self.cancellation.cancel()
            if self._state is TaskState.QUEUED:
                return self._transition_locked(TaskState.CANCELLED)
            if self._state is TaskState.RUNNING:
                return self._transition_locked(TaskState.CANCELLING)
            if self._state is TaskState.CANCELLING:
                return self._snapshot_locked()
            raise TaskTransitionError("cannot cancel a terminal task")

    def cancelled(self) -> TaskSnapshot:
        return self._transition(TaskState.CANCELLED)

    def succeed(self, result: Any) -> TaskSnapshot:
        return self._transition(TaskState.SUCCEEDED, result=result)

    def fail(self, error: DataViewerError) -> TaskSnapshot:
        return self._transition(TaskState.FAILED, error=error)

    def report_progress(
        self,
        *,
        completed: int,
        total: int | None,
        message: str = "",
    ) -> TaskSnapshot:
        progress = TaskProgress(completed=completed, total=total, message=message)
        with self._lock:
            if self._state in TERMINAL_STATES:
                raise TaskTransitionError("cannot report progress for a terminal task")
            self._progress = progress
            snapshot = self._snapshot_locked()
            listeners = tuple(self._listeners)
        self._publish(snapshot, listeners)
        return snapshot

    def _transition(
        self,
        new_state: TaskState,
        *,
        result: Any = None,
        error: DataViewerError | None = None,
    ) -> TaskSnapshot:
        with self._lock:
            return self._transition_locked(new_state, result=result, error=error)

    def _transition_locked(
        self,
        new_state: TaskState,
        *,
        result: Any = None,
        error: DataViewerError | None = None,
    ) -> TaskSnapshot:
        new_state = TaskState(new_state)
        _validate_transition(self._state, new_state)
        if new_state is TaskState.FAILED and error is None:
            raise ValueError("failed task requires an error")
        if new_state is not TaskState.FAILED and error is not None:
            raise ValueError("only failed tasks may carry an error")
        self._state = new_state
        if new_state is TaskState.SUCCEEDED:
            self._result = result
            self._error = None
        elif new_state is TaskState.FAILED:
            self._result = None
            self._error = error
        elif new_state is TaskState.CANCELLED:
            self._result = None
            self._error = None
        snapshot = self._snapshot_locked()
        listeners = tuple(self._listeners)
        self._publish(snapshot, listeners)
        return snapshot

    def _snapshot_locked(self) -> TaskSnapshot:
        return TaskSnapshot(
            task_id=self.task_id,
            operation=self.operation,
            owner_id=self.owner_id,
            request_generation=self.request_generation,
            state=self._state,
            progress=self._progress,
            result=self._result,
            error=self._error,
        )

    def _publish(
        self,
        snapshot: TaskSnapshot,
        listeners: tuple[TaskListener, ...],
    ) -> None:
        for listener in listeners:
            self._dispatcher.dispatch(listener, snapshot)


def _validate_transition(current: TaskState, new_state: TaskState) -> None:
    if current in TERMINAL_STATES:
        raise TaskTransitionError("cannot transition from a terminal task")
    legal = {
        TaskState.QUEUED: {TaskState.RUNNING, TaskState.CANCELLED},
        TaskState.RUNNING: {
            TaskState.CANCELLING,
            TaskState.SUCCEEDED,
            TaskState.FAILED,
        },
        TaskState.CANCELLING: {TaskState.CANCELLED},
    }
    if new_state not in legal[current]:
        raise TaskTransitionError(
            f"illegal task transition from {current.value} to {new_state.value}"
        )
