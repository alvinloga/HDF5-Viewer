"""Target shell bootstrap and command-path tests."""

from __future__ import annotations

import time
from pathlib import Path

import h5py
import numpy as np
import pytest

from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QTreeWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QTreeWidget,
)

from data_viewer.domain import (
    AxisSelection,
    DataDomain,
    DataMetadata,
    NodeKind,
    ResourceId,
    SelectionSpec,
)
from data_viewer.domain.errors import DataViewerError
from data_viewer.domain import ErrorCode
from data_viewer.sources import SourceRegistry
from data_viewer.sources.hdf5 import HDF5Adapter
from data_viewer.gui.shell import DataViewerShell
from data_viewer.gui import shell as shell_module


@pytest.fixture
def qapp():
    """Reuse or create one QApplication for shell-level tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication(["data-viewer-test"])
    yield app
    app.processEvents()


def _pump_events(cycles: int = 120, sleep: float = 0.02) -> None:
    """Pump Qt event loop for a bounded amount of time."""

    for _ in range(cycles):
        QApplication.processEvents()
        time.sleep(sleep)


def test_shell_layout_components(qapp: QApplication) -> None:
    """The bootstrap shell exposes required command and region widgets."""

    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    shell.show()
    assert shell.findChild(QLineEdit, "path_input") is not None
    assert isinstance(shell.findChild(QPushButton, "open_button"), QPushButton)
    assert isinstance(shell.findChild(QPushButton, "cancel_open_button"), QPushButton)
    assert isinstance(shell.findChild(QTreeWidget, "navigation_region"), QTreeWidget)
    assert isinstance(shell.findChild(QTableView, "workspace_region"), QTableView)
    assert shell.findChild(QPlainTextEdit, "inspector_region") is not None
    assert shell.findChild(QPlainTextEdit, "bottom_region") is not None
    shell.close()


def test_open_invalid_path_is_reported_without_crash(qapp: QApplication, tmp_path: Path) -> None:
    """Invalid input path writes to the bottom output panel and returns no handle."""

    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    handle = shell.open_file(tmp_path / "missing.h5")
    assert handle is None
    bottom_text = shell.findChild(QPlainTextEdit, "bottom_region").toPlainText()
    assert "Open skipped: path does not exist" in bottom_text
    shell.close()


def test_opening_hdf5_file_updates_shell_state(qapp: QApplication, tmp_path: Path) -> None:
    """Opening a valid file updates workspace/document state and metadata."""

    fixture_path = tmp_path / "sample.h5"
    with h5py.File(fixture_path, "w") as handle:
        handle.create_dataset("values", data=np.arange(8).reshape(2, 4))

    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    handle = shell.open_file(fixture_path)
    assert handle is not None
    _pump_events(cycles=120)
    assert shell.findChild(QPushButton, "cancel_open_button").isEnabled() is False

    assert len(shell._open_documents) == 1
    assert shell._active_document is not None
    assert shell.findChild(QTableView, "workspace_region") is not None

    root = shell.findChild(QTreeWidget, "navigation_region")
    assert root is not None
    assert root.topLevelItemCount() >= 1
    root_item = root.topLevelItem(0)
    assert root_item is not None

    shell.close()
    assert len(shell._open_documents) == 0


def test_open_can_be_cancelled_during_open(qapp: QApplication, tmp_path: Path) -> None:
    """Cancel Open interrupts an in-flight open and keeps shell state clean."""

    class SlowRegistry(SourceRegistry):
        def open(self, path: Path, *, cancellation) -> object:
            for _ in range(100):
                if cancellation.is_cancelled:
                    raise DataViewerError(
                        code=ErrorCode.READ_CANCELLED,
                        message="open cancelled by test harness",
                        operation="test_slow_open",
                    )
                time.sleep(0.02)
            raise AssertionError("Test open completed before cancellation.")

    slow_fixture = tmp_path / "slow.bin"
    slow_fixture.write_text("x", encoding="utf-8")
    shell = DataViewerShell(source_registry=SlowRegistry(()))
    handle = shell.open_file(slow_fixture)
    assert handle is not None

    assert shell._open_command.active_count() == 1
    shell._handle_cancel_open()
    handle.join(timeout=1.0)
    _pump_events(cycles=40)
    assert handle.thread.is_alive() is False
    assert len(shell._open_documents) == 0
    assert shell._open_command.active_count() == 0

    shell.close()


def test_high_dimensional_axis_controls_build_selection(qapp: QApplication) -> None:
    """Axis controls generate explicit index axes and row/col slicing."""

    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    metadata = DataMetadata(
        resource_id=ResourceId("mem://local", "/tensor"),
        name="tensor",
        domain=DataDomain.ARRAY,
        node_kind=NodeKind.RESOURCE,
        shape=(2, 3, 4),
        dtype="float32",
    )

    shell._configure_axis_controls(metadata)
    assert len(shell._axis_controls) == 1
    axis_spin = shell._axis_controls[0]
    axis_spin.setValue(1)

    shell._row_offset_input.setValue(1)
    shell._row_limit_input.setValue(2)
    shell._col_offset_input.setValue(1)
    shell._col_limit_input.setValue(2)

    spec = shell._build_selection(metadata)
    assert spec is not None
    normalized = spec.normalize(metadata.shape).unwrap()
    assert normalized.axes[0].index == 1
    assert normalized.axes[1].start == 1
    assert normalized.axes[1].stop == 3
    assert normalized.axes[2].start == 1
    assert normalized.axes[2].stop == 3
    shell.close()


def test_selection_status_format(qapp: QApplication) -> None:
    """Selection formatting emits concise axis tokens for status display."""

    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    metadata = SelectionSpec.hyperslab(
        AxisSelection(axis=0, index=1),
        AxisSelection.slice(1, start=2, stop=6, step=1),
        AxisSelection.slice(2, start=1, stop=4, step=2),
    )

    assert shell._format_selection_for_status(metadata) == "[0:1] [1:2:6] [2:1:4:2]"
    shell.close()


def _make_dataset_file(path: Path, count: int) -> None:
    with h5py.File(path, "w") as handle:
        bulk = handle.create_group("bulk")
        for i in range(count):
            bulk.create_dataset(f"item_{i:03d}", data=np.array([i], dtype=np.int64))
        handle.create_dataset("matrix", data=np.arange(12, dtype=np.int64).reshape(3, 4))


def _find_node_by_name(
    parent: QTreeWidget | QTreeWidgetItem,
    name: str,
) -> QTreeWidgetItem | None:
    if parent is None:
        return None

    if isinstance(parent, QTreeWidget):
        iterator = range(parent.topLevelItemCount())
        get_child = parent.topLevelItem
    elif isinstance(parent, QTreeWidgetItem):
        iterator = range(parent.childCount())

        def get_child(idx: int) -> QTreeWidgetItem | None:
            return parent.child(idx)
    else:
        return None

    for index in iterator:
        child = get_child(index)
        if child is None:
            continue
        label = child.text(0)
        if label.rstrip(" /") == name:
            return child
    return None


def test_lazy_tree_expansion_and_load_more(qapp: QApplication, tmp_path: Path) -> None:
    """Children are loaded on demand and load-more placeholders fetch next page."""

    fixture_path = tmp_path / "pagination.h5"
    _make_dataset_file(fixture_path, 700)

    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    handle = shell.open_file(fixture_path)
    assert handle is not None
    _pump_events(cycles=160)

    tree = shell.findChild(QTreeWidget, "navigation_region")
    assert tree is not None
    root = tree.topLevelItem(0)
    assert root is not None

    bulk_node = _find_node_by_name(root, "bulk")
    assert isinstance(bulk_node, shell_module.QTreeWidgetItem)
    shell._on_navigation_item_expanded(bulk_node)
    _pump_events(cycles=160)

    # First page must not include all items and should show load-more node.
    load_more_before = next(
        (
            child
            for i in range(bulk_node.childCount())
            for child in [bulk_node.child(i)]
            if child is not None and child.data(0, shell_module.ROLE_LOAD_MORE)
        ),
        None,
    )
    assert load_more_before is not None
    load_more_before_count = bulk_node.childCount()
    assert bulk_node.childCount() > 256

    shell._on_navigation_item_activated(load_more_before, 0)
    _pump_events(cycles=200)
    load_more_after = next(
        (
            child
            for i in range(bulk_node.childCount())
            for child in [bulk_node.child(i)]
            if child is not None and child.data(0, shell_module.ROLE_LOAD_MORE)
        ),
        None,
    )
    assert load_more_after is not None
    assert bulk_node.childCount() > load_more_before_count

    shell.close()


def test_enter_open_updates_workspace_and_active_status(qapp: QApplication, tmp_path: Path) -> None:
    """Enter/open actions keep active resource status and workspace metadata in sync."""

    fixture_path = tmp_path / "matrix.h5"
    with h5py.File(fixture_path, "w") as handle:
        handle.create_dataset("values", data=np.arange(24, dtype=np.float64).reshape(3, 8))

    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    handle = shell.open_file(fixture_path)
    assert handle is not None
    _pump_events(cycles=120)

    tree = shell.findChild(QTreeWidget, "navigation_region")
    assert tree is not None
    root = tree.topLevelItem(0)
    assert root is not None

    dataset_node = _find_node_by_name(root, "values")
    assert isinstance(dataset_node, shell_module.QTreeWidgetItem)
    shell._on_navigation_item_activated(dataset_node, 0)
    _pump_events(cycles=200)

    status_shape = shell.findChild(QLabel, "status_shape")
    status_dtype = shell.findChild(QLabel, "status_dtype")
    status_path = shell.findChild(QLabel, "status_path")
    status_scope = shell.findChild(QLabel, "status_scope")
    assert status_shape is not None
    assert status_dtype is not None
    assert status_path is not None
    assert status_scope is not None

    assert "shape: (3, 8)" in status_shape.text()
    assert "dtype: float64" in status_dtype.text()
    assert "/values" in status_path.text()
    assert "slice:" in status_scope.text()
    assert shell.findChild(QTableView, "workspace_region").model().rowCount() == 3

    shell.close()
