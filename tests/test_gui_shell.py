"""Target shell bootstrap and command-path tests."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

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
from data_viewer.editing.patches import CellPatch, fingerprint_value
from data_viewer.sources import SourceRegistry
from data_viewer.sources.delimited import DelimitedTextAdapter
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


def test_opening_csv_file_updates_table_workspace(qapp: QApplication, tmp_path: Path) -> None:
    """Opening a valid CSV file renders a paged table payload in the workspace."""

    fixture_path = tmp_path / "sample.csv"
    fixture_path.write_text("id,label\n1,alpha\n2,beta\n", encoding="utf-8")

    shell = DataViewerShell(source_registry=SourceRegistry([DelimitedTextAdapter()]))
    handle = shell.open_file(fixture_path)
    assert handle is not None
    _pump_events(cycles=120)

    tree = shell.findChild(QTreeWidget, "navigation_region")
    assert tree is not None
    root_item = tree.topLevelItem(0)
    assert root_item is not None
    table_item = _find_node_by_name(root_item, "table")
    assert table_item is not None
    shell._on_navigation_item_clicked(table_item, 0)
    _pump_events(cycles=120)

    assert shell._active_metadata is not None
    assert shell._active_metadata.domain is DataDomain.TABLE
    assert shell._workspace_model.rowCount() == 2
    assert shell._workspace_model.columnCount() == 2
    assert shell._workspace_model.data(shell._workspace_model.index(1, 1)) == "beta"
    assert "Workspace ready" in shell.findChild(QLabel, "workspace_status").text()
    shell.close()


def test_opening_txt_file_updates_text_workspace(qapp: QApplication, tmp_path: Path) -> None:
    """Opening a valid TXT file renders a bounded text payload in the workspace."""

    from data_viewer.sources.text import TXTAdapter

    fixture_path = tmp_path / "notes.txt"
    fixture_path.write_text("alpha\nbeta\n", encoding="utf-8")

    shell = DataViewerShell(source_registry=SourceRegistry([TXTAdapter()]))
    handle = shell.open_file(fixture_path)
    assert handle is not None
    _pump_events(cycles=120)

    tree = shell.findChild(QTreeWidget, "navigation_region")
    assert tree is not None
    root_item = tree.topLevelItem(0)
    assert root_item is not None
    text_item = _find_node_by_name(root_item, "text")
    assert text_item is not None
    shell._on_navigation_item_clicked(text_item, 0)
    _pump_events(cycles=120)

    assert shell._active_metadata is not None
    assert shell._active_metadata.domain is DataDomain.TEXT
    assert shell._workspace_model.rowCount() == 1
    assert shell._workspace_model.columnCount() == 1
    assert shell._workspace_model.data(shell._workspace_model.index(0, 0)) == "alpha\nbeta\n"
    assert "text preview" in shell.findChild(QLabel, "workspace_status").text()
    shell.close()


def test_opening_json_file_updates_structured_workspace(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    """Opening a JSON file renders a structured payload preview in the workspace."""

    from data_viewer.sources.json import JSONAdapter

    fixture_path = tmp_path / "sample.json"
    fixture_path.write_text('{"alpha": 1, "beta": [true]}', encoding="utf-8")

    shell = DataViewerShell(source_registry=SourceRegistry([JSONAdapter()]))
    handle = shell.open_file(fixture_path)
    assert handle is not None
    _pump_events(cycles=120)

    tree = shell.findChild(QTreeWidget, "navigation_region")
    assert tree is not None
    root_item = tree.topLevelItem(0)
    assert root_item is not None
    shell._on_navigation_item_clicked(root_item, 0)
    _pump_events(cycles=120)

    assert shell._active_metadata is not None
    assert shell._active_metadata.domain is DataDomain.STRUCTURED
    assert shell._workspace_model.rowCount() == 1
    assert shell._workspace_model.columnCount() == 1
    rendered = shell._workspace_model.data(shell._workspace_model.index(0, 0))
    assert '"alpha": 1' in rendered
    assert '"beta": [' in rendered
    assert "structured preview" in shell.findChild(QLabel, "workspace_status").text()
    shell.close()


def test_open_can_be_cancelled_during_open(qapp: QApplication, tmp_path: Path) -> None:
    """Cancel Open interrupts an in-flight open and keeps shell state clean."""

    class SlowRegistry(SourceRegistry):
        def open(self, path: Path, *, cancellation) -> Any:
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


def _pump_until(
    predicate: Callable[[], bool],
    cycles: int = 200,
    sleep: float = 0.02,
) -> bool:
    """Pump Qt events until predicate returns True or the cycle budget is exhausted."""

    for _ in range(cycles):
        QApplication.processEvents()
        time.sleep(sleep)
        if predicate():
            return True
    return False


def _build_hierarchical_file(path: Path, group_count: int, datasets_per_group: int) -> None:
    with h5py.File(path, "w") as handle:
        for group_index in range(group_count):
            group = handle.create_group(f"group_{group_index:04d}")
            for dataset_index in range(datasets_per_group):
                group.create_dataset(
                    f"values_{dataset_index:03d}",
                    data=np.arange(12, dtype=np.int64).reshape(3, 4),
                )


def test_large_hierarchy_is_lazy_and_does_not_uncontrolled_load(
    qapp: QApplication, tmp_path: Path
) -> None:
    """Large trees load only paginated children and remain deterministic when paginating."""

    fixture_path = tmp_path / "large_tree.h5"
    _build_hierarchical_file(fixture_path, group_count=640, datasets_per_group=1)

    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    handle = shell.open_file(fixture_path)
    assert handle is not None
    assert _pump_until(lambda: shell.findChild(QTreeWidget, "navigation_region").topLevelItemCount() == 1)

    tree = shell.findChild(QTreeWidget, "navigation_region")
    assert tree is not None
    root = tree.topLevelItem(0)
    assert root is not None
    shell._on_navigation_item_expanded(root)

    first_page_ready = _pump_until(
        lambda: root.childCount() > 0
        and any(
            root.child(i) is not None
            and bool(root.child(i).data(0, shell_module.ROLE_LOAD_MORE))
            for i in range(root.childCount())
        ),
    )
    assert first_page_ready
    assert 0 < root.childCount() <= 260

    seen_counts: list[int] = [root.childCount()]
    while True:
        load_more = None
        for i in range(root.childCount()):
            candidate = root.child(i)
            if candidate is not None and candidate.data(0, shell_module.ROLE_LOAD_MORE):
                load_more = candidate
                break
        if load_more is None:
            break

        shell._on_navigation_item_activated(load_more, 0)
        loaded = _pump_until(
            lambda: root.childCount() > seen_counts[-1],
            cycles=240,
        )
        assert loaded
        seen_counts.append(root.childCount())

    assert root.childCount() > 0
    final_item_count = root.childCount()
    final_has_load_more = any(
        root.child(i) is not None and bool(root.child(i).data(0, shell_module.ROLE_LOAD_MORE))
        for i in range(root.childCount())
    )
    assert final_item_count >= 640
    assert not final_has_load_more
    shell.close()


def test_repeated_open_and_close_remains_stable(qapp: QApplication, tmp_path: Path) -> None:
    """Repeated opens on the same shell maintain lifecycle state and keep handles clean."""

    fixture_path = tmp_path / "repeat.h5"
    _build_hierarchical_file(fixture_path, group_count=20, datasets_per_group=1)
    tree_top_count: int | None = None

    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    for _ in range(8):
        handle = shell.open_file(fixture_path)
        assert handle is not None
        tree_ready = _pump_until(
            lambda: shell.findChild(QTreeWidget, "navigation_region").topLevelItemCount() == 1,
            cycles=240,
        )
        assert tree_ready
        open_ready = _pump_until(lambda: len(shell._open_documents) == 1, cycles=240)
        assert open_ready

        assert len(shell._open_documents) == 1
        root = shell.findChild(QTreeWidget, "navigation_region").topLevelItem(0)
        assert root is not None and root.text(0) == fixture_path.name
        if tree_top_count is None:
            tree_top_count = shell.findChild(QTreeWidget, "navigation_region").topLevelItemCount()
        else:
            assert shell.findChild(QTreeWidget, "navigation_region").topLevelItemCount() == tree_top_count
        shell.close()
        _pump_until(lambda: len(shell._open_documents) == 0, cycles=160)
        assert len(shell._open_documents) == 0

    assert _pump_until(
        lambda: len(shell._background_tasks) == 0,
        cycles=200,
    )
    tree = shell.findChild(QTreeWidget, "navigation_region")
    assert tree is not None
    final_top_count = tree.topLevelItemCount()
    if tree_top_count is not None:
        assert final_top_count == tree_top_count


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


def _open_values_dataset(shell: DataViewerShell, fixture_path: Path) -> None:
    handle = shell.open_file(fixture_path)
    assert handle is not None
    assert _pump_until(
        lambda: shell.findChild(QTreeWidget, "navigation_region").topLevelItemCount() == 1,
        cycles=240,
    )
    tree = shell.findChild(QTreeWidget, "navigation_region")
    assert tree is not None
    root = tree.topLevelItem(0)
    assert root is not None
    shell._on_navigation_item_expanded(root)
    assert _pump_until(lambda: root.childCount() > 0, cycles=240)
    dataset_node = _find_node_by_name(root, "values")
    assert isinstance(dataset_node, shell_module.QTreeWidgetItem)
    shell._on_navigation_item_activated(dataset_node, 0)
    assert _pump_until(
        lambda: shell.findChild(QTableView, "workspace_region").model().rowCount() > 0,
        cycles=240,
    )


def test_edit_review_save_and_export_controls_are_textual_and_actionable(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    """Dirty/read-only save and export UI exposes non-color state and receipts."""

    fixture_path = tmp_path / "edit_export.h5"
    with h5py.File(fixture_path, "w") as handle:
        handle.create_dataset("values", data=np.arange(6, dtype=np.int64).reshape(2, 3))

    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    _open_values_dataset(shell, fixture_path)

    edit_state = shell.findChild(QLabel, "edit_state_label")
    readonly_hint = shell.findChild(QLabel, "readonly_hint_label")
    save_button = shell.findChild(QPushButton, "save_button")
    review_button = shell.findChild(QPushButton, "review_changes_button")
    export_button = shell.findChild(QPushButton, "export_button")
    assert edit_state is not None
    assert readonly_hint is not None
    assert save_button is not None
    assert review_button is not None
    assert export_button is not None
    assert "read-only source view" in readonly_hint.text()
    assert export_button.isEnabled()

    assert shell._active_resource is not None
    shell.record_edit_patch(
        CellPatch(
            resource_id=shell._active_resource,
            coordinate=(0, 1),
            old_value_fingerprint=fingerprint_value(1),
            new_value=41,
        )
    )
    assert "dirty" in edit_state.text()
    assert "1 pending" in edit_state.text()
    assert save_button.isEnabled()
    assert review_button.isEnabled()

    review_text = shell.review_active_edits()
    assert "target:" in review_text
    assert "/values" in review_text
    assert "cell: 1" in review_text

    assert shell.save_active_edits()
    assert "clean" in edit_state.text()
    assert not save_button.isEnabled()
    with h5py.File(fixture_path, "r") as handle:
        assert int(handle["values"][0, 1]) == 41

    target_path = tmp_path / "values.npy"
    receipt = shell.export_active_to_path(target_path)
    assert target_path.exists()
    assert receipt is not None
    assert receipt.outcome.value == "succeeded"
    bottom = shell.findChild(QPlainTextEdit, "bottom_region")
    assert bottom is not None
    assert "Export succeeded" in bottom.toPlainText()
    shell.close()


def test_conflict_state_disables_invalid_save_and_names_safe_choices(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    """Conflicted edits are not color-only and offer Reload/Save As/Cancel wording."""

    fixture_path = tmp_path / "conflict.h5"
    with h5py.File(fixture_path, "w") as handle:
        handle.create_dataset("values", data=np.arange(4, dtype=np.int64).reshape(2, 2))

    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    _open_values_dataset(shell, fixture_path)
    assert shell._active_resource is not None
    shell.record_edit_patch(
        CellPatch(
            resource_id=shell._active_resource,
            coordinate=(0, 0),
            old_value_fingerprint=fingerprint_value(0),
            new_value=9,
        )
    )

    shell.display_edit_conflict("file changed outside Data Viewer")
    edit_state = shell.findChild(QLabel, "edit_state_label")
    save_button = shell.findChild(QPushButton, "save_button")
    bottom = shell.findChild(QPlainTextEdit, "bottom_region")
    assert edit_state is not None
    assert save_button is not None
    assert bottom is not None
    assert "conflicted" in edit_state.text()
    assert not save_button.isEnabled()
    assert "Reload" in bottom.toPlainText()
    assert "Save As" in bottom.toPlainText()
    assert "Cancel" in bottom.toPlainText()
    shell.close()


def test_dirty_close_flow_and_shell_screenshot_render(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    """Pending edits keep close deterministic and the shell renders offscreen."""

    fixture_path = tmp_path / "close_screenshot.h5"
    with h5py.File(fixture_path, "w") as handle:
        handle.create_dataset("values", data=np.arange(4, dtype=np.int64).reshape(2, 2))

    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    shell.resize(1280, 820)
    shell.show()
    _open_values_dataset(shell, fixture_path)
    assert shell._active_resource is not None
    shell.record_edit_patch(
        CellPatch(
            resource_id=shell._active_resource,
            coordinate=(1, 1),
            old_value_fingerprint=fingerprint_value(3),
            new_value=33,
        )
    )

    screenshot = shell.grab()
    screenshot_path = tmp_path / "data-viewer-shell-dirty.png"
    assert not screenshot.isNull()
    assert screenshot.save(str(screenshot_path))
    assert screenshot_path.stat().st_size > 0
    assert shell.findChild(QPushButton, "save_button").isVisible()
    assert shell.findChild(QPushButton, "export_button").isVisible()

    shell.close()
    _pump_until(lambda: len(shell._open_documents) == 0, cycles=120)
    assert len(shell._open_documents) == 0
