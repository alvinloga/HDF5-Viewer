#!/usr/bin/env python3
"""Data Viewer release-build front end.

This wrapper keeps the repository root command small and delegates packaging to
`tools/build_pyinstaller_artifact.py`, which is the authoritative PyInstaller
builder used by CI.
"""

from __future__ import annotations

import argparse
import runpy
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


def _is_project_root_path(path_entry: str) -> bool:
    candidate = Path(path_entry or ".")
    try:
        return candidate.resolve() == PROJECT_ROOT
    except OSError:
        return False


def _run_pypa_build(argv: list[str]) -> int:
    """Delegate ``python -m build`` to the installed PyPA build package.

    The repository keeps a root ``build.py`` for the legacy-compatible
    ``python build.py`` release command.  Without this guard, Python resolves
    ``python -m build`` to this file instead of the standard build frontend.
    """

    original_argv = sys.argv[:]
    original_path = sys.path[:]
    try:
        sys.argv = ["python -m build", *argv]
        sys.path = [entry for entry in sys.path if not _is_project_root_path(entry)]
        sys.modules.pop("build", None)
        runpy.run_module("build", run_name="__main__", alter_sys=True)
    except ImportError as exc:
        if exc.name == "build" or str(exc) == "No module named build":
            print(
                "PyPA build is not installed; install the project dev dependencies "
                "or run `uv build --no-sources`.",
                file=sys.stderr,
            )
            return 1
        raise
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return 0 if exc.code is None else 1
    finally:
        sys.argv = original_argv
        sys.path = original_path
    return 0


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
    module_spec = globals().get("__spec__")
    if module_spec is not None and getattr(module_spec, "name", None) == "build":
        raise SystemExit(_run_pypa_build(sys.argv[1:]))
    raise SystemExit(main())
