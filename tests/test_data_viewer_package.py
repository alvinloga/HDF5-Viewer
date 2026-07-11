"""Contract tests for the target Data Viewer package skeleton."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_package_exports_its_canonical_development_version() -> None:
    """The target package exposes the single version used by build metadata."""
    import data_viewer

    assert data_viewer.__version__ == "1.0.0.dev0"


def test_module_entrypoint_explains_that_the_bootstrap_is_not_ready() -> None:
    """The temporary entry point is intentional and helpful during migration."""
    completed = subprocess.run(
        [sys.executable, "-m", "data_viewer"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "Data Viewer development shell" in completed.stdout
    assert "bootstrap is not available yet" in completed.stdout
