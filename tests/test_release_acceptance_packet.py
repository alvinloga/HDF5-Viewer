"""Release acceptance packet generation contracts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.prepare_release_acceptance_packet import AcceptanceMetadata, prepare_acceptance_packet
from tools.update_release_acceptance_artifact_metadata import (
    update_acceptance_artifact_metadata,
)
from tools.validate_release_acceptance_packet import validate_acceptance_packet


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


def test_validate_release_acceptance_packet_rejects_generated_preflight_packet(
    tmp_path: Path,
) -> None:
    packet_dir = _prepare_ready_packet(tmp_path, task_id="DV-1101", platform_name="Windows")

    issues = validate_acceptance_packet(packet_dir, task_id="DV-1101")

    issue_codes = {issue.code for issue in issues}
    assert "pending-marker" in issue_codes
    assert "functional-not-accepted" in issue_codes
    assert "visual-not-accepted" in issue_codes
    assert "checklist-required-field" in issue_codes


def test_validate_release_acceptance_packet_cli_runs_as_documented(tmp_path: Path) -> None:
    packet_dir = _prepare_ready_packet(tmp_path, task_id="DV-1101", platform_name="Windows")

    completed = subprocess.run(
        [
            sys.executable,
            "tools/validate_release_acceptance_packet.py",
            str(packet_dir),
            "--task-id",
            "DV-1101",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "ModuleNotFoundError" not in completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["issue_count"] > 0
    assert {issue["code"] for issue in payload["issues"]} >= {
        "pending-marker",
        "functional-not-accepted",
    }


def test_validate_release_acceptance_packet_accepts_completed_packet(tmp_path: Path) -> None:
    packet_dir = _prepare_ready_packet(tmp_path, task_id="DV-1101", platform_name="Windows")
    checklist_path = packet_dir / "DV-1101-checklist.md"
    checklist = checklist_path.read_text(encoding="utf-8")
    checklist = checklist.replace(
        "| pending-manual | pending-manual | pending-manual | pending-manual | pending-manual |  |  |",
        "| 150% | 1440x900 typical | light | table | pass | screenshots/table-light.png |  |",
    )
    checklist = checklist.replace(
        "| pending-manual |  |  |  |",
        "| None |  |  |  |",
    )
    replacements = {
        "pending-manual": "evidence/windows",
        "- Display server / scaling mechanism: evidence/windows": "- Display server / scaling mechanism: Windows 11 native display, 150% scaling",
        "- Evidence directory or URL: evidence/windows": "- Evidence directory or URL: evidence/windows",
        "- Signature: evidence/windows": "- Signature: Alice Reviewer",
        "- Date: evidence/windows": "- Date: 2026-07-16",
    }
    for old, new in replacements.items():
        checklist = checklist.replace(old, new)
    for row_id in (
        "FMT-HDF5",
        "FMT-NPY",
        "FMT-NPZ",
        "FMT-CSV",
        "FMT-TSV",
        "FMT-TXT",
        "FMT-MAT",
        "FMT-NIFTI",
        "FMT-XLSX",
        "FMT-JSON",
        "FMT-YAML",
        "EDIT",
        "EXPORT",
        "PLUGIN",
        "COMPARE",
        "WORKSPACE",
        "TASKS",
        "SECURITY",
        "PACKAGE",
    ):
        checklist = checklist.replace(
            f"| {row_id} | evidence/windows |  | Requires human execution and evidence. |",
            f"| {row_id} | pass | evidence/windows/{row_id}.md | reviewed |",
        )
    checklist_path.write_text(checklist, encoding="utf-8")

    issues = validate_acceptance_packet(packet_dir, task_id="DV-1101")

    assert issues == []


def test_ci_generates_preupload_acceptance_packet_before_package_upload() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "Prepare release acceptance packet" in workflow
    assert "--artifact-id \"pending-after-upload\"" in workflow
    assert "--artifact-digest \"pending-after-upload\"" in workflow
    assert "artifacts/${{ matrix.name }}/package/acceptance/**" in workflow
    assert "Upload release acceptance packet artifact" in workflow
    assert "data-viewer-acceptance-${{ matrix.name }}-${{ github.run_id }}-${{ github.run_attempt }}" in workflow


def test_update_release_acceptance_artifact_metadata_fills_preupload_fields_only(
    tmp_path: Path,
) -> None:
    packet_dir = _prepare_ready_packet(
        tmp_path,
        task_id="DV-1101",
        platform_name="Windows",
        artifact_id="pending-after-upload",
        artifact_digest="pending-after-upload",
    )

    result = update_acceptance_artifact_metadata(
        packet_dir,
        task_id="DV-1101",
        artifact_id="8377858744",
        artifact_digest="sha256:73c0aa7b0dbf14ce2d38ab9b0a28def8475bc65f706a2b4ad9f18d2e848b1163",
        artifact_name="data-viewer-package-Windows-123-1",
    )

    assert result["task_id"] == "DV-1101"
    assert result["artifact_id"] == "8377858744"
    assert result["artifact_digest"] == "sha256:73c0aa7b0dbf14ce2d38ab9b0a28def8475bc65f706a2b4ad9f18d2e848b1163"

    summary = json.loads((packet_dir / "acceptance-summary.json").read_text(encoding="utf-8"))
    assert summary["artifact"]["id"] == "8377858744"
    assert summary["artifact"]["github_digest"] == result["artifact_digest"]
    assert summary["preflight"]["artifact_digest_recorded"] is True
    assert summary["manual_status"] == "pending-manual"
    assert summary["manual_rows"]["FMT-HDF5"] == "pending-manual"

    checklist = (packet_dir / "DV-1101-checklist.md").read_text(encoding="utf-8")
    assert "- Package artifact ID: 8377858744" in checklist
    assert f"- GitHub artifact digest: {result['artifact_digest']}" in checklist
    assert "| FMT-HDF5 | pending-manual |" in checklist
    assert "Signature: pending-manual" in checklist
    assert "pending-after-upload" not in checklist

    issue_codes = {issue.code for issue in validate_acceptance_packet(packet_dir, task_id="DV-1101")}
    assert "summary-required-field" not in issue_codes
    assert "functional-not-accepted" in issue_codes
    assert "checklist-required-field" in issue_codes


def test_update_release_acceptance_artifact_metadata_rejects_mismatches(tmp_path: Path) -> None:
    packet_dir = _prepare_ready_packet(
        tmp_path,
        task_id="DV-1102",
        platform_name="Ubuntu",
        artifact_id="pending-after-upload",
        artifact_digest="pending-after-upload",
    )

    try:
        update_acceptance_artifact_metadata(
            packet_dir,
            task_id="DV-1101",
            artifact_id="8377825993",
            artifact_digest="sha256:07a8229d2fbb5e93bef7f544ff4ba57ce6554391032897af9d3cdeb1b06f620f",
        )
    except ValueError as exc:
        assert "task_id" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("task mismatch should fail")

    try:
        update_acceptance_artifact_metadata(
            packet_dir,
            task_id="DV-1102",
            artifact_id="8377825993",
            artifact_digest="07a8229d2fbb5e93bef7f544ff4ba57ce6554391032897af9d3cdeb1b06f620f",
        )
    except ValueError as exc:
        assert "sha256:" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("digest without sha256 prefix should fail")

    try:
        update_acceptance_artifact_metadata(
            packet_dir,
            task_id="DV-1102",
            artifact_id="8377825993",
            artifact_digest="sha256:07a8229d2fbb5e93bef7f544ff4ba57ce6554391032897af9d3cdeb1b06f620f",
            artifact_name="wrong-artifact",
        )
    except ValueError as exc:
        assert "artifact name" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("artifact name mismatch should fail")


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _prepare_ready_packet(
    tmp_path: Path,
    *,
    task_id: str,
    platform_name: str,
    artifact_id: str = "789",
    artifact_digest: str = "sha256:artifactdigest",
) -> Path:
    artifact_dir = tmp_path / f"artifact-{task_id}"
    artifact_dir.mkdir()
    archive = artifact_dir / "DataViewer-0.1.0-windows-x86_64.zip"
    archive.write_bytes(b"data-viewer-package")
    archive_hash = _sha256(archive)
    (artifact_dir / f"{archive.name}.sha256").write_text(
        f"{archive_hash}  {archive.name}\n",
        encoding="utf-8",
    )
    (artifact_dir / "pyinstaller-manifest.json").write_text(
        json.dumps({"app_name": "DataViewer", "version": "0.1.0"}),
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
    packet_dir = tmp_path / f"packet-{task_id}"
    prepare_acceptance_packet(
        artifact_dir=artifact_dir,
        output_dir=packet_dir,
        metadata=AcceptanceMetadata(
            task_id=task_id,
            platform_name=platform_name,
            candidate_commit="abc123",
            run_id="123",
            job_id="456",
            artifact_name=f"data-viewer-package-{platform_name}-123-1",
            artifact_id=artifact_id,
            artifact_digest=artifact_digest,
            reviewer="Alice Reviewer",
            version_output="Data Viewer 0.1.0",
        ),
    )
    return packet_dir
