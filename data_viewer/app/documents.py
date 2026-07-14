"""Document-owned source sessions and request generation tracking."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Condition, RLock
from time import monotonic

from data_viewer.domain import (
    DataMetadata,
    DataViewerError,
    ErrorCode,
    ReadResult,
    ResourceId,
    ResourceNode,
    SourceFingerprint,
)
from data_viewer.sources import (
    CancellationToken,
    ManagedSourceSession,
    NodePage,
    ProgressCallback,
    ReadRequest,
    SourceRegistry,
)
from data_viewer.tasks import CancellationToken as TaskCancellationToken
from data_viewer.tasks import TaskRecord, TaskSnapshot, TaskTransitionError


class DocumentStatus(StrEnum):
    """Document source-session lifecycle states."""

    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class DocumentRequest:
    """A resource request bound to one document generation."""

    document_id: str
    resource_id: ResourceId
    request_generation: int


@dataclass(frozen=True, slots=True)
class DocumentSnapshot:
    """Immutable document state for app services and UI view models."""

    document_id: str
    source_uri: str
    fingerprint: SourceFingerprint
    status: DocumentStatus
    request_generation: int
    active_resource_id: ResourceId | None
    dirty_count: int
    active_task_count: int
    active_io_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", DocumentStatus(self.status))


class DocumentController:
    """Owns one source session and exposes generation-checked operations."""

    def __init__(self, session: ManagedSourceSession) -> None:
        self._session = session
        self._document_id = session.source_uri
        self._status = DocumentStatus.OPEN
        self._request_generation = 0
        self._active_resource_id: ResourceId | None = None
        self._dirty_count = 0
        self._active_io_count = 0
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = RLock()
        self._condition = Condition(self._lock)

    @classmethod
    def open_path(
        cls,
        path: Path,
        *,
        registry: SourceRegistry,
        cancellation: CancellationToken,
    ) -> "DocumentController":
        """Open a path through the registry and own the resulting session."""

        return cls(registry.open(path, cancellation=cancellation))

    @property
    def document_id(self) -> str:
        return self._document_id

    @property
    def source_uri(self) -> str:
        return self._session.source_uri

    @property
    def request_generation(self) -> int:
        with self._condition:
            return self._request_generation

    def snapshot(self) -> DocumentSnapshot:
        """Return the current immutable document snapshot."""

        with self._condition:
            return self._snapshot_locked()

    def navigate_to(self, resource_id: ResourceId) -> DocumentRequest:
        """Set active resource and invalidate older request generations."""

        if resource_id.source_uri != self.source_uri:
            raise ValueError("resource does not belong to this document")
        with self._condition:
            self._ensure_open_locked("document.navigate")
            self._request_generation += 1
            self._active_resource_id = resource_id
            self._condition.notify_all()
            return DocumentRequest(
                document_id=self._document_id,
                resource_id=resource_id,
                request_generation=self._request_generation,
            )

    def accepts_task_result(self, snapshot: TaskSnapshot) -> bool:
        """Return whether a task snapshot is still current for this document."""

        with self._condition:
            return (
                self._status is DocumentStatus.OPEN
                and snapshot.matches(
                    owner_id=self._document_id,
                    request_generation=self._request_generation,
                )
            )

    def mark_dirty(self) -> DocumentSnapshot:
        """Record one dirty hook without depending on GUI state."""

        with self._condition:
            self._ensure_not_closed_locked("document.mark_dirty")
            self._dirty_count += 1
            self._condition.notify_all()
            return self._snapshot_locked()

    def clear_dirty(self) -> DocumentSnapshot:
        """Clear dirty hook state."""

        with self._condition:
            self._ensure_not_closed_locked("document.clear_dirty")
            self._dirty_count = 0
            self._condition.notify_all()
            return self._snapshot_locked()

    def create_task(self, operation: str) -> TaskRecord:
        """Create and track an owned task for the current generation."""

        with self._condition:
            self._ensure_open_locked("document.create_task")
            task = TaskRecord.create(
                operation=operation,
                owner_id=self._document_id,
                request_generation=self._request_generation,
                cancellation=TaskCancellationToken(),
            )
            self._tasks[task.task_id] = task
            task.add_listener(self._on_task_snapshot)
            self._condition.notify_all()
            return task

    @contextmanager
    def acquire_io_lease(
        self,
        *,
        cancellation: CancellationToken,
    ) -> Iterator[None]:
        """Hold a bounded I/O lease that prevents source close until released."""

        _raise_if_cancelled(cancellation, operation="document.acquire_io_lease")
        with self._condition:
            self._ensure_open_locked("document.acquire_io_lease")
            self._active_io_count += 1
            self._condition.notify_all()
        try:
            yield
        finally:
            with self._condition:
                self._active_io_count -= 1
                self._condition.notify_all()

    def root(self, *, cancellation: CancellationToken) -> ResourceNode:
        with self.acquire_io_lease(cancellation=cancellation):
            return self._session.root()

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: CancellationToken,
    ) -> NodePage:
        with self.acquire_io_lease(cancellation=cancellation):
            return self._session.list_children(
                parent,
                cursor=cursor,
                page_size=page_size,
                cancellation=cancellation,
            )

    def get_metadata(
        self,
        resource: ResourceId,
        *,
        cancellation: CancellationToken,
    ) -> DataMetadata:
        with self.acquire_io_lease(cancellation=cancellation):
            return self._session.get_metadata(resource, cancellation=cancellation)

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: CancellationToken,
        progress: ProgressCallback,
    ) -> ReadResult:
        with self.acquire_io_lease(cancellation=cancellation):
            return self._session.read(
                request,
                cancellation=cancellation,
                progress=progress,
            )

    def search(
        self,
        query: str,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: CancellationToken,
    ) -> NodePage:
        with self.acquire_io_lease(cancellation=cancellation):
            return self._session.search(
                query,
                cursor=cursor,
                page_size=page_size,
                cancellation=cancellation,
            )

    def close(self, *, timeout: float | None = None) -> DocumentSnapshot:
        """Cancel owned tasks, wait for tasks/leases, and close once."""

        deadline = monotonic() + timeout if timeout is not None else None
        with self._condition:
            if self._status is DocumentStatus.CLOSED:
                return self._snapshot_locked()
            self._status = DocumentStatus.CLOSING
            self._cancel_active_tasks_locked()
            self._condition.notify_all()
            while self._active_io_count > 0 or self._tasks:
                remaining = None if deadline is None else deadline - monotonic()
                if remaining is not None and remaining <= 0:
                    raise DataViewerError(
                        code=ErrorCode.TASK_FAILED,
                        message="Document close timed out while waiting for work.",
                        operation="document.close",
                        details={
                            "active_io_count": self._active_io_count,
                            "active_task_count": len(self._tasks),
                        },
                    )
                self._condition.wait(timeout=remaining)

        self._session.close()
        with self._condition:
            self._status = DocumentStatus.CLOSED
            self._condition.notify_all()
            return self._snapshot_locked()

    def _on_task_snapshot(self, snapshot: TaskSnapshot) -> None:
        if not snapshot.is_terminal:
            return
        with self._condition:
            self._tasks.pop(snapshot.task_id, None)
            self._condition.notify_all()

    def _cancel_active_tasks_locked(self) -> None:
        for task in tuple(self._tasks.values()):
            try:
                task.request_cancel()
            except TaskTransitionError:
                if task.snapshot().is_terminal:
                    self._tasks.pop(task.task_id, None)
                else:
                    raise

    def _ensure_open_locked(self, operation: str) -> None:
        if self._status is not DocumentStatus.OPEN:
            raise _closed_error(operation, self._document_id)

    def _ensure_not_closed_locked(self, operation: str) -> None:
        if self._status is DocumentStatus.CLOSED:
            raise _closed_error(operation, self._document_id)

    def _snapshot_locked(self) -> DocumentSnapshot:
        return DocumentSnapshot(
            document_id=self._document_id,
            source_uri=self._session.source_uri,
            fingerprint=self._session.fingerprint,
            status=self._status,
            request_generation=self._request_generation,
            active_resource_id=self._active_resource_id,
            dirty_count=self._dirty_count,
            active_task_count=len(self._tasks),
            active_io_count=self._active_io_count,
        )


def _closed_error(operation: str, document_id: str) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.SOURCE_CLOSED,
        message="Document source session is not open.",
        operation=operation,
        details={"document_id": document_id},
    )


def _raise_if_cancelled(
    cancellation: CancellationToken,
    *,
    operation: str,
) -> None:
    if cancellation.is_cancelled:
        raise DataViewerError(
            code=ErrorCode.READ_CANCELLED,
            message="Document operation was cancelled.",
            operation=operation,
            retryable=True,
        )


__all__ = [
    "DocumentController",
    "DocumentRequest",
    "DocumentSnapshot",
    "DocumentStatus",
]
