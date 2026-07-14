"""Active document/resource context without GUI widget coupling."""

from __future__ import annotations

from dataclasses import dataclass, replace
from threading import RLock

from data_viewer.domain import ResourceId

from .documents import DocumentRequest, DocumentSnapshot


@dataclass(frozen=True, slots=True)
class ActiveContextSnapshot:
    """Immutable active-context state for commands and view models."""

    document_id: str | None = None
    resource_id: ResourceId | None = None
    request_generation: int | None = None
    active_split_id: str | None = None
    active_view_id: str | None = None
    selection_label: str | None = None
    has_dirty_changes: bool = False
    has_active_task: bool = False
    can_undo: bool = False
    can_redo: bool = False
    bottom_panel_visible: bool = True

    def with_edit_state(
        self,
        *,
        has_dirty_changes: bool,
        can_undo: bool,
        can_redo: bool,
    ) -> ActiveContextSnapshot:
        """Return a copy with updated edit affordance state."""

        return replace(
            self,
            has_dirty_changes=has_dirty_changes,
            can_undo=can_undo,
            can_redo=can_redo,
        )


class ActiveContext:
    """Single source of truth for active document/resource request context."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._document_id: str | None = None
        self._resource_id: ResourceId | None = None
        self._request_generation: int | None = None
        self._active_split_id: str | None = None
        self._active_view_id: str | None = None
        self._selection_label: str | None = None
        self._has_dirty_changes = False
        self._has_active_task = False
        self._can_undo = False
        self._can_redo = False
        self._bottom_panel_visible = True

    def activate_document(self, document: DocumentSnapshot) -> ActiveContextSnapshot:
        """Activate a document without reaching into any widget."""

        with self._lock:
            self._document_id = document.document_id
            self._resource_id = document.active_resource_id
            self._request_generation = document.request_generation
            return self._snapshot_locked()

    def activate_request(self, request: DocumentRequest) -> ActiveContextSnapshot:
        """Activate a concrete resource request."""

        with self._lock:
            self._document_id = request.document_id
            self._resource_id = request.resource_id
            self._request_generation = request.request_generation
            return self._snapshot_locked()

    def activate_view(
        self,
        *,
        document_id: str,
        resource_id: ResourceId,
        request_generation: int,
        active_split_id: str,
        active_view_id: str,
        selection_label: str | None = None,
    ) -> ActiveContextSnapshot:
        """Activate a concrete split/view/resource without widget references."""

        with self._lock:
            self._document_id = document_id
            self._resource_id = resource_id
            self._request_generation = request_generation
            self._active_split_id = active_split_id
            self._active_view_id = active_view_id
            self._selection_label = selection_label
            return self._snapshot_locked()

    def set_edit_state(
        self,
        *,
        has_dirty_changes: bool,
        can_undo: bool,
        can_redo: bool,
    ) -> ActiveContextSnapshot:
        """Update edit-related command state."""

        with self._lock:
            self._has_dirty_changes = has_dirty_changes
            self._can_undo = can_undo
            self._can_redo = can_redo
            return self._snapshot_locked()

    def set_task_state(self, *, has_active_task: bool) -> ActiveContextSnapshot:
        """Update task-related command state."""

        with self._lock:
            self._has_active_task = has_active_task
            return self._snapshot_locked()

    def set_bottom_panel_visible(self, visible: bool) -> ActiveContextSnapshot:
        """Update bottom-panel command state."""

        with self._lock:
            self._bottom_panel_visible = visible
            return self._snapshot_locked()

    def clear(self) -> ActiveContextSnapshot:
        """Clear all active context."""

        with self._lock:
            self._document_id = None
            self._resource_id = None
            self._request_generation = None
            self._active_split_id = None
            self._active_view_id = None
            self._selection_label = None
            self._has_dirty_changes = False
            self._has_active_task = False
            self._can_undo = False
            self._can_redo = False
            self._bottom_panel_visible = True
            return self._snapshot_locked()

    def snapshot(self) -> ActiveContextSnapshot:
        """Return the current immutable context snapshot."""

        with self._lock:
            return self._snapshot_locked()

    def matches(self, document: DocumentSnapshot) -> bool:
        """Return whether the context still matches a document generation."""

        with self._lock:
            return (
                self._document_id == document.document_id
                and self._request_generation == document.request_generation
            )

    def _snapshot_locked(self) -> ActiveContextSnapshot:
        return ActiveContextSnapshot(
            document_id=self._document_id,
            resource_id=self._resource_id,
            request_generation=self._request_generation,
            active_split_id=self._active_split_id,
            active_view_id=self._active_view_id,
            selection_label=self._selection_label,
            has_dirty_changes=self._has_dirty_changes,
            has_active_task=self._has_active_task,
            can_undo=self._can_undo,
            can_redo=self._can_redo,
            bottom_panel_visible=self._bottom_panel_visible,
        )


__all__ = ["ActiveContext", "ActiveContextSnapshot"]
