"""Regression tests for the legacy suite's test-process lifecycle."""

from __future__ import annotations

import os
import locale
import subprocess
import sys
from pathlib import Path

import h5py
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MULTI_MODULE_GUI_COLLECTION = [
    "tests/test_gui_interaction.py",
    "tests/test_phase1.py",
    "tests/test_comprehensive.py",
]


def test_qt_platform_is_configured_before_gui_modules_import() -> None:
    """Headless collection must choose Qt's offscreen platform up front."""
    assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"


def test_locale_and_timezone_are_stable_for_each_test() -> None:
    """Locale-sensitive formatting must not inherit a developer workstation setting."""
    assert os.environ.get("TZ") == "UTC"
    assert locale.setlocale(locale.LC_ALL) == "C"


def test_gui_config_writes_do_not_modify_repository_config(qapp) -> None:
    """Theme changes in tests are redirected away from the checked-in config."""
    from gui.main_window import MainWindow

    repository_config = PROJECT_ROOT / "config.json"
    before = repository_config.read_bytes()
    window = MainWindow({"ui": {"theme": "dark"}})

    window._toggle_theme()

    assert repository_config.read_bytes() == before


def test_main_window_does_not_mutate_application_stylesheet(qapp) -> None:
    """Each window must own its theme without replacing Qt's process-wide style."""
    from gui.main_window import MainWindow

    original_style = qapp.styleSheet()
    sentinel_style = "QWidget { color: magenta; }"
    window = None
    qapp.setStyleSheet(sentinel_style)
    try:
        window = MainWindow({"ui": {"theme": "dark"}})

        assert qapp.styleSheet() == sentinel_style
        assert "QMainWindow" in window.styleSheet()
    finally:
        if window is not None:
            window.close()
            window.deleteLater()
        qapp.setStyleSheet(original_style)


def test_tab_manager_closes_file_panels_before_removing_them(tmp_path, monkeypatch, qapp) -> None:
    """Removing a tab must run its panel lifecycle before releasing its source."""
    from core.h5_source import H5Source
    from core.registry import DataSourceRegistry
    from gui.editor.file_panel import FilePanel
    from gui.editor.tab_manager import TabManager

    file_path = tmp_path / "tab-lifecycle.h5"
    with h5py.File(file_path, "w") as file:
        file.create_dataset("values", data=[1, 2, 3])

    DataSourceRegistry.register(H5Source)
    manager = TabManager()
    assert manager.open_file(str(file_path))
    panel = manager._panels[str(file_path)]
    closed_panels = []

    monkeypatch.setattr(FilePanel, "close", lambda value: closed_panels.append(value))

    manager.close_file(str(file_path))

    assert closed_panels == [panel]


def test_file_panel_close_requests_cooperative_thread_stop(qapp) -> None:
    """Closing a panel must never force-terminate a data-load thread."""
    from core.h5_source import H5Source
    from gui.editor.file_panel import FilePanel

    class RunningThread:
        def __init__(self) -> None:
            self.interruption_requested = False
            self.wait_timeouts = []

        def isRunning(self) -> bool:
            return True

        def requestInterruption(self) -> None:
            self.interruption_requested = True

        def wait(self, timeout: int) -> bool:
            self.wait_timeouts.append(timeout)
            return True

    panel = FilePanel(H5Source())
    thread = RunningThread()
    panel._load_thread = thread

    panel.close()

    assert thread.interruption_requested
    assert thread.wait_timeouts == [5_000]


def test_parent_tab_stays_open_when_a_child_panel_cannot_stop(tmp_path, monkeypatch, qapp) -> None:
    """A shared source remains open until every child panel has stopped loading."""
    from core.h5_source import H5Source
    from core.registry import DataSourceRegistry
    from gui.editor.file_panel import FilePanel
    from gui.editor.tab_manager import TabManager

    file_path = tmp_path / "shared-source.h5"
    with h5py.File(file_path, "w") as file:
        file.create_dataset("values", data=[1, 2, 3])

    DataSourceRegistry.register(H5Source)
    manager = TabManager()
    key = str(file_path)
    assert manager.open_file(key)
    source = manager._panels[key].get_source()

    child = FilePanel(source, manager)
    child_key = f"{key}::/values"
    tab_widget = manager._tab_groups[0]
    tab_widget.addTab(child, "values")
    manager._panels[child_key] = child
    manager._panel_to_key[id(child)] = child_key
    manager._file_to_group[child_key] = 0
    monkeypatch.setattr(child, "stop_loading", lambda: False)

    manager.close_file(key)

    assert key in manager.get_all_paths()
    assert child_key in manager.get_all_paths()
    assert source.is_open()


def test_registry_cleanup_releases_open_hdf5_sources(tmp_path) -> None:
    """Legacy per-test cleanup must release handles before temp files are removed."""
    from core.h5_source import H5Source
    from core.registry import DataSourceRegistry

    file_path = tmp_path / "cleanup.h5"
    with h5py.File(file_path, "w") as file:
        file.create_dataset("values", data=[1, 2, 3])

    DataSourceRegistry.register(H5Source)
    source = DataSourceRegistry.get(str(file_path))
    source.open(str(file_path))

    DataSourceRegistry.close_all()

    assert not source.is_open()


def test_gui_module_collection_exits_after_importing_multiple_modules() -> None:
    """Collection must not leave a second QApplication keeping pytest alive."""
    environment = os.environ.copy()
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                *MULTI_MODULE_GUI_COLLECTION,
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired as error:
        pytest.fail(
            "GUI module collection did not exit within 10 seconds.\n"
            f"stdout:\n{error.stdout or ''}\n"
            f"stderr:\n{error.stderr or ''}"
        )

    assert completed.returncode == 0, completed.stdout + completed.stderr
