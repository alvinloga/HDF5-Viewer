"""Prepare a Data Viewer manual release-acceptance evidence packet.

The generated packet is a prefilled checklist plus machine-readable summary for
DV-1101/DV-1102. It verifies package-level evidence that can be checked
automatically, but intentionally leaves functional and visual rows as
``pending-manual`` so CI evidence cannot masquerade as human sign-off.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform as platform_module
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FUNCTIONAL_ROWS = (
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
)


@dataclass(frozen=True)
class AcceptanceMetadata:
    """GitHub artifact and candidate metadata for a platform packet."""

    task_id: str
    platform_name: str
    candidate_commit: str
    run_id: str
    job_id: str
    artifact_name: str
    artifact_id: str
    artifact_digest: str
    reviewer: str
    version_output: str


def prepare_acceptance_packet(
    *,
    artifact_dir: Path,
    output_dir: Path,
    metadata: AcceptanceMetadata,
) -> dict[str, Any]:
    """Validate package evidence and write a prefilled manual checklist."""

    artifact_dir = artifact_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    archive = _find_package_archive(artifact_dir)
    archive_sha256 = _sha256_file(archive)
    checksum_status = _verify_archive_checksum(archive, archive_sha256)
    manifest = _read_json(artifact_dir / "pyinstaller-manifest.json")
    sbom = _read_json(artifact_dir / "sbom.json")
    security_review = _read_json(artifact_dir / "release-security-review.json")
    license_notices = artifact_dir / "third-party-licenses.txt"
    if not license_notices.exists():
        raise FileNotFoundError(license_notices)

    blockers = _release_blockers(security_review)
    preflight = {
        "package_artifact_present": archive.exists(),
        "artifact_digest_recorded": metadata.artifact_digest.startswith("sha256:"),
        "archive_sha256_verified": checksum_status["verified"],
        "manifest_present": bool(manifest),
        "sbom_present": bool(sbom),
        "third_party_licenses_present": license_notices.exists(),
        "release_security_review_ready": not blockers,
        "packaged_version_output_recorded": bool(metadata.version_output.strip()),
    }
    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_id": metadata.task_id,
        "platform": metadata.platform_name,
        "environment": _environment_record(),
        "candidate_commit": metadata.candidate_commit,
        "github_actions_run": metadata.run_id,
        "job_id": metadata.job_id,
        "artifact": {
            "name": metadata.artifact_name,
            "id": metadata.artifact_id,
            "github_digest": metadata.artifact_digest,
            "archive_name": archive.name,
            "archive_sha256": archive_sha256,
            "checksum_file": checksum_status["checksum_file"],
        },
        "manifest": manifest,
        "release_security_review": {
            "release_status": security_review.get("release_status"),
            "leak_scan_status": (security_review.get("leak_scan") or {}).get("status"),
            "findings": security_review.get("findings", []),
        },
        "preflight": preflight,
        "manual_status": "pending-manual",
        "manual_rows": {row: "pending-manual" for row in FUNCTIONAL_ROWS},
        "blockers": blockers,
    }

    checklist_name = f"{metadata.task_id}-checklist.md"
    (output_dir / checklist_name).write_text(
        _render_checklist(metadata, summary),
        encoding="utf-8",
    )
    (output_dir / "acceptance-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _find_package_archive(artifact_dir: Path) -> Path:
    archives = sorted(
        path
        for path in artifact_dir.iterdir()
        if path.is_file()
        and path.name.startswith("DataViewer-")
        and (path.suffix == ".zip" or path.name.endswith(".tar.gz"))
    )
    if len(archives) != 1:
        raise FileNotFoundError(
            f"Expected exactly one DataViewer package archive in {artifact_dir}, found {archives}"
        )
    return archives[0]


def _verify_archive_checksum(archive: Path, archive_sha256: str) -> dict[str, Any]:
    checksum_path = archive.with_name(f"{archive.name}.sha256")
    if not checksum_path.exists():
        raise FileNotFoundError(checksum_path)
    first_line = checksum_path.read_text(encoding="utf-8").splitlines()[0]
    recorded_hash, _, recorded_name = first_line.partition("  ")
    return {
        "checksum_file": checksum_path.name,
        "recorded_hash": recorded_hash,
        "recorded_name": recorded_name,
        "verified": recorded_hash == archive_sha256 and recorded_name == archive.name,
    }


def _release_blockers(security_review: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if security_review.get("release_status") != "ready":
        blockers.append(
            {
                "id": "release_status",
                "summary": "release-security-review.json does not report ready status",
            }
        )
    leak_scan = security_review.get("leak_scan") or {}
    if leak_scan.get("status") != "passed":
        blockers.append(
            {
                "id": "leak_scan",
                "summary": "release evidence leak scan did not pass",
                "findings": leak_scan.get("findings", []),
            }
        )
    for finding in security_review.get("findings", []):
        blockers.append(finding)
    return blockers


def _render_checklist(metadata: AcceptanceMetadata, summary: dict[str, Any]) -> str:
    preflight = summary["preflight"]
    artifact = summary["artifact"]
    env = summary["environment"]

    def checkbox(value: bool) -> str:
        return "x" if value else " "

    functional_rows = "\n".join(
        f"| {row} | pending-manual |  | Requires human execution and evidence. |"
        for row in FUNCTIONAL_ROWS
    )
    blockers = summary["blockers"]
    blocker_rows = (
        "\n".join(
            f"| {blocker.get('id', 'unknown')} | release-blocker | yes | release-owner |  | {blocker.get('summary', blocker)} |"
            for blocker in blockers
        )
        if blockers
        else "| None recorded by automated preflight |  | no |  |  | Manual acceptance still pending |"
    )

    return f"""# Data Viewer v1 Platform Acceptance Checklist

