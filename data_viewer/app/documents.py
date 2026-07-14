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
    ResourceId,
    DataViewerError,
    ErrorCode,
    ReadResult,
    ResourceNode,
    SourceFingerprint,
)
from data_viewer.editing.review import (
    SaveReview,
    SaveStrategy,
    build_save_review,
    build_warnings,
)
from data_viewer.editing.session import (
    EditCloseAction,
    EditSession,
    EditSessionState,
    EditSessionTransitionError,
)
from data_viewer.editing.patches import EditPatch
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
    edit_state: EditSessionState
    edit_patch_count: int
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
        self._edit_session = EditSession.create(
            source_uri=self._session.source_uri,
            source_fingerprint=self._session.fingerprint,
        )
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

    def apply_edit_patch(self, patch: EditPatch) -> DocumentSnapshot:
        """Append one edit patch and transition edit state."""

        with self._condition:
            self._ensure_open_locked("document.apply_edit_patch")
            self._edit_session = self._edit_session.with_patch(patch)
            self._condition.notify_all()
            return self._snapshot_locked()

    def undo_edit(self) -> tuple[DocumentSnapshot, EditPatch]:
        """Undo the latest edit patch."""

        with self._condition:
            self._ensure_open_locked("document.undo_edit")
            self._edit_session, patch = self._edit_session.undo()
            self._condition.notify_all()
            return self._snapshot_locked(), patch

    def redo_edit(self) -> tuple[DocumentSnapshot, EditPatch]:
        """Redo the latest undone edit patch."""

        with self._condition:
            self._ensure_open_locked("document.redo_edit")
            self._edit_session, patch = self._edit_session.redo()
            self._condition.notify_all()
            return self._snapshot_locked(), patch

    def discard_edit_changes(self) -> DocumentSnapshot:
        """Drop all unsaved edit patches."""

        with self._condition:
            self._ensure_open_locked("document.discard_edit_changes")
            self._edit_session = self._edit_session.discard()
            self._condition.notify_all()
            return self._snapshot_locked()

    def refresh_edit_fingerprint(self, *, cancellation: CancellationToken) -> DocumentSnapshot:
        """Refresh document fingerprint and update edit conflict state."""

        with self._condition:
            self._ensure_open_locked("document.refresh_edit_fingerprint")
        with self.acquire_io_lease(cancellation=cancellation):
            observed = self._session.refresh_fingerprint()
        with self._condition:
            self._edit_session = self._edit_session.refresh_fingerprint(observed)
            self._condition.notify_all()
            return self._snapshot_locked()

    def begin_edit_save(self) -> DocumentSnapshot:
        """Mark edit session as saving and block further patch edits."""

        with self._condition:
            self._ensure_open_locked("document.begin_edit_save")
            self._edit_session = self._edit_session.begin_save()
            self._condition.notify_all()
            return self._snapshot_locked()

    def mark_edit_save_success(self, fingerprint: SourceFingerprint) -> DocumentSnapshot:
        """Clear patches and return to clean after successful persistence."""

        with self._condition:
            self._ensure_open_locked("document.mark_edit_save_success")
            self._edit_session = self._edit_session.mark_save_success(fingerprint)
            self._condition.notify_all()
            return self._snapshot_locked()

    def mark_edit_save_failed(self, error: DataViewerError) -> DocumentSnapshot:
        """Keep patches and enter SAVE_FAILED after failed persistence."""

        with self._condition:
            self._ensure_open_locked("document.mark_edit_save_failed")
            self._edit_session = self._edit_session.mark_save_failed(error)
            self._condition.notify_all()
            return self._snapshot_locked()

    def build_edit_save_review(
        self,
        *,
        target_uri: str,
        strategy: SaveStrategy,
    ) -> SaveReview:
        """Build a review payload for the current change set."""

        with self._condition:
            self._ensure_open_locked("document.build_edit_save_review")
            review = build_save_review(
                self._edit_session.history.changeset,
                target_uri=target_uri,
                strategy=strategy,
            )
            return SaveReview(
                target_uri=review.target_uri,
                strategy=review.strategy,
                source_fingerprint=review.source_fingerprint,
                resources=review.resources,
                patch_count=review.patch_count,
                changed_patch_kinds=review.changed_patch_kinds,
                estimated_size_bytes=review.estimated_size_bytes,
                warnings=tuple(
                    review.warnings
                    + build_warnings(self._edit_session.history.changeset, ())
                ),
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

    def close(
        self,
        *,
        timeout: float | None = None,
        edit_close_action: EditCloseAction = EditCloseAction.DISCARD,
    ) -> DocumentSnapshot:
        """Cancel owned tasks, wait for tasks/leases, and close once."""

        deadline = monotonic() + timeout if timeout is not None else None
        with self._condition:
            if self._status is DocumentStatus.CLOSED:
                return self._snapshot_locked()
            try:
                updated_session, should_close = self._edit_session.close_action(
                    edit_close_action,
                )
            except EditSessionTransitionError as exc:
                raise DataViewerError(
                    code=ErrorCode.EDIT_CONFLICT,
                    message=str(exc),
                    operation="document.close",
                    details={
                        "edit_state": self._edit_session.state.value,
                        "edit_patch_count": self._edit_session.patch_count,
                        "edit_close_action": edit_close_action.value,
                    },
                ) from exc
            if not should_close:
                raise DataViewerError(
                    code=ErrorCode.EDIT_CONFLICT,
                    message="Document close was canceled due to unsaved changes.",
                    operation="document.close",
                    details={
                        "edit_state": self._edit_session.state.value,
                        "edit_patch_count": self._edit_session.patch_count,
                        "edit_close_action": edit_close_action.value,
                    },
                )
            self._edit_session = updated_session
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
            edit_state=self._edit_session.state,
            edit_patch_count=self._edit_session.patch_count,
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
