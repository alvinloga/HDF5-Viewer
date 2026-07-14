"""Target shell bootstrap and command-path tests."""

from __future__ import annotations

import time
from pathlib import Path

import h5py
import numpy as np
import pytest

from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication, QLineEdit, QPushButton, QPlainTextEdit, QListWidget

from data_viewer.domain import DataViewerError, ErrorCode
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
    assert shell.findChild(QListWidget, "navigation_region") is not None
    assert shell.findChild(QListWidget, "workspace_region") is not None
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
    """Opening a valid file creates one active document and updates workspace list."""

    fixture_path = tmp_path / "sample.h5"
    with h5py.File(fixture_path, "w") as handle:
        handle.create_dataset("values", data=np.arange(8).reshape(2, 4))

    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    handle = shell.open_file(fixture_path)
    assert handle is not None
    _pump_events(cycles=60)
    assert shell.findChild(QPushButton, "cancel_open_button").isEnabled() is False

    assert len(shell._open_documents) == 1
    workspace = shell.findChild(QListWidget, "workspace_region")
    assert workspace is not None
    assert workspace.item(0).text().startswith("Opened: sample.h5")

    shell.closeEvent(QCloseEvent())
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

    shell._handle_cancel_open()
    handle.join(timeout=1.0)
    _pump_events(cycles=40)
    assert handle.thread.is_alive() is False
    assert len(shell._open_documents) == 0

    shell.close()
