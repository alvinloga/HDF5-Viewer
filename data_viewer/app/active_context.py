"""Active document/resource context without GUI widget coupling."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from data_viewer.domain import ResourceId

from .documents import DocumentRequest, DocumentSnapshot


@dataclass(frozen=True, slots=True)
class ActiveContextSnapshot:
    """Immutable active-context state for commands and view models."""

    document_id: str | None = None
    resource_id: ResourceId | None = None
    request_generation: int | None = None


class ActiveContext:
    """Single source of truth for active document/resource request context."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._document_id: str | None = None
        self._resource_id: ResourceId | None = None
        self._request_generation: int | None = None

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

    def clear(self) -> ActiveContextSnapshot:
        """Clear all active context."""

        with self._lock:
            self._document_id = None
            self._resource_id = None
            self._request_generation = None
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
        )


__all__ = ["ActiveContext", "ActiveContextSnapshot"]

