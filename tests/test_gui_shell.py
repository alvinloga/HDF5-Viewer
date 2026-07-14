"""Target shell bootstrap and command-path tests."""

from __future__ import annotations

import time
from pathlib import Path

import h5py
import numpy as np
import pytest

from PyQt6.QtWidgets import (
    QApplication,
    QLineEdit,
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
