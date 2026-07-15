"""Packaging contracts for Data Viewer PyInstaller artifacts."""

from __future__ import annotations

from pathlib import Path

import yaml

from data_viewer import __version__
from tools.build_pyinstaller_artifact import artifact_name, executable_name, platform_tag


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_COMPACT_NAME = "HDF5" + "Viewer"


def test_data_viewer_pyinstaller_spec_uses_current_product_name() -> None:
    spec = PROJECT_ROOT / "packaging" / "DataViewer.spec"
    text = spec.read_text(encoding="utf-8")

    assert "DataViewer" in text
    assert LEGACY_COMPACT_NAME not in text
    assert "data_viewer" in text
    assert "pyinstaller_entry.py" in text


def test_packaging_artifact_names_are_data_viewer_and_platform_specific() -> None:
    assert artifact_name(version=__version__, platform="win32") == (
        f"DataViewer-{__version__}-windows-x86_64.zip"
    )
    assert artifact_name(version=__version__, platform="linux") == (
        f"DataViewer-{__version__}-linux-x86_64.tar.gz"
    )
    assert executable_name(platform="win32") == "DataViewer.exe"
    assert executable_name(platform="linux") == "DataViewer"
    assert platform_tag("win32") == "windows-x86_64"
    assert platform_tag("linux") == "linux-x86_64"


def test_ci_builds_and_uploads_data_viewer_pyinstaller_artifacts() -> None:
    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text())
    steps = workflow["jobs"]["quality"]["steps"]
    step_names = [step["name"] for step in steps]

    assert "Build Data Viewer PyInstaller artifact" in step_names
    assert "Smoke-test Data Viewer executable" in step_names
    assert "Upload Data Viewer package artifact" in step_names
