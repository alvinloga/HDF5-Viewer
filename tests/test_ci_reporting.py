"""Contracts for durable, dual-platform CI evidence and release gating."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_manifest_writer():
    script_path = ROOT / ".github" / "scripts" / "write_quality_manifest.py"
    spec = importlib.util.spec_from_file_location("write_quality_manifest", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_quality_manifest_records_platform_lock_and_safe_ci_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_SHA", "0123456789abcdef")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "3")
    manifest_writer = _load_manifest_writer()

    manifest_path = manifest_writer.write_manifest(tmp_path, platform_name="Windows")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["platform"] == "Windows"
    assert manifest["git_sha"] == "0123456789abcdef"
    assert manifest["run_id"] == "42"
    assert manifest["run_attempt"] == "3"
    assert manifest["uv_lock_sha256"] == hashlib.sha256(
        (ROOT / "uv.lock").read_text(encoding="utf-8")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .encode("utf-8")
    ).hexdigest()


def test_lock_hash_normalizes_checkout_line_endings(tmp_path) -> None:
    manifest_writer = _load_manifest_writer()
    lf_lock = tmp_path / "lf.lock"
    crlf_lock = tmp_path / "crlf.lock"
    lf_lock.write_bytes(b"version = 1\nrequires-python = '>=3.12'\n")
    crlf_lock.write_bytes(b"version = 1\r\nrequires-python = '>=3.12'\r\n")

    assert manifest_writer._lock_file_sha256(
        lf_lock
    ) == manifest_writer._lock_file_sha256(crlf_lock)


def test_lock_file_checkout_uses_lf_for_cross_platform_ci_evidence() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()

    assert "uv.lock text eol=lf" in attributes


def test_workflows_upload_quality_evidence_and_release_requires_quality() -> None:
    quality_workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    release_workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_call:" in quality_workflow
    assert "--junitxml=ci-reports/${{ matrix.name }}/pytest.xml" in quality_workflow
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in quality_workflow
    assert "if: ${{ always() }}" in quality_workflow
    assert "hashFiles('uv.lock')" in quality_workflow
    assert "uses: ./.github/workflows/ci.yml" in release_workflow
    assert "needs: quality" in release_workflow


def test_deliberate_quality_gate_failure_for_dv0005_release_block() -> None:
    assert False, "DV-0005 intentional quality-gate failure verification"
