"""Release evidence contracts for Data Viewer artifacts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_release_evidence_module():
    module_path = PROJECT_ROOT / ".github" / "scripts" / "generate_release_evidence.py"
    spec = importlib.util.spec_from_file_location("generate_release_evidence", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_evidence_writes_checksums_sbom_notices_and_review(tmp_path: Path) -> None:
    """CI release evidence must be generated from package artifacts without path leaks."""

    evidence = _load_release_evidence_module()
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    archive = package_dir / "DataViewer-0.1.0-windows-x86_64.zip"
    archive.write_bytes(b"data-viewer-archive")
    (package_dir / "pyinstaller-manifest.json").write_text(
        json.dumps(
            {
                "app_name": "DataViewer",
                "version": "0.1.0",
                "platform": "windows-x86_64",
                "artifact": archive.name,
                "bundle_dir": "../dist/DataViewer",
                "executable": "../dist/DataViewer/DataViewer.exe",
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / "release-evidence"
    result = evidence.generate_release_evidence(
        package_dir=package_dir,
        evidence_dir=output,
        project_root=PROJECT_ROOT,
    )

    checksum = package_dir / f"{archive.name}.sha256"
    assert checksum.exists()
    assert checksum.read_text(encoding="utf-8").endswith(f"  {archive.name}\n")
    assert result["release_status"] == "blocked"
    assert result["pyqt_distribution_decision"] == "unresolved"

    sbom = json.loads((package_dir / "sbom.json").read_text(encoding="utf-8"))
    assert sbom["schema_version"] == 1
    assert sbom["metadata"]["artifact_files"] == [archive.name]
    assert "uv_lock_sha256" in sbom["metadata"]
    assert any(component["name"].lower() == "pyqt6" for component in sbom["components"])

    notices = (package_dir / "third-party-licenses.txt").read_text(encoding="utf-8")
    assert "Third-party license notices for Data Viewer" in notices
    assert "PyQt6" in notices

    review = json.loads((package_dir / "release-security-review.json").read_text(encoding="utf-8"))
    assert review["release_status"] == "blocked"
    assert review["findings"][0]["owner"] == "project-owner"
    assert not review["leak_scan"]["findings"]

    serialized_outputs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            package_dir / "sbom.json",
            package_dir / "third-party-licenses.txt",
            package_dir / "release-security-review.json",
        ]
    )
    assert str(tmp_path) not in serialized_outputs


def test_release_evidence_detects_path_and_secret_leaks() -> None:
    """Evidence validation fails closed for common local-path and credential leaks."""

    evidence = _load_release_evidence_module()

    findings = evidence.detect_sensitive_text(
        "artifact=C:\\Users\\Alvin\\Desktop\\HDF5-Viewer\nToken: gho_123456789abcdef\n"
    )

    kinds = {finding["kind"] for finding in findings}
    assert "absolute_windows_user_path" in kinds
    assert "github_token" in kinds


def test_release_evidence_scans_uploaded_manifest_for_path_leaks(tmp_path: Path) -> None:
    """Uploaded package attachments must fail closed if the manifest leaks local paths."""

    evidence = _load_release_evidence_module()
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    archive = package_dir / "DataViewer-0.1.0-windows-x86_64.zip"
    archive.write_bytes(b"data-viewer-archive")
    (package_dir / "pyinstaller-manifest.json").write_text(
        json.dumps(
            {
                "app_name": "DataViewer",
                "version": "0.1.0",
                "platform": "windows-x86_64",
                "artifact": archive.name,
                "bundle_dir": "C:\\Users\\Alvin\\Desktop\\HDF5-Viewer\\dist\\DataViewer",
                "executable": "C:\\Users\\Alvin\\Desktop\\HDF5-Viewer\\dist\\DataViewer\\DataViewer.exe",
            }
        ),
        encoding="utf-8",
    )

    result = evidence.generate_release_evidence(
        package_dir=package_dir,
        evidence_dir=tmp_path / "release-evidence",
        project_root=PROJECT_ROOT,
    )

    assert result["release_status"] == "blocked"
    assert result["leak_scan"]["status"] == "failed"
    assert {
        "file": "pyinstaller-manifest.json",
        "kind": "absolute_windows_user_path",
        "status": "detected",
    } in result["leak_scan"]["findings"]


def test_ci_generates_release_evidence_before_uploading_packages() -> None:
    """Package uploads must include SBOM, notices, checksums, and security review evidence."""

    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release_workflow = (PROJECT_ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )

    assert "Generate release evidence" in workflow
    assert "generate_release_evidence.py" in workflow
    assert "release-security-review.json" in workflow
    assert "third-party-licenses.txt" in workflow
    assert "sbom.json" in workflow
    assert "*.sha256" in workflow
    assert "PyQt licensing decision" in release_workflow
