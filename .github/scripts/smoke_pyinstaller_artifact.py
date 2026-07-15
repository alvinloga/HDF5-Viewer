"""Smoke-test a built Data Viewer PyInstaller executable."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test Data Viewer executable.")
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    executable = Path(manifest["executable"])
    if not executable.exists():
        raise FileNotFoundError(executable)
    completed = subprocess.run(
        [str(executable), "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if "Data Viewer" not in completed.stdout:
        raise AssertionError(f"Unexpected version output: {completed.stdout!r}")
    print(completed.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
