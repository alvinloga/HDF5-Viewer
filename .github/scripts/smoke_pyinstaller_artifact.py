"""Smoke-test a built Data Viewer PyInstaller executable."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test Data Viewer executable.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--functional-workspace-dir", type=Path)
    parser.add_argument("--functional-report", type=Path)
    parser.add_argument("--functional-screenshot", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    executable = _resolve_manifest_path(args.manifest, manifest["executable"])
    if not executable.exists():
        raise FileNotFoundError(executable)
    completed = _run_executable(executable, ["--version"], timeout=30)
    if "Data Viewer" not in completed.stdout:
        raise AssertionError(f"Unexpected version output: {completed.stdout!r}")
    print(completed.stdout.strip())
    if args.functional_workspace_dir is not None:
        report = args.functional_report or (
            args.functional_workspace_dir / "installed-smoke-report.json"
        )
        screenshot = args.functional_screenshot or (
            args.functional_workspace_dir / "installed-smoke-screenshot.png"
        )
        completed = _run_executable(
            executable,
            [
                "--ci-smoke",
                str(args.functional_workspace_dir),
                "--ci-smoke-report",
                str(report),
                "--ci-smoke-screenshot",
                str(screenshot),
            ],
            timeout=120,
        )
        if not report.exists():
            raise FileNotFoundError(report)
        if not screenshot.exists():
            raise FileNotFoundError(screenshot)
        print(completed.stdout.strip())
    return 0


def _resolve_manifest_path(manifest_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def _run_executable(executable: Path, args: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(executable), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
