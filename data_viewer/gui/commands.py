"""Command handlers for the Data Viewer target shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, Thread, current_thread

from data_viewer.app.documents import DocumentController
from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.sources import SourceRegistry
from data_viewer.tasks import CancellationToken

OpenResultCallback = Callable[["OpenCommandResult"], None]
StateCallback = Callable[[], None]


@dataclass(frozen=True, slots=True)
class OpenCommandResult:
    """Result envelope for asynchronous open attempts."""

    path: Path
    document: DocumentController | None
    error: DataViewerError | None = None

    @property
    def success(self) -> bool:
        """Whether the open operation completed with a document."""

        return self.document is not None and self.error is None


@dataclass(frozen=True, slots=True)
class OpenCommandHandle:
    """Handle for one async open request."""

    path: Path
    cancellation: CancellationToken
    thread: Thread

    def cancel(self) -> None:
        """Request cancellation of the open operation."""

        self.cancellation.cancel()

    def join(self, timeout: float | None = None) -> bool:
        """Wait for completion and report whether the open thread finished."""

        self.thread.join(timeout=timeout)
        return not self.thread.is_alive()


class OpenFileCommand:
    """Launches file-open operations in a worker thread."""

    def __init__(
        self,
        *,
        registry: SourceRegistry,
        on_started: StateCallback | None = None,
        on_finished: OpenResultCallback | None = None,
    ) -> None:
        self._registry = registry
        self._on_started = on_started
        self._on_finished = on_finished
        self._active_lock = Lock()
        self._active_threads: dict[Thread, OpenCommandHandle] = {}

    def open_async(self, path: str | Path) -> OpenCommandHandle:
        """Open a data source without blocking the GUI thread."""

        source_path = Path(path)
        if self._on_started is not None:
            self._on_started()

        cancellation = CancellationToken()
        thread = Thread(
            target=self._run_open,
            args=(source_path, cancellation),
            name=f"data-viewer-open-{source_path.name}",
            daemon=True,
        )
        handle = OpenCommandHandle(path=source_path, cancellation=cancellation, thread=thread)
        with self._active_lock:
            self._active_threads[thread] = handle
        thread.start()
        return handle

    def cancel_all(self) -> int:
        """Cancel every in-flight open request."""

        with self._active_lock:
            active = tuple(self._active_threads.values())
        for handle in active:
            handle.cancel()
        return len(active)

    def active_count(self) -> int:
        """Return the number of in-flight open requests."""

        with self._active_lock:
            return len(self._active_threads)

    def _run_open(self, source_path: Path, cancellation: CancellationToken) -> None:
        try:
            document = DocumentController.open_path(
                source_path,
                registry=self._registry,
                cancellation=cancellation,
            )
            result = OpenCommandResult(path=source_path, document=document)
        except DataViewerError as error:
            result = OpenCommandResult(
                path=source_path,
                document=None,
                error=error,
            )
        except Exception as error:  # pragma: no cover - defensive shell boundary.
            result = OpenCommandResult(
                path=source_path,
                document=None,
                error=DataViewerError(
                    code=ErrorCode.SOURCE_OPEN_FAILED,
                    message=f"Unexpected error while opening {source_path}.",
                    operation="shell.open_file",
                    cause=error,
                ),
            )

        if self._on_finished is not None:
            self._on_finished(result)
        with self._active_lock:
            self._active_threads.pop(current_thread(), None)
