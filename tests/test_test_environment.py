"""Regression tests for the legacy suite's test-process lifecycle."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import h5py
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MULTI_MODULE_GUI_COLLECTION = [
    "tests/test_all_features.py",
    "tests/test_final.py",
    "tests/test_phase1.py",
]


def test_qt_platform_is_configured_before_gui_modules_import() -> None:
    """Headless collection must choose Qt's offscreen platform up front."""
    assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"


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
