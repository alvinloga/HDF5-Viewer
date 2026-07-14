"""Main target shell widget composition for Data Viewer."""

from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from data_viewer.app.documents import DocumentController
from data_viewer.domain import DataViewerError
from data_viewer.sources import SourceRegistry
from data_viewer.sources.hdf5 import HDF5Adapter

from .commands import OpenCommandHandle, OpenCommandResult, OpenFileCommand


def create_source_registry() -> SourceRegistry:
    """Build a bootstrap registry for the current phase."""

    return SourceRegistry([HDF5Adapter()])


class DataViewerShell(QMainWindow):
    """Minimal shell with navigation/workspace/inspector/bottom/status regions."""

    def __init__(
        self,
        *,
        source_registry: SourceRegistry | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Data Viewer")
        self.setMinimumSize(980, 660)

        self._registry = source_registry or create_source_registry()
        self._open_results: Queue[OpenCommandResult] = Queue()
        self._open_documents: list[DocumentController] = []
        self._open_handles: dict[Thread, OpenCommandHandle] = {}

        self._open_command = OpenFileCommand(
            registry=self._registry,
            on_started=self._on_open_started,
            on_finished=self._open_results.put,
        )

        self._build_controls()
        self._build_layout()

        self._open_drain_timer = QTimer(self)
        self._open_drain_timer.setInterval(16)
        self._open_drain_timer.timeout.connect(self._drain_open_results)
        self._open_drain_timer.start()

    def _build_controls(self) -> None:
        self._path_input = QLineEdit(self)
        self._path_input.setPlaceholderText("Drop or enter a source path, then open")
        self._path_input.setObjectName("path_input")
        self._path_input.returnPressed.connect(self._handle_open_triggered)

        self._open_button = QPushButton("Open", self)
        self._open_button.setObjectName("open_button")
        self._open_button.clicked.connect(self._handle_open_triggered)

        self._cancel_open_button = QPushButton("Cancel Open", self)
        self._cancel_open_button.setObjectName("cancel_open_button")
        self._cancel_open_button.clicked.connect(self._handle_cancel_open)
        self._cancel_open_button.setEnabled(False)

        self._navigation = QListWidget(self)
        self._navigation.setObjectName("navigation_region")
        self._workspace = QListWidget(self)
        self._workspace.setObjectName("workspace_region")
        self._inspector = QPlainTextEdit(self)
        self._inspector.setObjectName("inspector_region")
        self._inspector.setReadOnly(True)
        self._inspector.setPlaceholderText("Inspector details appear after opening a source.")

        self._bottom = QPlainTextEdit(self)
        self._bottom.setObjectName("bottom_region")
        self._bottom.setReadOnly(True)
        self._bottom.setPlaceholderText("Task and problem messages appear here.")

        self._status_bar = QStatusBar(self)
        self._status_bar.setObjectName("status_bar")
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("Ready", self)
        self._status_bar.addWidget(self._status_label)

        self._append_bottom("Ready")
        self._navigation.addItem(QListWidgetItem("No source opened yet."))
        self._workspace.addItem(QListWidgetItem("No active resource yet."))

    def _build_panel(self, title: str, widget: QWidget) -> QGroupBox:
        panel = QGroupBox(title, self)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        panel_layout.addWidget(widget)
        return panel

    def _build_layout(self) -> None:
        command_row = QWidget(self)
        command_layout = QHBoxLayout(command_row)
        command_layout.setContentsMargins(8, 8, 8, 8)
        command_layout.setSpacing(8)
        command_layout.addWidget(QLabel("Source path", self))
        command_layout.addWidget(self._path_input, 1)
        command_layout.addWidget(self._open_button)
        command_layout.addWidget(self._cancel_open_button)

        top_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        top_splitter.setObjectName("main_splitter")
        top_splitter.setChildrenCollapsible(False)
        top_splitter.addWidget(self._build_panel("Navigation", self._navigation))
        top_splitter.addWidget(self._build_panel("Workspace", self._workspace))
        top_splitter.addWidget(self._build_panel("Inspector", self._inspector))
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 3)
        top_splitter.setStretchFactor(2, 2)

        bottom_panel = self._build_panel("Bottom", self._bottom)
        bottom_panel.setObjectName("bottom_panel")
        bottom_panel.setMinimumHeight(190)

        main_splitter = QSplitter(Qt.Orientation.Vertical, self)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_panel)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(command_row)
        layout.addWidget(main_splitter)

        container = QWidget(self)
        container.setLayout(layout)
        self.setCentralWidget(container)

        self._navigation.setMinimumWidth(240)
        self._workspace.setMinimumWidth(220)
        self._inspector.setMinimumWidth(300)

    def _append_bottom(self, message: str) -> None:
        self._bottom.appendPlainText(message)

    def _handle_open_triggered(self) -> None:
        self.open_file(self._path_input.text())

    def _handle_cancel_open(self) -> None:
        cancelled = self._open_command.cancel_all()
        if cancelled:
            self._append_bottom(f"Cancelled {cancelled} open request(s).")
        else:
            self._append_bottom("No active open request to cancel.")
        self._refresh_open_cancel_state()

    def open_file(
        self,
        path_text: str | Path,
        *,
        _start_from_ui: bool = True,
        _show_feedback: bool = True,
    ) -> OpenCommandHandle | None:
        source_path = Path(path_text)
        if not source_path.exists():
            if _show_feedback:
                self._append_bottom(f"Open skipped: path does not exist: {source_path}")
            self._status_label.setText("Open skipped")
            self._status_bar.showMessage("Path does not exist.", 5000)
            return None
        if not source_path.is_file():
            if _show_feedback:
                self._append_bottom(f"Open skipped: not a file: {source_path}")
            self._status_label.setText("Open skipped")
            self._status_bar.showMessage("Path is not a file.", 5000)
            return None
        if _start_from_ui:
            self._path_input.setText(str(source_path))
        if _show_feedback:
            self._append_bottom(f"Requesting open: {source_path}")

        handle = self._open_command.open_async(source_path)
        self._open_handles[handle.thread] = handle
        self._refresh_open_cancel_state()
        return handle

    def _on_open_started(self) -> None:
        self._status_label.setText("Opening source...")
        self._status_bar.showMessage("Opening source...")
        self._append_bottom("Open request started.")

    def _drain_open_results(self) -> None:
        self._refresh_open_handle_states()
        self._refresh_open_cancel_state()

        while True:
            try:
                result = self._open_results.get_nowait()
            except Empty:
                return
            if not result.success or result.document is None:
                self._handle_open_error(result.error, result.path)
                continue
            self._handle_open_success(result.document, result.path)

    def _handle_open_success(self, document: DocumentController, path: Path) -> None:
        self._open_documents.append(document)
        if (
            self._navigation.count() == 1
            and self._navigation.item(0) is not None
        ):
            navigation_item = self._navigation.item(0)
            if navigation_item is not None and navigation_item.text() == "No source opened yet.":
                self._workspace.clear()
                self._navigation.clear()
        if (
            self._workspace.count() == 1
            and self._workspace.item(0) is not None
        ):
            workspace_item = self._workspace.item(0)
            if workspace_item is not None and workspace_item.text() == "No active resource yet.":
                self._workspace.clear()
        self._navigation.addItem(QListWidgetItem(path.name))
        self._workspace.addItem(QListWidgetItem(f"Opened: {path.name}"))
        snapshot = document.snapshot()
        self._inspector.setPlainText(
            "\n".join(
                [
                    f"Source URI: {snapshot.source_uri}",
                    f"Fingerprint: {snapshot.fingerprint}",
                    f"Request generation: {snapshot.request_generation}",
                    f"Active task count: {snapshot.active_task_count}",
                    f"Active I/O count: {snapshot.active_io_count}",
                ]
            )
        )
        self._status_label.setText(f"Opened {path}")
        self._status_bar.showMessage(f"Opened {path}", 5000)
        self._append_bottom(f"Opened {path}")

    def _handle_open_error(self, error: DataViewerError | None, path: Path) -> None:
        message = error.message if error is not None else "unknown error"
        self._status_label.setText("Open failed")
        self._status_bar.showMessage("Open failed", 5000)
        self._append_bottom(f"Failed opening {path}: {message}")
        if self._workspace.count() == 0:
            self._workspace.clear()
            self._workspace.addItem(QListWidgetItem("No active resource yet."))

    def _refresh_open_handle_states(self) -> None:
        for thread in tuple(self._open_handles.keys()):
            if not thread.is_alive():
                self._open_handles.pop(thread, None)

    def _refresh_open_cancel_state(self) -> None:
        has_active = any(handle.thread.is_alive() for handle in self._open_handles.values())
        self._cancel_open_button.setEnabled(has_active)

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self._open_command.cancel_all()
        for handle in tuple(self._open_handles.values()):
            handle.join(timeout=0.1)
        self._refresh_open_handle_states()
        self._refresh_open_cancel_state()
        for document in list(self._open_documents):
            try:
                document.close(timeout=0.2)
            except Exception as error:  # pragma: no cover - defensive shell boundary.
                self._append_bottom(f"Could not close {document.source_uri}: {error}")
        self._open_documents.clear()
        super().closeEvent(event)


def launch_shell(*, startup_path: Path | None = None) -> DataViewerShell:
    """Create and show the minimal shell in the current QApplication."""

    if QApplication.instance() is None:
        raise RuntimeError("QApplication instance is required before launching shell.")
    shell = DataViewerShell()
    if startup_path is not None:
        shell.open_file(startup_path, _start_from_ui=False, _show_feedback=False)
    shell.show()
    return shell
