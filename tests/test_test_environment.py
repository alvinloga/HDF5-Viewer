"""Regression tests for the target suite's test-process lifecycle."""

from __future__ import annotations

import os
import locale
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MULTI_MODULE_GUI_COLLECTION = [
    "tests/test_gui_shell.py",
    "tests/test_gui_base_views.py",
]


def _format_subprocess_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def test_qt_platform_is_configured_before_gui_modules_import() -> None:
    """Headless collection must choose Qt's offscreen platform up front."""
    assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"


def test_locale_and_timezone_are_stable_for_each_test() -> None:
    """Locale-sensitive formatting must not inherit a developer workstation setting."""
    assert os.environ.get("TZ") == "UTC"
    assert locale.setlocale(locale.LC_ALL) == "C"


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
            f"stdout:\n{_format_subprocess_output(error.stdout)}\n"
            f"stderr:\n{_format_subprocess_output(error.stderr)}"
        )

    assert completed.returncode == 0, completed.stdout + completed.stderr