- Task: {metadata.task_id}
- Platform: {metadata.platform_name}
- OS version/build: {env['system']} {env['release']} ({env['version']})
- Display server / scaling mechanism: pending-manual
- CPU architecture: {env['machine']}
- Reviewer: {metadata.reviewer}
- Date/time/timezone: {summary['generated_at']}
- Candidate commit: {metadata.candidate_commit}
- GitHub Actions run: {metadata.run_id}
- Job ID: {metadata.job_id}
- Package artifact name: {metadata.artifact_name}
- Package artifact ID: {metadata.artifact_id}
- GitHub artifact digest: {metadata.artifact_digest}
- Archive SHA-256: {artifact['archive_sha256']}
- `Data Viewer --version` output: {metadata.version_output}
- Evidence directory or URL: pending-manual

## Preflight

- [{checkbox(preflight['package_artifact_present'])}] Package artifact downloaded from the recorded run
- [{checkbox(preflight['artifact_digest_recorded'])}] GitHub artifact digest recorded
- [{checkbox(preflight['archive_sha256_verified'])}] Archive SHA-256 verified against package checksum file
- [{checkbox(preflight['manifest_present'])}] `pyinstaller-manifest.json` present
- [{checkbox(preflight['sbom_present'])}] SBOM present
- [{checkbox(preflight['third_party_licenses_present'])}] Third-party licenses present
- [{checkbox(preflight['release_security_review_ready'])}] `release-security-review.json` reports no blocking findings
- [{checkbox(preflight['packaged_version_output_recorded'])}] Packaged executable version output recorded

## Functional matrix

Record `pass`, `fail`, `blocked`, or `not applicable with reason` only after manual execution.

| ID | Status | Evidence path or URL | Notes / issue |
|---|---|---|---|
{functional_rows}

## Visual/accessibility/localization matrix

Record one row per screenshot set. Each row must link the screenshot directory and any failure issue.

| Scaling | Window size | Theme | State | Status | Screenshot path or URL | Notes / issue |
|---|---|---|---|---|---|---|
| pending-manual | pending-manual | pending-manual | pending-manual | pending-manual |  |  |

## Platform differences

| Difference | Reason | Accepted by | Issue / evidence |
|---|---|---|---|
| pending-manual |  |  |  |

## Blockers and limitations

| Item | Severity | Integrity/security impact? | Owner | Issue | Release decision |
|---|---|---:|---|---|---|
{blocker_rows}

## Sign-off

I confirm this checklist was executed against the recorded packaged artifact and that no unresolved integrity or security blocker remains.

- Reviewer: {metadata.reviewer}
- Signature: pending-manual
- Date: pending-manual
"""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _environment_record() -> dict[str, str]:
    return {
        "system": platform_module.system(),
        "release": platform_module.release(),
        "version": platform_module.version(),
        "machine": platform_module.machine(),
        "python": platform_module.python_version(),
    }


def _task_id_for_platform(platform_name: str) -> str:
    normalized = platform_name.casefold()
    if normalized == "windows":
        return "DV-1101"
    if normalized in {"linux", "ubuntu"}:
        return "DV-1102"
    raise ValueError(f"Unsupported acceptance platform: {platform_name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--platform", choices=["Windows", "Ubuntu", "Linux"], required=True)
    parser.add_argument("--candidate-commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--artifact-digest", required=True)
    parser.add_argument("--reviewer", default="pending-manual")
    parser.add_argument("--version-output", default="pending-manual")
    args = parser.parse_args(argv)

    metadata = AcceptanceMetadata(
        task_id=_task_id_for_platform(args.platform),
        platform_name=args.platform,
        candidate_commit=args.candidate_commit,
        run_id=args.run_id,
        job_id=args.job_id,
        artifact_name=args.artifact_name,
        artifact_id=args.artifact_id,
        artifact_digest=args.artifact_digest,
        reviewer=args.reviewer,
        version_output=args.version_output,
    )
    summary = prepare_acceptance_packet(
        artifact_dir=args.artifact_dir,
        output_dir=args.output_dir,
        metadata=metadata,
    )
    print(json.dumps({"output_dir": str(args.output_dir), "blockers": summary["blockers"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
