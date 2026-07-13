"""Cooperative cancellation primitives."""

from __future__ import annotations

from threading import Event

from data_viewer.domain.errors import DataViewerError, ErrorCode


class CancellationToken:
    """Thread-safe cooperative cancellation token."""

    def __init__(self) -> None:
        self._event = Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self, *, operation: str = "task") -> None:
        if self.is_cancelled:
            raise DataViewerError(
                code=ErrorCode.TASK_CANCELLED,
                message="Operation was cancelled.",
                operation=operation,
                details={"operation": operation},
            )
