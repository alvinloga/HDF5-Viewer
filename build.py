#!/usr/bin/env python3
"""Data Viewer release-build front end.

This wrapper keeps the repository root command small and delegates packaging to
`tools/build_pyinstaller_artifact.py`, which is the authoritative PyInstaller
builder used by CI.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
TARGET_BUILDER = PROJECT_ROOT / "tools" / "build_pyinstaller_artifact.py"


def _platform_name() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return sys.platform


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def _clean() -> None:
    for relative in (
        Path("artifacts") / "package",
        Path("dist") / "pyinstaller",
        Path("build") / "pyinstaller",
    ):
        shutil.rmtree(PROJECT_ROOT / relative, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Data Viewer release artifacts.")
    parser.add_argument("--clean", action="store_true", help="Remove Data Viewer package outputs first.")
    parser.add_argument("--test", action="store_true", help="Run the full local pytest suite before packaging.")
    parser.add_argument("--windows", action="store_true", help="Assert this build is running on Windows.")
    parser.add_argument("--linux", action="store_true", help="Assert this build is running on Linux.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts") / "package",
        help="Directory where the Data Viewer archive and manifest are written.",
    )
    args = parser.parse_args(argv)

    platform_name = _platform_name()
    if args.windows and platform_name != "windows":
        parser.error(f"--windows requested on {platform_name}")
    if args.linux and platform_name != "linux":
        parser.error(f"--linux requested on {platform_name}")

    if args.clean:
        _clean()

    if args.test:
        _run([sys.executable, "-m", "pytest", "-q"])

    _run(
        [
            sys.executable,
            str(TARGET_BUILDER),
            "--output-dir",
            str(args.output_dir),
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
