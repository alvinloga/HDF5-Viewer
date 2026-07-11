"""Regression tests for the legacy suite's test-process lifecycle."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

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
