"""Packaging contracts for Data Viewer PyInstaller artifacts."""

from __future__ import annotations

import subprocess
import sys
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


def test_ci_compile_gate_excludes_legacy_runtime_paths() -> None:
    """DV-1008 keeps release compile gates focused on target Data Viewer paths."""

    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text())
    steps = workflow["jobs"]["quality"]["steps"]
    compile_step = next(step for step in steps if step["name"] == "Compile Data Viewer target paths")
    compile_command = compile_step["run"]

    assert "data_viewer" in compile_command
    assert ".github/scripts" in compile_command
    assert "tools" in compile_command
    for legacy_path in ("core", "gui", "plugins", "services", "utils", "main.py"):
        assert legacy_path not in compile_command


def test_legacy_pyinstaller_build_entrypoints_are_removed() -> None:
    """DV-1008 removes obsolete legacy release launchers from the root packaging surface."""

    for legacy_entrypoint in ("HDF5Viewer.spec", "build_windows.py", "build_windows.bat"):
        assert not (PROJECT_ROOT / legacy_entrypoint).exists()

    build_script = PROJECT_ROOT / "build.py"
    text = build_script.read_text(encoding="utf-8")
    assert "Data Viewer" in text
    assert "tools/build_pyinstaller_artifact.py" in text
    for legacy_token in ("HDF5Viewer", "HDF5Viewer.spec", "main.py", "hdf5viewer_build"):
        assert legacy_token not in text


def test_root_build_wrapper_does_not_shadow_pypa_build_module() -> None:
    """DV-1008 keeps the standard wheel/sdist build entry point usable."""

    result = subprocess.run(
        [sys.executable, "-m", "build", "--version"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert "build.py: error" not in result.stderr
    assert "Traceback" not in result.stderr
    if result.returncode == 0:
        assert "build " in result.stdout
    else:
        assert "PyPA build is not installed" in result.stderr


def test_legacy_packaged_build_smoke_suite_is_removed() -> None:
    """DV-1008 uses target artifact smoke tests instead of legacy source imports."""

    legacy_packaged_suite = PROJECT_ROOT / "tests" / "test_packaged.py"
    assert not legacy_packaged_suite.exists()

    target_smoke = (PROJECT_ROOT / "tests" / "test_installed_artifact_smoke.py").read_text(
        encoding="utf-8"
    )
    assert "run_installed_artifact_smoke" in target_smoke
    assert "--ci-smoke" in target_smoke

    for legacy_import in ("from core", "from gui", "from plugins", "from services"):
        assert legacy_import not in target_smoke


def test_legacy_final_integration_smoke_script_is_removed() -> None:
    """DV-1008 removes the obsolete source-import final integration script."""

    legacy_final_suite = PROJECT_ROOT / "tests" / "test_final.py"
    assert not legacy_final_suite.exists()

    environment_test = (
        PROJECT_ROOT / "tests" / "test_test_environment.py"
    ).read_text(encoding="utf-8")
    assert "test_final.py" not in environment_test

    for target_test in (
        "tests/test_data_viewer_package.py",
        "tests/test_installed_artifact_smoke.py",
        "tests/test_integration.py",
    ):
        assert (PROJECT_ROOT / target_test).exists()


def test_legacy_all_features_smoke_script_is_removed() -> None:
    """DV-1008 removes the obsolete comprehensive legacy smoke script."""

    legacy_all_features_suite = PROJECT_ROOT / "tests" / "test_all_features.py"
    assert not legacy_all_features_suite.exists()

    environment_test = (
        PROJECT_ROOT / "tests" / "test_test_environment.py"
    ).read_text(encoding="utf-8")
    assert "test_all_features.py" not in environment_test

    for retained_suite in (
        "tests/test_integration.py",
        "tests/test_gui_interaction.py",
        "tests/test_comprehensive.py",
    ):
        assert (PROJECT_ROOT / retained_suite).exists()


def test_legacy_core_test_manual_runner_is_removed() -> None:
    """DV-1008 keeps legacy core tests as pytest tests, not standalone scripts."""

    core_test = (PROJECT_ROOT / "tests" / "test_core.py").read_text(encoding="utf-8")

    assert "Legacy HDF5 Viewer - Core Module Tests" not in core_test
    assert "def main(" not in core_test
    assert '__name__ == "__main__"' not in core_test
