"""Data Viewer command-line entry point."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Protocol

from . import __version__
from .gui import run_data_viewer
from .domain import DataViewerError, ErrorCode


class DataViewerRunner(Protocol):
    def __call__(self, *, path: str | None = None) -> int: ...


def main() -> int:
    """Run Data Viewer with explicit legacy fallback."""

    return main_with_handlers(
        run_data_viewer=run_data_viewer,
        run_legacy=_run_legacy_bootstrap,
    )


def main_with_handlers(
    *,
    run_data_viewer: DataViewerRunner = run_data_viewer,
    run_legacy: DataViewerRunner | None = None,
    argv: list[str] | None = None,
) -> int:
    """Run the CLI with injectable handlers for testability."""
    if run_legacy is None:
        run_legacy = _run_legacy_bootstrap

    parser = argparse.ArgumentParser(
        prog="data_viewer",
        description="Data Viewer command-line entry point.",
    )
    parser.add_argument("path", nargs="?", help="Optional source file to open.")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Start legacy HDF5 Viewer workflow explicitly.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print application version and exit.",
    )
    parser.add_argument(
        "--ci-smoke",
        type=Path,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--ci-smoke-report",
        type=Path,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--ci-smoke-screenshot",
        type=Path,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv[1:] if argv is not None else None)

    if args.version:
        print(f"Data Viewer {__version__}")
        return 0

    if args.ci_smoke is not None:
        from .installed_smoke import run_installed_artifact_smoke

        report_path = args.ci_smoke_report or (args.ci_smoke / "installed-smoke-report.json")
        run_installed_artifact_smoke(
            workspace_dir=args.ci_smoke,
            report_path=report_path,
            screenshot_path=args.ci_smoke_screenshot,
        )
        print(f"Data Viewer installed smoke passed: {report_path}")
        return 0

    if args.legacy or os.getenv("DATA_VIEWER_LEGACY") == "1":
        return run_legacy(path=args.path)

    return run_data_viewer(path=args.path)  # noqa: TRY300


def _run_legacy_bootstrap(*, path: str | None = None) -> int:
    """Run the legacy bootstrap in a subprocess so process lifecycle is isolated."""

    command = [sys.executable, str(_legacy_entrypoint())]
    if path:
        command.append(path)
    try:
        completed = subprocess.run(command, check=False)
        return int(completed.returncode)
    except Exception as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Unable to start legacy Data Viewer bootstrap.",
            operation="__main__._run_legacy_bootstrap",
            cause=exc,
        ) from exc


def _legacy_entrypoint() -> str:
    """Return the repository path to the legacy bootstrap script."""

    return str(Path(__file__).resolve().with_name("main.py"))


if __name__ == "__main__":
    raise SystemExit(main())
