"""Fill GitHub package artifact metadata in a release-acceptance packet.

CI prepares DV-1101/DV-1102 acceptance packets before GitHub assigns final
artifact IDs and digests. This tool updates only those upload metadata fields.
It intentionally does not mark manual rows, visual rows, or sign-off fields as
complete.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PENDING_AFTER_UPLOAD = "pending-after-upload"
TASK_CHOICES = ("DV-1101", "DV-1102")


def update_acceptance_artifact_metadata(
    packet_dir: Path,
    *,
    task_id: str,
    artifact_id: str,
    artifact_digest: str,
    artifact_name: str | None = None,
) -> dict[str, str]:
    """Update package artifact ID and GitHub digest in an acceptance packet.

    Args:
        packet_dir: Evidence packet directory containing acceptance-summary.json
            and a DV-1101/DV-1102 checklist.
        task_id: Expected acceptance task ID.
        artifact_id: Final GitHub package artifact ID.
        artifact_digest: Final GitHub package artifact digest with sha256: prefix.
        artifact_name: Optional expected package artifact name.

    Returns:
        Machine-readable update summary.

    Raises:
        FileNotFoundError: If the packet summary or checklist is missing.
        ValueError: If the packet does not match the requested task/artifact or
            does not contain the exact pre-upload metadata fields.
    """

    if task_id not in TASK_CHOICES:
        raise ValueError(f"task_id must be one of {', '.join(TASK_CHOICES)}")
    artifact_id = artifact_id.strip()
    artifact_digest = artifact_digest.strip()
    if not artifact_id:
        raise ValueError("artifact_id must not be blank")
    if not artifact_digest.startswith("sha256:"):
        raise ValueError("artifact_digest must start with sha256:")

    packet_dir = packet_dir.resolve()
    summary_path = packet_dir / "acceptance-summary.json"
    checklist_path = packet_dir / f"{task_id}-checklist.md"
    summary = _read_summary(summary_path)
    _validate_summary_identity(summary, task_id=task_id, artifact_name=artifact_name)

    checklist = checklist_path.read_text(encoding="utf-8")
    _validate_checklist_identity(checklist, task_id=task_id, artifact_name=artifact_name)

    artifact = summary.get("artifact")
    if not isinstance(artifact, dict):
        raise ValueError("acceptance-summary.json artifact must be an object")
    if artifact.get("id") != PENDING_AFTER_UPLOAD:
        raise ValueError("summary artifact.id is not pending-after-upload")
    if artifact.get("github_digest") != PENDING_AFTER_UPLOAD:
        raise ValueError("summary artifact.github_digest is not pending-after-upload")

    updated_checklist = _replace_one(
        checklist,
        f"- Package artifact ID: {PENDING_AFTER_UPLOAD}",
        f"- Package artifact ID: {artifact_id}",
    )
    updated_checklist = _replace_one(
        updated_checklist,
        f"- GitHub artifact digest: {PENDING_AFTER_UPLOAD}",
        f"- GitHub artifact digest: {artifact_digest}",
    )

    artifact["id"] = artifact_id
    artifact["github_digest"] = artifact_digest
    preflight = summary.get("preflight")
    if isinstance(preflight, dict):
        preflight["artifact_digest_recorded"] = True
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checklist_path.write_text(updated_checklist, encoding="utf-8")

    return {
        "packet_dir": str(packet_dir),
        "task_id": task_id,
        "artifact_id": artifact_id,
        "artifact_digest": artifact_digest,
    }


def _read_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("acceptance-summary.json must contain an object")
    return data


def _validate_summary_identity(
    summary: dict[str, Any],
    *,
    task_id: str,
    artifact_name: str | None,
) -> None:
    if summary.get("task_id") != task_id:
        raise ValueError(f"summary task_id {summary.get('task_id')!r} does not match {task_id!r}")
    artifact = summary.get("artifact")
    if not isinstance(artifact, dict):
        raise ValueError("acceptance-summary.json artifact must be an object")
    if artifact_name is not None and artifact.get("name") != artifact_name:
        raise ValueError(f"summary artifact name {artifact.get('name')!r} does not match {artifact_name!r}")


def _validate_checklist_identity(
    checklist: str,
    *,
    task_id: str,
    artifact_name: str | None,
) -> None:
    if f"- Task: {task_id}" not in checklist:
        raise ValueError(f"checklist does not identify task_id {task_id}")
    if artifact_name is not None and f"- Package artifact name: {artifact_name}" not in checklist:
        raise ValueError(f"checklist artifact name does not match {artifact_name!r}")


def _replace_one(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"expected exactly one checklist field {old!r}, found {count}")
    return text.replace(old, new)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet_dir", type=Path)
    parser.add_argument("--task-id", choices=TASK_CHOICES, required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--artifact-digest", required=True)
    parser.add_argument("--artifact-name")
    args = parser.parse_args(argv)

    result = update_acceptance_artifact_metadata(
        args.packet_dir,
        task_id=args.task_id,
        artifact_id=args.artifact_id,
        artifact_digest=args.artifact_digest,
        artifact_name=args.artifact_name,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
