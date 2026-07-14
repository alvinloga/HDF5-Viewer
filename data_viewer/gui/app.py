"""Application bootstrap for the target Data Viewer shell."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from PyQt6.QtWidgets import QApplication

from data_viewer import __version__
from data_viewer.gui.shell import launch_shell


def run_data_viewer(
    *,
    path: str | None = None,
    app_args: Sequence[str] | None = None,
) -> int:
    """Start the target Qt shell and enter the GUI event loop.

    Parameters
    ----------
    path:
        Optional file path opened on startup.
    app_args:
        Optional additional CLI args for the QApplication instance.

    Returns
    -------
    int
        Exit code from the GUI event loop.
    """

    qt_args = _build_qt_argv(sys.argv[0], app_args)
    app = QApplication(qt_args)
    app.setApplicationName("Data Viewer")
    app.setApplicationVersion(__version__)

    startup = Path(path) if path else None
    launch_shell(startup_path=startup)
    return int(app.exec())


def _build_qt_argv(program: str, app_args: Sequence[str] | None) -> list[str]:
    """Build the argument vector forwarded to QApplication."""

    args = [program]
    if app_args:
        args.extend(app_args)
    return args


__all__ = ["run_data_viewer"]
