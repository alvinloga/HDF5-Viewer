"""Data Viewer command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Protocol

from . import __version__
from .gui import run_data_viewer


class DataViewerRunner(Protocol):
    def __call__(self, *, path: str | None = None) -> int: ...


def main() -> int:
    """Run Data Viewer."""

    return main_with_handlers(run_data_viewer=run_data_viewer)


def main_with_handlers(
    *,
    run_data_viewer: DataViewerRunner = run_data_viewer,
    argv: list[str] | None = None,
) -> int:
    """Run the CLI with injectable handlers for testability."""

    parser = argparse.ArgumentParser(
        prog="data_viewer",
        description="Data Viewer command-line entry point.",
    )
    parser.add_argument("path", nargs="?", help="Optional source file to open.")
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

    return run_data_viewer(path=args.path)  # noqa: TRY300


if __name__ == "__main__":
    raise SystemExit(main())
