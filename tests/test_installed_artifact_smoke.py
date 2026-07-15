"""Installed Data Viewer artifact functional smoke contracts."""

from __future__ import annotations

import json
from pathlib import Path

from data_viewer.__main__ import main_with_handlers
from data_viewer.installed_smoke import run_installed_artifact_smoke


def test_installed_artifact_smoke_runs_representative_workflow(tmp_path: Path) -> None:
    """The packaged-app smoke opens core formats, runs a plugin, exports, and closes."""

    report_path = tmp_path / "reports" / "installed-smoke.json"
    screenshot_path = tmp_path / "reports" / "installed-smoke.png"

    result = run_installed_artifact_smoke(
        workspace_dir=tmp_path / "workspace",
        report_path=report_path,
        screenshot_path=screenshot_path,
    )

    assert result["status"] == "passed"
    assert report_path.exists()
    assert screenshot_path.exists()
    assert screenshot_path.stat().st_size > 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert {item["format"] for item in report["opened"]} == {
        "csv",
        "gzip-csv",
        "hdf5",
        "nifti",
        "workspace",
    }
    assert report["plugin"]["plugin_id"] == "org.dataviewer.dataset_profile"
    assert report["plugin"]["state"] == "succeeded"
    assert report["export"]["outcome"] == "succeeded"
    assert Path(report["export"]["target_path"]).exists()
    assert report["closed_documents"] == 4


def test_cli_ci_smoke_mode_exits_without_launching_interactive_gui(tmp_path: Path) -> None:
    """The executable exposes a hidden CI smoke mode for packaged artifacts."""

    launched: list[str | None] = []

    exit_code = main_with_handlers(
        argv=[
            "data-viewer",
            "--ci-smoke",
            str(tmp_path / "workspace"),
            "--ci-smoke-report",
            str(tmp_path / "report.json"),
            "--ci-smoke-screenshot",
            str(tmp_path / "screenshot.png"),
        ],
        run_data_viewer=lambda *, path=None: launched.append(path) or 99,
    )

    assert exit_code == 0
    assert launched == []
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "screenshot.png").exists()


def test_ci_and_release_gate_require_installed_artifact_functional_smoke() -> None:
    """Release gating must depend on both matrix smoke jobs, not build alone."""

    quality_workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    release_workflow = Path(".github/workflows/build.yml").read_text(encoding="utf-8")
    smoke_script = Path(".github/scripts/smoke_pyinstaller_artifact.py").read_text(
        encoding="utf-8"
    )

    assert "Functional smoke installed Data Viewer artifact" in quality_workflow
    assert "--ci-smoke" in smoke_script
    assert "installed-smoke-report.json" in quality_workflow
    assert "installed-smoke-screenshot.png" in quality_workflow
    assert "needs: quality" in release_workflow
    assert "dry_run_tag" in release_workflow
