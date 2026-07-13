"""Write small, secret-free metadata for a GitHub Actions quality run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from pathlib import Path


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _lock_file_sha256(path: Path) -> str:
    """Return a stable lock-file hash independent of checkout line endings."""
    normalized_text = (
        path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    )
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def build_manifest(platform_name: str) -> dict[str, object]:
    """Return the non-secret metadata needed to interpret CI evidence."""
    lock_path = _repository_root() / "uv.lock"
    return {
        "schema_version": 1,
        "platform": platform_name,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "runner_machine": platform.machine(),
        "runner_system": platform.system(),
        "git_sha": os.environ.get("GITHUB_SHA", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "uv_lock_sha256": _lock_file_sha256(lock_path),
    }


def write_manifest(output_directory: Path, platform_name: str) -> Path:
    """Write and return the quality manifest path for one matrix platform."""
    output_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = output_directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(build_manifest(platform_name), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, dest="platform_name")
    parser.add_argument("--output-directory", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = write_manifest(args.output_directory, args.platform_name)
    print(f"quality-manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
