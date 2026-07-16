"""Release acceptance packet generation contracts."""

from __future__ import annotations

import json
from pathlib import Path

from tools.prepare_release_acceptance_packet import AcceptanceMetadata, prepare_acceptance_packet


def test_prepare_release_acceptance_packet_prefills_preflight_without_manual_signoff(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    archive = artifact_dir / "DataViewer-0.1.0-windows-x86_64.zip"
    archive.write_bytes(b"data-viewer-package")
    archive_hash = _sha256(archive)
    (artifact_dir / f"{archive.name}.sha256").write_text(
        f"{archive_hash}  {archive.name}\n",
        encoding="utf-8",
    )
    (artifact_dir / "pyinstaller-manifest.json").write_text(
        json.dumps(
            {
                "app_name": "DataViewer",
                "version": "0.1.0",
                "platform": "windows-x86_64",
                "artifact": archive.name,
                "bundle_dir": "DataViewer",
                "executable": "DataViewer/DataViewer.exe",
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "sbom.json").write_text('{"schema_version": 1}\n', encoding="utf-8")
    (artifact_dir / "third-party-licenses.txt").write_text("notices\n", encoding="utf-8")
    (artifact_dir / "release-security-review.json").write_text(
        json.dumps(
            {
                "release_status": "ready",
                "leak_scan": {"status": "passed", "findings": []},
                "findings": [],
            }
        ),
        encoding="utf-8",
    )

    summary = prepare_acceptance_packet(
        artifact_dir=artifact_dir,
        output_dir=tmp_path / "packet",
        metadata=AcceptanceMetadata(
            task_id="DV-1101",
            platform_name="Windows",
            candidate_commit="abc123",
            run_id="123",
            job_id="456",
            artifact_name="data-viewer-package-Windows-123-1",
            artifact_id="789",
            artifact_digest="sha256:artifactdigest",
            reviewer="pending-manual",
            version_output="Data Viewer 0.1.0",
        ),
    )

    assert summary["preflight"]["archive_sha256_verified"] is True
    assert summary["preflight"]["release_security_review_ready"] is True
    assert summary["manual_status"] == "pending-manual"
    assert summary["manual_rows"]["FMT-HDF5"] == "pending-manual"
    assert summary["blockers"] == []

    checklist = (tmp_path / "packet" / "DV-1101-checklist.md").read_text(encoding="utf-8")
    assert "- [x] Archive SHA-256 verified against package checksum file" in checklist
    assert "| FMT-HDF5 | pending-manual |" in checklist
    assert "Signature: pending-manual" in checklist


def test_prepare_release_acceptance_packet_reports_security_blockers(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    archive = artifact_dir / "DataViewer-0.1.0-linux-x86_64.tar.gz"
    archive.write_bytes(b"data-viewer-package")
    (artifact_dir / f"{archive.name}.sha256").write_text(
        f"{_sha256(archive)}  {archive.name}\n",
        encoding="utf-8",
    )
    (artifact_dir / "pyinstaller-manifest.json").write_text("{}\n", encoding="utf-8")
    (artifact_dir / "sbom.json").write_text("{}\n", encoding="utf-8")
    (artifact_dir / "third-party-licenses.txt").write_text("notices\n", encoding="utf-8")
    (artifact_dir / "release-security-review.json").write_text(
        json.dumps(
            {
                "release_status": "blocked",
                "leak_scan": {"status": "failed", "findings": [{"kind": "path"}]},
                "findings": [{"id": "finding-1", "summary": "bad evidence"}],
            }
        ),
        encoding="utf-8",
    )

    summary = prepare_acceptance_packet(
        artifact_dir=artifact_dir,
        output_dir=tmp_path / "packet",
        metadata=AcceptanceMetadata(
            task_id="DV-1102",
            platform_name="Ubuntu",
            candidate_commit="abc123",
            run_id="123",
            job_id="456",
            artifact_name="data-viewer-package-Ubuntu-123-1",
            artifact_id="789",
            artifact_digest="sha256:artifactdigest",
            reviewer="pending-manual",
            version_output="Data Viewer 0.1.0",
        ),
    )

    assert summary["preflight"]["release_security_review_ready"] is False
    assert {blocker["id"] for blocker in summary["blockers"]} == {
        "release_status",
        "leak_scan",
        "finding-1",
    }


def test_ci_generates_preupload_acceptance_packet_before_package_upload() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "Prepare release acceptance packet" in workflow
    assert "--artifact-id \"pending-after-upload\"" in workflow
    assert "--artifact-digest \"pending-after-upload\"" in workflow
    assert "artifacts/${{ matrix.name }}/package/acceptance/**" in workflow
    assert "Upload release acceptance packet artifact" in workflow
    assert "data-viewer-acceptance-${{ matrix.name }}-${{ github.run_id }}-${{ github.run_attempt }}" in workflow


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()
