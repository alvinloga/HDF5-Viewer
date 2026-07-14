"""Main target shell widget composition for Data Viewer.

This module implements the DV-0205 vertical shell surfaces:
- lazy structure tree,
- metadata inspector,
- asynchronous array/table workspace with paging and high-dim axis controls.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Thread
from typing import Any
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QSpinBox,
    QStatusBar,
    QTableView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from data_viewer.app.documents import DocumentController
from data_viewer.domain import (
    ArrayPayload,
    AxisSelection,
    DataDomain,
    DataMetadata,
    DataViewerError,
    OperationScope,
    ReadResult,
    ResourceId,
    NormalizedSelection,
    SelectionSpec,
    ErrorCode,
)
from data_viewer.domain.payload import TablePayload
from data_viewer.editing.patches import EditPatch
from data_viewer.editing.review import SaveReview, SaveStrategy
from data_viewer.editing.session import EditSessionState
from data_viewer.exporting import (
    ExportReceipt,
    ExportScope,
    ExportService,
    ExportValueMode,
    build_export_plan,
)
from data_viewer.tasks import CancellationToken
from data_viewer.sources import (
    NodePage,
    ReadRequest,
    SourceRegistry,
)
from data_viewer.sources.hdf5 import HDF5Adapter
from data_viewer.sources.numpy import NPYAdapter

from .commands import OpenCommandHandle, OpenCommandResult, OpenFileCommand


TreeNodeKey = tuple[str, str]


ROLE_NODE_KEY = Qt.ItemDataRole.UserRole + 1
ROLE_CURSOR = Qt.ItemDataRole.UserRole + 2
ROLE_LOADED = Qt.ItemDataRole.UserRole + 3
ROLE_HAS_CHILDREN = Qt.ItemDataRole.UserRole + 4
ROLE_LOAD_MORE = Qt.ItemDataRole.UserRole + 5


def create_source_registry() -> SourceRegistry:
    """Build a bootstrap registry for the current task profile."""

    return SourceRegistry([HDF5Adapter(), NPYAdapter()])


@dataclass(frozen=True)
class _WorkItemResult:
    """Generalized asynchronous work result for shell-side UI tasks."""

    kind: str
    document_token: int
    document_id: str
    request_generation: int
    payload: Any = None
    resource: ResourceId | None = None
    parent_key: TreeNodeKey | None = None
    cursor: str | None = None
    selection: SelectionSpec | None = None
    error: DataViewerError | None = None

    @property
    def failed(self) -> bool:
        return self.error is not None


@dataclass(frozen=True)
class _AxisControlConfig:
    """Configuration for one axis control row."""

    axis: int
    span: tuple[int, int]


class _ArrayTableModel(QAbstractTableModel):
    """Lightweight virtualized table model for array and table payloads."""

    def __init__(self) -> None:
        super().__init__()
        self._payload: ArrayPayload | TablePayload | None = None
        self._rows: list[list[str]] = []
        self._headers: tuple[list[str], list[str]] = ([], [])
        self._row_source_coords: list[tuple[int, ...]] = []
        self._col_source_coords: list[tuple[int, ...]] = []

    def clear(self) -> None:
        self.beginResetModel()
        self._payload = None
        self._rows = []
        self._headers = ([], [])
        self._row_source_coords = []
        self._col_source_coords = []
        self.endResetModel()

    def _format_cell(self, value: Any) -> str:
        if isinstance(value, np.ndarray):
            if value.shape == ():
                value = value.item()
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except Exception:
                return value.hex()
        if isinstance(value, np.integer | np.floating | np.bool_):
            return str(value.item())
        if isinstance(value, (float, int, bool, str)):
            return str(value)
        return repr(value)

    def set_payload(self, payload: ArrayPayload | TablePayload) -> None:
        self.beginResetModel()
        self._payload = payload
        self._rows = []
        self._row_source_coords = []
        self._col_source_coords = []

        if isinstance(payload, TablePayload):
            columns = [column.name for column in payload.columns]
            row_count = payload.row_count
            self._headers = (columns, [str(value) for value in range(len(columns))])
            self._rows = [
                [
                    self._format_cell(payload.column_values[col][row])
                    for col in range(len(columns))
                ]
                for row in range(row_count)
            ]
            for row in range(row_count):
                self._row_source_coords.append((payload.source_row(row),))
            self._col_source_coords = [(idx,) for idx in range(len(columns))]
            self.endResetModel()
            return

        values = np.asarray(payload.values)
        if values.ndim == 0:
            self._headers = (["value"], [""], )
            self._rows = [[self._format_cell(values.item())]]
            self._row_source_coords = [()]
            self._col_source_coords = [tuple()]
            self.endResetModel()
            return

        if values.ndim == 1:
            self._headers = (["Value"], [""], )
            self._rows = [[self._format_cell(values[row])] for row in range(values.shape[0])]
            for row in range(values.shape[0]):
                self._row_source_coords.append(payload.source_coordinates((row,)))
            self._col_source_coords = [tuple()]
            self.endResetModel()
            return

        if values.ndim >= 2:
            self._headers = (
                [f"C{col}" for col in range(values.shape[1])],
                ["" for _ in range(values.shape[1])],
            )
            rows: list[list[str]] = []
            for row in range(values.shape[0]):
                row_values = []
                source = payload.source_coordinates((row, 0))
                self._row_source_coords.append(source)
                for col in range(values.shape[1]):
                    if row == 0:
                        self._col_source_coords.append(payload.source_coordinates((0, col)))
                    row_values.append(self._format_cell(values[row, col]))
                rows.append(row_values)
            self._rows = rows
            if values.shape[1] == 0:
                self._col_source_coords = []
            self.endResetModel()
            return

        self._headers = (["value"], [""])
        self._rows = [[self._format_cell(values)]]
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._headers[0])

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: N802
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        row = index.row()
        col = index.column()
        if not (0 <= row < len(self._rows)):
            return None
        row_values = self._rows[row]
        if not (0 <= col < len(row_values)):
            return None
        return row_values[col]

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            headers = self._headers[0]
            if 0 <= section < len(headers):
                return headers[section]
            return None

        if orientation == Qt.Orientation.Vertical:
            if 0 <= section < len(self._row_source_coords):
                return str(self._row_source_coords[section])
            return str(section)
        return None


def _node_key_for(resource_id: ResourceId | None) -> TreeNodeKey | None:
    if resource_id is None:
        return None
    return (resource_id.source_uri, resource_id.node_path)


def _node_path_to_key(source_uri: str, node_path: str) -> TreeNodeKey:
    return (source_uri, node_path)


class DataViewerShell(QMainWindow):
    """Structured workspace shell with structure table, metadata, and async tasks."""

    def __init__(self, *, source_registry: SourceRegistry | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Data Viewer")
        self.setMinimumSize(1150, 740)

        self._registry = source_registry or create_source_registry()
        self._open_results: Queue[OpenCommandResult] = Queue()
        self._work_results: Queue[_WorkItemResult] = Queue()
        self._open_documents: list[DocumentController] = []
        self._background_tasks: dict[Thread, CancellationToken] = {}

        self._active_document: DocumentController | None = None
        self._active_document_token: int | None = None
        self._active_resource: ResourceId | None = None
        self._active_metadata: DataMetadata | None = None
        self._active_read_result: ReadResult | None = None
        self._active_request_generation_by_resource: dict[TreeNodeKey, int] = {}
        self._active_read_generation_by_resource: dict[TreeNodeKey, int] = {}
        self._tree_node_map: dict[TreeNodeKey, QTreeWidgetItem] = {}
        self._latest_slice: dict[str, int] = {
            "row_offset": 0,
            "row_limit": 256,
            "col_offset": 0,
            "col_limit": 256,
        }
        self._axis_controls: dict[int, QSpinBox] = {}
        self._axis_configs: list[_AxisControlConfig] = []

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

    # ----------------------------- UI construction -----------------------------
    def _build_controls(self) -> None:
        self._path_input = QLineEdit(self)
        self._path_input.setPlaceholderText("Enter source path, then open")
        self._path_input.setObjectName("path_input")
        self._path_input.returnPressed.connect(self._handle_open_triggered)

        self._open_button = QPushButton("Open", self)
        self._open_button.setObjectName("open_button")
        self._open_button.clicked.connect(self._handle_open_triggered)

        self._cancel_open_button = QPushButton("Cancel Open", self)
        self._cancel_open_button.setObjectName("cancel_open_button")
        self._cancel_open_button.clicked.connect(self._handle_cancel_open)
        self._cancel_open_button.setEnabled(False)

        self._review_changes_button = QPushButton("Review Changes", self)
        self._review_changes_button.setObjectName("review_changes_button")
        self._review_changes_button.clicked.connect(self.review_active_edits)
        self._review_changes_button.setEnabled(False)

        self._save_button = QPushButton("Save", self)
        self._save_button.setObjectName("save_button")
        self._save_button.clicked.connect(self.save_active_edits)
        self._save_button.setEnabled(False)

        self._save_as_button = QPushButton("Save As", self)
        self._save_as_button.setObjectName("save_as_button")
        self._save_as_button.setEnabled(False)
        self._save_as_button.clicked.connect(
            lambda: self._append_bottom("Save As requires a target path in this shell build.")
        )

        self._export_button = QPushButton("Export", self)
        self._export_button.setObjectName("export_button")
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(
            lambda: self._append_bottom("Export requires a target path. Use export_active_to_path(path).")
        )

        self._edit_state_label = QLabel("edit: clean (0 pending)", self)
        self._edit_state_label.setObjectName("edit_state_label")
        self._readonly_hint_label = QLabel("No source loaded", self)
        self._readonly_hint_label.setObjectName("readonly_hint_label")

        self._navigation = QTreeWidget(self)
        self._navigation.setObjectName("navigation_region")
        self._navigation.setHeaderLabel("Structure")
        self._navigation.itemExpanded.connect(self._on_navigation_item_expanded)
        self._navigation.itemClicked.connect(self._on_navigation_item_clicked)
        self._navigation.itemActivated.connect(self._on_navigation_item_activated)
        self._navigation.itemDoubleClicked.connect(self._on_navigation_item_activated)
        self._navigation.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._navigation.setMinimumWidth(280)
        self._navigation.setColumnCount(1)
        self._navigation.setHeaderHidden(False)

        self._inspector = QPlainTextEdit(self)
        self._inspector.setObjectName("inspector_region")
        self._inspector.setReadOnly(True)
        self._inspector.setPlaceholderText("Select a node to inspect metadata.")

        self._workspace_status = QLabel("Workspace: not ready", self)
        self._workspace_status.setObjectName("workspace_status")
        self._axis_area = QWidget(self)
        self._axis_area.setObjectName("axis_controls_container")
        self._axis_area_layout = QVBoxLayout(self._axis_area)
        self._axis_area_layout.setContentsMargins(0, 0, 0, 0)
        self._axis_area_layout.setSpacing(6)

        slice_form = QWidget(self._axis_area)
        form = QFormLayout(slice_form)
        form.setContentsMargins(0, 0, 0, 0)

        self._row_offset_input = QSpinBox(self)
        self._row_offset_input.setObjectName("row_offset_input")
        self._row_offset_input.setMinimum(0)
        self._row_offset_input.setMaximum(0)
        self._row_offset_input.setValue(0)
        self._row_offset_input.valueChanged.connect(self._mark_workspace_dirty)

        self._row_limit_input = QSpinBox(self)
        self._row_limit_input.setObjectName("row_limit_input")
        self._row_limit_input.setMinimum(1)
        self._row_limit_input.setMaximum(8192)
        self._row_limit_input.setValue(256)
        self._row_limit_input.valueChanged.connect(self._mark_workspace_dirty)

        self._col_offset_input = QSpinBox(self)
        self._col_offset_input.setObjectName("col_offset_input")
        self._col_offset_input.setMinimum(0)
        self._col_offset_input.setMaximum(0)
        self._col_offset_input.setValue(0)
        self._col_offset_input.valueChanged.connect(self._mark_workspace_dirty)

        self._col_limit_input = QSpinBox(self)
        self._col_limit_input.setObjectName("col_limit_input")
        self._col_limit_input.setMinimum(1)
        self._col_limit_input.setMaximum(8192)
        self._col_limit_input.setValue(256)
        self._col_limit_input.valueChanged.connect(self._mark_workspace_dirty)

        self._load_slice_button = QPushButton("Load Slice", self)
        self._load_slice_button.setObjectName("load_slice_button")
        self._load_slice_button.clicked.connect(self._on_load_slice_clicked)
        self._load_slice_button.setEnabled(False)

        form.addRow("Row offset", self._row_offset_input)
        form.addRow("Row limit", self._row_limit_input)
        form.addRow("Col offset", self._col_offset_input)
        form.addRow("Col limit", self._col_limit_input)
        form.addRow("Slice", self._load_slice_button)
        self._axis_area_layout.addWidget(slice_form)

        self._axis_scroll = QScrollArea(self)
        self._axis_scroll.setObjectName("axis_scroll_area")
        self._axis_scroll.setWidgetResizable(True)
        self._axis_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._axis_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._axis_dynamic_form_widget = QWidget(self)
        self._axis_dynamic_form = QFormLayout(self._axis_dynamic_form_widget)
        self._axis_dynamic_form.setContentsMargins(0, 0, 0, 0)
        self._axis_scroll.setWidget(self._axis_dynamic_form_widget)
        self._axis_area_layout.addWidget(self._axis_scroll)

        self._workspace_view = QTableView(self)
        self._workspace_view.setObjectName("workspace_region")
        self._workspace_view.setAlternatingRowColors(True)
        self._workspace_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._workspace_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )
        horizontal_header = self._workspace_view.horizontalHeader()
        if horizontal_header is not None:
            horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        vertical_header = self._workspace_view.verticalHeader()
        if vertical_header is not None:
            vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        self._workspace_model = _ArrayTableModel()
        self._workspace_view.setModel(self._workspace_model)
        self._set_workspace_status("ready", "Open a source and select an ARRAY node.")

        self._bottom = QPlainTextEdit(self)
        self._bottom.setObjectName("bottom_region")
        self._bottom.setReadOnly(True)
        self._bottom.setPlaceholderText("Task and diagnostics appear here.")

        self._status_bar = QStatusBar(self)
        self._status_bar.setObjectName("status_bar")
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("Ready", self)
        self._status_label.setObjectName("status_label")
        self._status_path = QLabel("Path: -", self)
        self._status_path.setObjectName("status_path")
        self._status_shape = QLabel("shape: -", self)
        self._status_shape.setObjectName("status_shape")
        self._status_dtype = QLabel("dtype: -", self)
        self._status_dtype.setObjectName("status_dtype")
        self._status_scope = QLabel("slice: -", self)
        self._status_scope.setObjectName("status_scope")
        self._status_readonly = QLabel("mode: -", self)
        self._status_readonly.setObjectName("status_readonly")
        self._status_bar.addWidget(self._status_label)
        self._status_bar.addPermanentWidget(self._status_path)
        self._status_bar.addPermanentWidget(self._status_shape)
        self._status_bar.addPermanentWidget(self._status_dtype)
        self._status_bar.addPermanentWidget(self._status_scope)
        self._status_bar.addPermanentWidget(self._status_readonly)
        self._status_bar.addPermanentWidget(self._edit_state_label)
        self._append_bottom("Ready")
        self._set_workspace_state("initial", "No source opened yet.")
        self._refresh_edit_actions()

    def _build_layout(self) -> None:
        command_row = QWidget(self)
        command_layout = QHBoxLayout(command_row)
        command_layout.setContentsMargins(8, 8, 8, 8)
        command_layout.setSpacing(8)
        command_layout.addWidget(QLabel("Source path", self))
        command_layout.addWidget(self._path_input, 1)
        command_layout.addWidget(self._open_button)
        command_layout.addWidget(self._cancel_open_button)
        command_layout.addWidget(self._review_changes_button)
        command_layout.addWidget(self._save_button)
        command_layout.addWidget(self._save_as_button)
        command_layout.addWidget(self._export_button)

        workspace_container = QWidget(self)
        workspace_layout = QVBoxLayout(workspace_container)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(8)
        workspace_layout.addWidget(self._workspace_status)
        workspace_layout.addWidget(self._readonly_hint_label)
        workspace_layout.addWidget(self._axis_area)
        workspace_layout.addWidget(self._workspace_view, 1)

        top_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        top_splitter.setObjectName("main_splitter")
        top_splitter.setChildrenCollapsible(False)
        top_splitter.addWidget(self._build_panel("Navigation", self._navigation))
        top_splitter.addWidget(self._build_panel("Workspace", workspace_container))
        top_splitter.addWidget(self._build_panel("Inspector", self._inspector))
        top_splitter.setStretchFactor(0, 2)
        top_splitter.setStretchFactor(1, 4)
        top_splitter.setStretchFactor(2, 2)

        bottom_panel = self._build_panel("Bottom", self._bottom)
        bottom_panel.setObjectName("bottom_panel")
        bottom_panel.setMinimumHeight(220)

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

        self._navigation.setMinimumWidth(280)
        self._workspace_view.setMinimumWidth(320)
        self._inspector.setMinimumWidth(320)
        self._workspace_status.setMinimumHeight(24)
        self._workspace_view.setMinimumHeight(220)

    def _build_panel(self, title: str, widget: QWidget) -> QGroupBox:
        panel = QGroupBox(title, self)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        panel_layout.setSpacing(8)
        panel_layout.addWidget(widget)
        return panel

    # ----------------------------- public operations -----------------------------
    def open_file(
        self,
        path_text: str | Path,
        *,
        _start_from_ui: bool = True,
        _show_feedback: bool = True,
    ) -> OpenCommandHandle | None:
        """Open a file asynchronously and route results to the GUI thread."""

        source_path = Path(path_text)
        if not source_path.exists():
            if _show_feedback:
                self._append_bottom(f"Open skipped: path does not exist: {source_path}")
            self._status_label.setText("Open skipped")
            self._status_bar.showMessage("Path does not exist.", 5000)
            self._set_workspace_state("error", "Path does not exist.")
            return None
        if not source_path.is_file():
            if _show_feedback:
                self._append_bottom(f"Open skipped: not a file: {source_path}")
            self._status_label.setText("Open skipped")
            self._status_bar.showMessage("Path is not a file.", 5000)
            self._set_workspace_state("error", "Path is not a file.")
            return None
        if _start_from_ui:
            self._path_input.setText(str(source_path))
        if _show_feedback:
            self._append_bottom(f"Requesting open: {source_path}")

        handle = self._open_command.open_async(source_path)
        self._refresh_open_cancel_state()
        self._set_workspace_state("loading", f"Opening: {source_path}")
        return handle

    # ----------------------------- command callbacks -----------------------------
    def _handle_open_triggered(self) -> None:
        self.open_file(self._path_input.text())

    def _handle_cancel_open(self) -> None:
        cancelled = self._open_command.cancel_all()
        if cancelled:
            self._append_bottom(f"Cancelled {cancelled} open request(s).")
        else:
            self._append_bottom("No active open request to cancel.")
        self._refresh_open_cancel_state()

    # ----------------------------- async pumpers -----------------------------
    def _drain_open_results(self) -> None:
        self._refresh_open_handle_states()
        self._refresh_open_cancel_state()
        self._drain_async_results()

        while True:
            try:
                result = self._open_results.get_nowait()
            except Empty:
                return
            if not result.success or result.document is None:
                self._handle_open_error(result.error, result.path)
                continue
            self._handle_open_success(result.document, result.path)

    def _drain_async_results(self) -> None:
        while True:
            try:
                result = self._work_results.get_nowait()
            except Empty:
                return
            if not self._is_active_document_token(result.document_token):
                continue
            if result.kind == "root":
                self._apply_root_load_result(result)
            elif result.kind == "children":
                self._apply_children_result(result)
            elif result.kind == "metadata":
                self._apply_metadata_result(result)
            elif result.kind == "read":
                self._apply_read_result(result)
            elif result.kind == "log":
                self._append_bottom(str(result.payload))

    def _refresh_open_handle_states(self) -> None:
        for thread in tuple(self._background_tasks.keys()):
            if not thread.is_alive():
                self._background_tasks.pop(thread, None)

    def _refresh_open_cancel_state(self) -> None:
        self._cancel_open_button.setEnabled(self._open_command.active_count() > 0)

    def _drain_background_threads(self) -> None:
        self._refresh_open_handle_states()

    def _is_active_document_token(self, token: int) -> bool:
        return self._active_document_token == token

    def _active_generation_for(self, key: TreeNodeKey) -> int:
        return self._active_request_generation_by_resource.get(key, -1)

    def _active_read_generation_for(self, key: TreeNodeKey) -> int:
        return self._active_read_generation_by_resource.get(key, -1)

    # ----------------------------- open handling -----------------------------
    def _on_open_started(self) -> None:
        self._status_label.setText("Opening source")
        self._status_bar.showMessage("Opening source...")

    def _handle_open_success(self, document: DocumentController, path: Path) -> None:
        self._open_documents.append(document)
        self._active_document = document
        self._active_document_token = id(document)
        self._active_resource = None
        self._active_metadata = None
        self._active_read_result = None
        self._active_request_generation_by_resource = {}
        self._active_read_generation_by_resource = {}
        self._tree_node_map = {}
        self._axis_controls = {}
        self._axis_configs = []
        self._load_slice_button.setEnabled(False)
        self._workspace_model.clear()
        self._inspector.clear()

        snapshot = document.snapshot()
        self._status_label.setText(f"Opened: {snapshot.source_uri}")
        self._status_bar.showMessage(f"Opened {path}", 5000)
        self._status_path.setText(f"Path: {snapshot.source_uri}")
        self._status_shape.setText("shape: /")
        self._status_dtype.setText("dtype: -")
        self._status_scope.setText("slice: /")
        self._status_readonly.setText("mode: read-only")
        self._refresh_edit_actions()
        self._append_bottom(f"Opened {snapshot.source_uri}")
        self._set_workspace_state("loading", "Loading structure root...")

        self._navigation.clear()
        root_id = ResourceId(snapshot.source_uri, "/")
        root_item = self._new_tree_item(
            snapshot.source_uri,
            root_id,
            label=self._basename_from_path(path),
        )
        root_item.setToolTip(0, str(root_id))
        self._navigation.addTopLevelItem(root_item)
        self._tree_node_map[(snapshot.source_uri, "/")] = root_item

        self._schedule_root_load(document)

    def _basename_from_path(self, path: Path) -> str:
        return path.name or str(path)

    def _handle_open_error(self, error: DataViewerError | None, path: Path) -> None:
        message = error.message if error is not None else "unknown error"
        self._status_label.setText("Open failed")
        self._status_bar.showMessage("Open failed", 5000)
        self._append_bottom(f"Failed opening {path}: {message}")
        self._set_workspace_state("error", f"Failed opening {path}: {message}")

    # ----------------------------- background dispatch helpers -----------------------------
    def _append_bottom(self, message: str) -> None:
        self._bottom.appendPlainText(message)

    # ----------------------------- edit/save/export actions -----------------------------
    def record_edit_patch(self, patch: EditPatch) -> None:
        """Record one typed edit patch from an editor delegate or plugin-owned UI."""

        if self._active_document is None:
            self._append_bottom("Edit ignored: no active document.")
            return
        snapshot = self._active_document.apply_edit_patch(patch)
        self._append_bottom(
            "Edit recorded: "
            f"{patch.resource_id.node_path} -> {type(patch).__name__}; "
            f"{snapshot.edit_patch_count} pending patch(es)."
        )
        self._refresh_edit_actions()

    def review_active_edits(self) -> str:
        """Build and display the current save review summary."""

        if self._active_document is None:
            message = "No active document to review."
            self._append_bottom(message)
            return message
        try:
            review = self._active_document.build_edit_save_review(
                target_uri=self._active_document.source_uri,
                strategy=SaveStrategy.IN_PLACE,
            )
        except Exception as exc:
            message = f"Save review unavailable: {exc}"
            self._append_bottom(message)
            return message
        text = self._format_save_review(review)
        self._append_bottom(text)
        self._refresh_edit_actions()
        return text

    def save_active_edits(self) -> bool:
        """Persist pending edits for the active document and update user-visible state."""

        if self._active_document is None:
            self._append_bottom("Save skipped: no active document.")
            return False
        snapshot = self._active_document.snapshot()
        if snapshot.edit_state is EditSessionState.CONFLICTED:
            self.display_edit_conflict("source changed before save")
            return False
        if snapshot.edit_patch_count == 0:
            self._append_bottom("Save skipped: no pending edits.")
            self._refresh_edit_actions()
            return False

        self.review_active_edits()
        self._append_bottom("Save task: running.")
        try:
            result = self._active_document.save_edits(cancellation=CancellationToken())
        except DataViewerError as error:
            if error.code.value in {"SOURCE_CHANGED", "EDIT_CONFLICT"}:
                self.display_edit_conflict(error.message)
            else:
                self._append_bottom(f"Save failed: {error.code.value}: {error.message}")
                self._refresh_edit_actions()
            return False

        strategy = getattr(result, "strategy", "adapter-selected")
        self._append_bottom(f"Save succeeded: strategy={strategy}.")
        self._refresh_edit_actions()
        if self._active_document is not None and self._active_resource is not None:
            self._active_document.refresh_edit_fingerprint(cancellation=CancellationToken())
        return True

    def display_edit_conflict(self, message: str) -> None:
        """Display a non-color-only conflict state with explicit safe choices."""

        self._edit_state_label.setText("edit: conflicted (save blocked)")
        self._save_button.setEnabled(False)
        self._review_changes_button.setEnabled(True)
        self._save_as_button.setEnabled(self._active_document is not None)
        self._append_bottom(
            "Edit conflict: "
            f"{message}. Safe choices: Reload source, Save As to a new target, or Cancel and keep patches."
        )

    def export_active_to_path(self, target_path: Path, *, overwrite: bool = False) -> ExportReceipt | None:
        """Export the active workspace payload to a reviewed target path."""

        if self._active_document is None or self._active_resource is None:
            self._append_bottom("Export skipped: no active resource.")
            return None
        if self._active_read_result is None:
            self._append_bottom("Export skipped: no active payload loaded.")
            return None
        payload = self._active_read_result.payload
        selection = (
            payload.selection
            if isinstance(payload, ArrayPayload)
            and isinstance(payload.selection, NormalizedSelection)
            else None
        )
        plan = build_export_plan(
            source_fingerprint=self._active_document.snapshot().fingerprint,
            resource_id=self._active_resource,
            selection=selection,
            target_path=target_path,
            scope=ExportScope.CURRENT_SLICE if selection is not None else ExportScope.FULL_RESOURCE,
            value_mode=ExportValueMode.RAW,
            overwrite=overwrite,
            parameters={
                "ui_surface": "workspace",
                "resource_path": self._active_resource.node_path,
            },
        )
        self._append_bottom(f"Export task: running -> {target_path}")
        receipt = ExportService().export_payload(
            plan,
            payload,
            cancellation=CancellationToken(),
        )
        if receipt.outcome.value == "succeeded":
            self._append_bottom(
                f"Export succeeded: {receipt.target_path} ({receipt.bytes_written} bytes)."
            )
        else:
            self._append_bottom(
                f"Export {receipt.outcome.value}: {receipt.error_code}: {receipt.error_message}"
            )
        return receipt

    def _refresh_edit_actions(self) -> None:
        if self._active_document is None:
            self._edit_state_label.setText("edit: clean (0 pending)")
            self._readonly_hint_label.setText("No source loaded")
            self._review_changes_button.setEnabled(False)
            self._save_button.setEnabled(False)
            self._save_as_button.setEnabled(False)
            self._export_button.setEnabled(False)
            return
        snapshot = self._active_document.snapshot()
        pending = snapshot.edit_patch_count
        self._edit_state_label.setText(f"edit: {snapshot.edit_state.value} ({pending} pending)")
        can_save = pending > 0 and snapshot.edit_state in {
            EditSessionState.DIRTY,
            EditSessionState.SAVE_FAILED,
        }
        self._review_changes_button.setEnabled(pending > 0)
        self._save_button.setEnabled(can_save)
        self._save_as_button.setEnabled(self._active_resource is not None)
        self._export_button.setEnabled(self._active_read_result is not None)
        if self._active_metadata is None:
            self._readonly_hint_label.setText("Source opened. Select a resource to inspect or export.")
        elif DataDomain(self._active_metadata.domain) is DataDomain.ARRAY:
            self._readonly_hint_label.setText(
                "read-only source view: edits are pending patches; use Save, Save As, or Export."
            )
        else:
            self._readonly_hint_label.setText("Inspect-only resource: use Export or Save As where supported.")

    def _format_save_review(self, review: SaveReview) -> str:
        lines = [
            "Save review",
            f"target: {review.target_uri}",
            f"strategy: {review.strategy.value}",
            f"patches: {review.patch_count}",
            f"estimated patch bytes: {review.estimated_size_bytes}",
            "resources:",
        ]
        lines.extend(f"  - {resource.node_path}" for resource in review.resources)
        lines.append("patch kinds:")
        lines.extend(f"  - {kind}: {count}" for kind, count in review.changed_patch_kinds)
        if review.warnings:
            lines.append("warnings:")
            lines.extend(f"  - {warning}" for warning in review.warnings)
        return "\n".join(lines)

    def _run_with_cancel_token(
        self,
        kind: str,
        *,
        document: DocumentController,
        request_generation: int,
        resource: ResourceId | None = None,
        parent_key: TreeNodeKey | None = None,
        selection: SelectionSpec | None = None,
        action: Callable[[CancellationToken], Any],
    ) -> None:
        cancellation = CancellationToken()
        document_token = id(document)
        document_id = document.source_uri

        def runner() -> None:
            try:
                payload = action(cancellation)
            except DataViewerError as error:
                payload = error
            except Exception as error:  # pragma: no cover - defensive shell boundary
                payload = DataViewerError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message="Unexpected shell background error.",
                    operation=f"shell.{kind}",
                    cause=error,  # type: ignore[arg-type]
                )
            self._work_results.put(
                _WorkItemResult(
                    kind=kind,
                    document_token=document_token,
                    document_id=document_id,
                    request_generation=request_generation,
                    payload=payload,
                    resource=resource,
                    parent_key=parent_key,
                    selection=selection,
                )
            )

        thread = Thread(target=runner, name=f"data-viewer-shell-{kind}", daemon=True)
        self._background_tasks[thread] = cancellation
        thread.start()

    # ----------------------------- scheduling tasks -----------------------------
    def _schedule_root_load(self, document: DocumentController) -> None:
        if document is None:
            return
        request_generation = document.request_generation
        source_uri = document.source_uri
        root_resource = ResourceId(source_uri, "/")
        root_key = _node_key_for(root_resource)
        if root_key is None:
            return
        self._active_request_generation_by_resource[root_key] = request_generation

        def action(token: CancellationToken) -> ResourceId:
            document.root(cancellation=token)
            return root_resource

        self._run_with_cancel_token(
            "root",
            document=document,
            request_generation=request_generation,
            resource=root_resource,
            action=action,
        )
        self._run_with_cancel_token(
            "children",
            document=document,
            request_generation=request_generation,
            parent_key=_node_key_for(root_resource),
            resource=root_resource,
            action=lambda token: document.list_children(
                root_resource,
                cursor=None,
                page_size=256,
                cancellation=token,
            ),
        )

    def _schedule_metadata_load(
        self,
        document: DocumentController,
        resource_id: ResourceId,
    ) -> None:
        if document is None:
            return
        request = document.navigate_to(resource_id)
        key = _node_key_for(resource_id)
        if key is not None:
            self._active_request_generation_by_resource[key] = request.request_generation
            self._active_resource = resource_id
        self._set_workspace_state("loading", f"Loading metadata: {resource_id.node_path}")
        self._set_active_status(resource_id)

        self._run_with_cancel_token(
            "metadata",
            document=document,
            request_generation=request.request_generation,
            resource=resource_id,
            action=lambda token: document.get_metadata(resource_id, cancellation=token),
        )

    def _schedule_read(
        self,
        document: DocumentController,
        resource_id: ResourceId,
        metadata: DataMetadata,
        *,
        force_refresh_axes: bool = False,
    ) -> None:
        request = document.navigate_to(resource_id)
        key = _node_key_for(resource_id)
        if key is not None:
            self._active_read_generation_by_resource[key] = request.request_generation
            self._active_resource = resource_id

        if force_refresh_axes:
            self._configure_row_col_limits(metadata)

        read_spec = self._build_selection(metadata, force_refresh_axes=force_refresh_axes)
        if read_spec is None:
            self._set_workspace_state("error", "Unsupported selection for this resource.")
            return
        self._set_status_scope(read_spec)

        request_obj = ReadRequest(
            resource_id=resource_id,
            selection=read_spec,
            scope=OperationScope.FULL if metadata.shape == () else OperationScope.SLICE,
            max_bytes=8 * 1024 * 1024,
        )

        self._set_workspace_state("loading", f"Reading: {resource_id.node_path}")
        self._run_with_cancel_token(
            "read",
            document=document,
            request_generation=request.request_generation,
            resource=resource_id,
            selection=read_spec,
            action=lambda token: document.read(
                request_obj,
                cancellation=token,
                progress=lambda *_args: None,
            ),
        )

    # ----------------------------- tree helpers -----------------------------
    def _new_tree_item(
        self,
        document_id: str,
        resource_id: ResourceId,
        *,
        label: str | None = None,
    ) -> QTreeWidgetItem:
        if label is None:
            label = self._node_label_from_resource(resource_id)
        item = QTreeWidgetItem([label])
        item.setData(0, ROLE_NODE_KEY, _node_key_for(resource_id))
        item.setData(0, ROLE_LOADED, False)
        item.setData(0, ROLE_HAS_CHILDREN, False)
        item.setData(0, ROLE_CURSOR, None)
        item.setData(0, ROLE_LOAD_MORE, False)
        self._tree_node_map[(document_id, resource_id.node_path)] = item
        return item

    @staticmethod
    def _node_label_from_resource(resource_id: ResourceId) -> str:
        if resource_id.node_path in {"/", ""}:
            return "/"
        return resource_id.node_path.rsplit("/", 1)[-1]

    def _new_placeholder_item(self, label: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label])
        item.setData(0, ROLE_LOAD_MORE, True)
        return item

    def _on_navigation_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        node_key = self._resource_key_from_item(item)
        if node_key is None:
            return
        document = self._active_document
        if document is None:
            return
        resource_id = ResourceId(node_key[0], node_key[1])
        if item.data(0, ROLE_LOAD_MORE):
            return
        self._schedule_metadata_load(document, resource_id)

    def _on_navigation_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        if item.data(0, ROLE_LOAD_MORE):
            parent_item = item.parent()
            parent_key = parent_item.data(0, ROLE_NODE_KEY) if parent_item is not None else None
            if parent_key is None:
                return
            parent_resource = ResourceId(parent_key[0], parent_key[1])
            cursor = item.data(0, ROLE_CURSOR)
            if cursor in (None, ""):
                cursor = "0"
            self._load_more_children(parent_resource, str(cursor))
            return
        node_key = self._resource_key_from_item(item)
        if node_key is None:
            return
        document = self._active_document
        if document is None:
            return
        resource_id = ResourceId(node_key[0], node_key[1])
        self._open_resource_in_workspace(resource_id, document)

    def _resource_key_from_item(self, item: QTreeWidgetItem | None) -> TreeNodeKey | None:
        if item is None:
            return None
        key = item.data(0, ROLE_NODE_KEY)
        if isinstance(key, tuple) and len(key) == 2:
            first, second = key
            if isinstance(first, str) and isinstance(second, str):
                return (first, second)
        return None

    def _on_navigation_item_expanded(self, item: QTreeWidgetItem) -> None:
        document = self._active_document
        if document is None:
            return
        if item.data(0, ROLE_LOAD_MORE):
            return
        if bool(item.data(0, ROLE_LOADED)):
            return
        has_children = bool(item.data(0, ROLE_HAS_CHILDREN))
        if not has_children:
            return

        key = self._resource_key_from_item(item)
        if key is None:
            return
        parent_resource = ResourceId(key[0], key[1])
        self._load_children(parent_resource, cursor=None)

    def _load_more_children(self, parent_resource: ResourceId, cursor: str) -> None:
        if self._active_document is None:
            return
        self._load_children(parent_resource, cursor=cursor)

    def _load_children(self, parent_resource: ResourceId, cursor: str | None) -> None:
        document = self._active_document
        if document is None:
            return
        request_generation = document.request_generation
        parent_key = _node_key_for(parent_resource)
        if parent_key is None:
            return
        self._active_request_generation_by_resource[parent_key] = request_generation
        self._run_with_cancel_token(
            "children",
            document=document,
            request_generation=request_generation,
            parent_key=parent_key,
            action=lambda token: document.list_children(
                parent_resource,
                cursor=cursor,
                page_size=256,
                cancellation=token,
            ),
        )

    # ----------------------------- apply async results -----------------------------
    def _apply_root_load_result(self, result: _WorkItemResult) -> None:
        if result.failed:
            self._set_workspace_state("error", f"Open error: {result.error}")
            return
        self._status_readonly.setText("mode: read-only")

    def _apply_children_result(self, result: _WorkItemResult) -> None:
        document = self._active_document
        if document is None:
            return
        if result.failed:
            self._append_bottom(
                f"Failed listing children of {result.parent_key}: {result.error}"
            )
            return

        generation = (
            self._active_generation_for(result.parent_key)
            if result.parent_key is not None
            else None
        )
        if generation is not None and generation != result.request_generation:
            return

        page = result.payload
        if not isinstance(page, NodePage) or result.parent_key is None:
            return

        parent_item = self._tree_node_map.get(result.parent_key)
        if parent_item is None:
            return
        self._clear_load_more_children(parent_item)

        for child in page.items:
            child_key = _node_key_for(child.resource_id)
            if child_key is None:
                continue
            child_item = self._new_tree_item(
                document.source_uri,
                child.resource_id,
                label=self._tree_node_text(child),
            )
            child_item.setData(0, ROLE_HAS_CHILDREN, bool(child.has_children))
            child_item.setData(0, ROLE_LOAD_MORE, False)
            if child.has_children:
                child_item.addChild(self._new_placeholder_item("Expand to load"))
            parent_item.addChild(child_item)

        parent_item.setData(0, ROLE_LOADED, True)
        parent_item.setExpanded(True)

        if page.next_cursor is not None and bool(page.next_cursor):
            more_item = self._new_placeholder_item("Load more...")
            more_item.setData(0, ROLE_LOAD_MORE, True)
            more_item.setData(0, ROLE_CURSOR, page.next_cursor)
            more_item.setData(0, ROLE_NODE_KEY, result.parent_key)
            parent_item.addChild(more_item)

        if parent_item.childCount() == 0:
            no_child = self._new_placeholder_item("(empty)")
            no_child.setData(0, ROLE_LOAD_MORE, True)
            no_child.setData(0, ROLE_NODE_KEY, result.parent_key)
            no_child.setFlags(no_child.flags() & ~no_child.flags())
            parent_item.addChild(no_child)
        self._set_workspace_state("ready", "Structure loaded.")

    def _apply_metadata_result(self, result: _WorkItemResult) -> None:
        document = self._active_document
        if document is None or result.resource is None:
            return
        if result.failed:
            self._append_bottom(f"Failed metadata for {result.resource}: {result.error}")
            self._set_workspace_state("error", f"Failed metadata for {result.resource}")
            return

        metadata = result.payload
        if not isinstance(metadata, DataMetadata):
            return
        key = _node_key_for(metadata.resource_id)
        if key is None:
            return
        generation = self._active_generation_for(key)
        if generation != result.request_generation:
            return

        self._active_metadata = metadata
        self._render_metadata(metadata)
        self._configure_axis_controls(metadata)
        self._load_slice_button.setEnabled(True)
        self._status_shape.setText(f"shape: {metadata.shape or '(scalar)'}")
        self._status_dtype.setText(f"dtype: {metadata.dtype or '-'}")
        self._status_path.setText(f"path: {metadata.resource_id.source_uri}{metadata.resource_id.node_path}")
        self._status_scope.setText("slice: current")
        self._status_readonly.setText(
            "mode: read-only" if DataDomain(metadata.domain) in {DataDomain.ARRAY} else "mode: inspect"
        )
        self._refresh_edit_actions()
        self._set_workspace_state("ready", f"Metadata ready: {metadata.name}")

        # auto-load if this is an array.
        if metadata.domain == DataDomain.ARRAY:
            self._schedule_read(document, metadata.resource_id, metadata, force_refresh_axes=False)
        else:
            self._set_workspace_state("disabled", "Unsupported for tabular workspace in this build.")

    def _apply_read_result(self, result: _WorkItemResult) -> None:
        document = self._active_document
        if document is None or result.resource is None:
            return
        key = _node_key_for(result.resource)
        if key is None:
            return
        generation = self._active_read_generation_for(key)
        if generation != result.request_generation:
            return

        if result.failed:
            self._append_bottom(f"Read failed for {result.resource}: {result.error}")
            self._set_workspace_state("error", f"Read failed: {result.error}")
            return

        read_result = result.payload
        if not isinstance(read_result, ReadResult):
            self._set_workspace_state("error", "Unexpected read result payload.")
            return
        self._active_read_result = read_result
        if result.selection is not None:
            self._set_status_scope(result.selection)

        payload = read_result.payload
        if isinstance(payload, (ArrayPayload, TablePayload)):
            self._workspace_model.set_payload(payload)
            self._workspace_view.resizeColumnsToContents()
            self._set_workspace_state(
                "ready",
                f"Workspace ready: {self._counted_rows(self._workspace_model)} rows, {self._counted_cols(self._workspace_model)} cols",
            )
            self._refresh_edit_actions()
            return
        self._set_workspace_state("error", "Unsupported payload type.")

    # ----------------------------- workspace controls -----------------------------
    def _counted_rows(self, model: _ArrayTableModel) -> int:
        return model.rowCount()

    def _counted_cols(self, model: _ArrayTableModel) -> int:
        return model.columnCount()

    def _on_load_slice_clicked(self) -> None:
        if self._active_document is None or self._active_metadata is None:
            return
        self._schedule_read(
            self._active_document,
            self._active_metadata.resource_id,
            self._active_metadata,
            force_refresh_axes=True,
        )

    def _mark_workspace_dirty(self) -> None:
        self._set_workspace_state("initial", "Selection changed. Click Load Slice.")

    def _configure_axis_controls(self, metadata: DataMetadata) -> None:
        self._axis_controls = {}
        self._axis_configs = []
        self._latest_slice = {"row_offset": 0, "row_limit": 256, "col_offset": 0, "col_limit": 256}

        shape = metadata.shape
        ndim = len(shape)
        while self._axis_dynamic_form.rowCount() > 0:
            child = self._axis_dynamic_form.takeAt(0)
            if child is None:
                continue
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

        self._row_offset_input.setMaximum(max(0, shape[0] - 1) if ndim >= 1 else 0)
        self._row_limit_input.setMaximum(max(1, shape[0]) if ndim >= 1 else 1)
        self._col_offset_input.setMaximum(max(0, shape[1] - 1) if ndim >= 2 else 0)
        self._col_limit_input.setMaximum(max(1, shape[1]) if ndim >= 2 else 1)

        if ndim <= 2:
            self._row_offset_input.setValue(0)
            self._col_offset_input.setValue(0)
            self._row_limit_input.setValue(min(256, max(1, shape[0])) if ndim >= 1 else 1)
            self._col_limit_input.setValue(
                min(256, max(1, shape[1])) if ndim >= 2 else 1
            )
            return

        for axis in range(ndim - 2):
            spin = QSpinBox(self)
            spin.setObjectName(f"axis_{axis}_spin")
            spin.setMinimum(0)
            spin.setMaximum(max(0, shape[axis] - 1))
            spin.setValue(0)
            spin.valueChanged.connect(self._mark_workspace_dirty)
            self._axis_dynamic_form.addRow(f"Axis {axis}", spin)
            self._axis_controls[axis] = spin
            self._axis_configs.append(_AxisControlConfig(axis=axis, span=(0, 0)))

    def _configure_row_col_limits(self, metadata: DataMetadata) -> None:
        shape = metadata.shape
        if not shape:
            return
        if len(shape) >= 1:
            self._row_limit_input.setValue(min(256, max(1, shape[0])))
            self._row_offset_input.setMaximum(max(0, shape[0] - 1))
            self._row_limit_input.setMaximum(max(1, shape[0]))
        if len(shape) >= 2:
            self._col_offset_input.setMaximum(max(0, shape[1] - 1))
            self._col_limit_input.setMaximum(max(1, shape[1]))
            self._col_limit_input.setValue(min(256, max(1, shape[1])))

    def _build_selection(
        self,
        metadata: DataMetadata,
        *,
        force_refresh_axes: bool = False,
    ) -> SelectionSpec | None:
        shape = metadata.shape
        if not isinstance(shape, tuple) or metadata.domain != DataDomain.ARRAY:
            return None

        dims = tuple(shape)
        ndim = len(dims)
        if force_refresh_axes:
            self._configure_row_col_limits(metadata)
        self._latest_slice["row_offset"] = max(
            0,
            min(
                self._row_offset_input.value(),
                max(0, dims[0] - 1) if ndim >= 1 else 0,
            ),
        )
        self._latest_slice["col_offset"] = max(
            0,
            min(
                self._col_offset_input.value(),
                max(0, dims[1] - 1) if ndim >= 2 else 0,
            ),
        )
        row_limit = max(1, min(self._row_limit_input.value(), dims[0])) if ndim >= 1 else 1
        col_limit = max(1, min(self._col_limit_input.value(), dims[1])) if ndim >= 2 else 1
        self._latest_slice["row_limit"] = row_limit
        self._latest_slice["col_limit"] = col_limit

        specs: list[AxisSelection] = []

        if ndim == 0:
            return SelectionSpec.all()

        if ndim == 1:
            start = self._latest_slice["row_offset"]
            stop = min(start + row_limit, dims[0])
            specs.append(
                AxisSelection.slice(0, start=start, stop=stop, step=1)
            )
        elif ndim >= 2:
            if ndim > 2:
                for axis in range(ndim - 2):
                    spin = self._axis_controls.get(axis)
                    if spin is None:
                        return None
                    specs.append(AxisSelection(axis=axis, index=spin.value()))
            # row slice on the penultimate axis
            axis = ndim - 2
            row_start = self._latest_slice["row_offset"]
            row_stop = min(row_start + row_limit, dims[axis])
            specs.append(AxisSelection.slice(axis, start=row_start, stop=row_stop, step=1))
            # col slice on the last axis
            axis = ndim - 1
            col_start = self._latest_slice["col_offset"]
            col_stop = min(col_start + col_limit, dims[axis])
            specs.append(AxisSelection.slice(axis, start=col_start, stop=col_stop, step=1))
            if ndim == 2:
                pass
        return SelectionSpec.hyperslab(*specs)

    def _build_selection_for_resource(
        self, metadata: DataMetadata,
    ) -> SelectionSpec | None:
        return self._build_selection(metadata)

    # ----------------------------- workspace/metadata rendering -----------------------------
    def _render_metadata(self, metadata: DataMetadata) -> None:
        lines: list[str] = [
            f"name: {metadata.name}",
            f"resource: {metadata.resource_id.node_path}",
            f"domain: {metadata.domain}",
            f"node kind: {metadata.node_kind}",
            f"shape: {metadata.shape}",
            f"dtype: {metadata.dtype or '-'}",
            f"logical size: {metadata.logical_size_bytes if metadata.logical_size_bytes is not None else '-'}",
            f"storage size: {metadata.storage_size_bytes if metadata.storage_size_bytes is not None else '-'}",
            f"capabilities: {[cap.name for cap in metadata.capabilities]}",
        ]
        if metadata.attributes:
            lines.append("")
            lines.append("attributes:")
            try:
                lines.extend(
                    f"  - {name}: {json.dumps(value, ensure_ascii=False)}"
                    for name, value in dict(metadata.attributes).items()
                )
            except Exception:
                lines.extend(
                    f"  - {name}: {value}" for name, value in dict(metadata.attributes).items()
                )
        self._inspector.setPlainText("\n".join(lines))

    def _set_workspace_status(self, state: str, message: str) -> None:
        self._workspace_status.setText(f"{state}: {message}")

    def _set_workspace_state(
        self,
        state: str,
        message: str,
        *,
        update_status_bar: bool = True,
    ) -> None:
        self._set_workspace_status(state, message)
        if update_status_bar:
            self._status_bar.showMessage(message, 4000)
        if state in {"error", "empty"}:
            self._status_label.setText("No ready view")

    def _clear_load_more_children(self, item: QTreeWidgetItem) -> None:
        for row in range(item.childCount() - 1, -1, -1):
            child = item.child(row)
            if child is not None and bool(child.data(0, ROLE_LOAD_MORE)):
                item.removeChild(child)

    def _open_resource_in_workspace(self, resource_id: ResourceId, document: DocumentController) -> None:
        self._active_resource = resource_id
        self._active_read_result = None
        document_snapshot = document.snapshot()
        if document_snapshot.active_resource_id != resource_id:
            request = document.navigate_to(resource_id)
            resource_key = _node_key_for(resource_id)
            if resource_key is None:
                return
            self._active_read_generation_by_resource[resource_key] = request.request_generation
        self._set_workspace_state("loading", f"Loading resource: {resource_id.node_path}")
        try:
            metadata = document.get_metadata(resource_id, cancellation=CancellationToken())
            self._active_metadata = metadata
            self._render_metadata(metadata)
            self._status_shape.setText(f"shape: {metadata.shape or '(scalar)'}")
            self._status_dtype.setText(f"dtype: {metadata.dtype or '-'}")
            self._status_path.setText(f"path: {metadata.resource_id.node_path}")
            self._status_scope.setText("slice: pending")
            self._status_readonly.setText(
                "mode: read-only" if DataDomain(metadata.domain) in {DataDomain.ARRAY} else "mode: inspect"
            )
            self._refresh_edit_actions()
            if metadata.domain == DataDomain.ARRAY:
                self._schedule_read(document, resource_id, metadata, force_refresh_axes=True)
            else:
                self._set_workspace_state(
                    "partial", "Selected resource is not an array payload in v1 shell."
                )
        except DataViewerError as error:
            self._append_bottom(f"Failed opening workspace for {resource_id}: {error.message}")
            self._set_workspace_state("error", error.message)

    def _set_active_status(self, resource_id: ResourceId) -> None:
        state = f"path: {resource_id.node_path}"
        self._status_path.setText(state)
        self._status_scope.setText("slice: pending")

    def _set_status_scope(self, selection: SelectionSpec) -> None:
        self._status_scope.setText(f"slice: {self._format_selection_for_status(selection)}")

    def _format_selection_for_status(self, selection: SelectionSpec) -> str:
        parts: list[str] = []
        for axis in selection.axes:
            if axis.index is not None:
                parts.append(f"[{axis.axis}:{axis.index}]")
            else:
                if axis.start is None or axis.stop is None:
                    parts.append(f"[{axis.axis}:?]")
                else:
                    if axis.step in (None, 1):
                        parts.append(f"[{axis.axis}:{axis.start}:{axis.stop}]")
                    else:
                        parts.append(f"[{axis.axis}:{axis.start}:{axis.stop}:{axis.step}]")
        return " ".join(parts) if parts else "full"

    # ----------------------------- tree text -----------------------------------
    def _tree_node_text(self, node: Any) -> str:
        if not hasattr(node, "name"):
            return "unknown"
        text = str(node.name)
        if getattr(node, "has_children", False):
            return f"{text} /"
        return text

    # ----------------------------- close -----------------------------
    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self._open_command.cancel_all()
        for thread, token in tuple(self._background_tasks.items()):
            token.cancel()
            thread.join(timeout=0.1)
        self._drain_background_threads()
        self._active_document = None
        self._active_document_token = None
        self._active_resource = None
        self._active_metadata = None
        self._active_read_result = None
        self._active_request_generation_by_resource.clear()
        self._active_read_generation_by_resource.clear()
        self._workspace_model.clear()
        self._refresh_edit_actions()
        for document in list(self._open_documents):
            try:
                document.close(timeout=0.2)
            except Exception as error:  # pragma: no cover - defensive shell boundary
                self._append_bottom(f"Could not close document {document.source_uri}: {error}")
        self._open_documents.clear()
        super().closeEvent(event)


def launch_shell(*, startup_path: Path | None = None) -> DataViewerShell:
    """Create and show the shell in the current QApplication."""

    if QApplication.instance() is None:
        raise RuntimeError("QApplication instance is required before launching shell.")
    shell = DataViewerShell()
    if startup_path is not None:
        shell.open_file(startup_path, _start_from_ui=False, _show_feedback=False)
    shell.show()
    return shell


__all__ = ["DataViewerShell", "launch_shell", "create_source_registry"]
