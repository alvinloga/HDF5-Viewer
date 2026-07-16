"""Hydrate a CI-generated release-acceptance packet from GitHub artifact JSON.

The GitHub Actions packet is generated before package artifact IDs and digests
exist. This tool consumes a saved `gh api .../artifacts` response, selects the
matching package artifact for the packet's run/platform, and fills only the
upload metadata fields. It does not complete manual DV-1101/DV-1102 rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.update_release_acceptance_artifact_metadata import (
    update_acceptance_artifact_metadata,
)


PLATFORM_TASKS = {
    "windows": ("Windows", "DV-1101"),
    "ubuntu": ("Ubuntu", "DV-1102"),
    "linux": ("Ubuntu", "DV-1102"),
}


def hydrate_release_acceptance_packet(
    packet_dir: Path,
    *,
    artifacts_json: Path,
    platform_name: str,
    run_id: str,
    run_attempt: str | None = None,
) -> dict[str, str]:
    """Fill package upload metadata in a downloaded acceptance packet.

    Args:
        packet_dir: Directory containing `acceptance-summary.json` and the
            platform checklist downloaded from the lightweight acceptance
            artifact.
        artifacts_json: JSON file saved from GitHub Actions artifacts API.
        platform_name: `Windows`, `Ubuntu`, or `Linux`.
        run_id: Expected GitHub Actions run ID.
        run_attempt: Optional run attempt suffix to disambiguate artifact names.

    Returns:
        Machine-readable update summary.

    Raises:
        ValueError: If packet/run/platform identity does not match or if the
            package artifact cannot be selected exactly.
    """

    canonical_platform, task_id = _platform_and_task(platform_name)
    packet_dir = packet_dir.resolve()
    summary = _read_packet_summary(packet_dir)
    if str(summary.get("github_actions_run")) != str(run_id):
        raise ValueError(
            "packet acceptance-summary.json github_actions_run "
            f"{summary.get('github_actions_run')!r} does not match {run_id!r}"
        )
    if summary.get("task_id") != task_id:
        raise ValueError(f"packet task_id {summary.get('task_id')!r} does not match {task_id!r}")
    if summary.get("platform") not in {canonical_platform, platform_name}:
        raise ValueError(
            f"packet platform {summary.get('platform')!r} does not match {canonical_platform!r}"
        )

    artifact = _select_package_artifact(
        _read_artifacts(artifacts_json),
        platform_name=canonical_platform,
        run_id=str(run_id),
        run_attempt=run_attempt,
    )
    digest = str(artifact["digest"])
    if not digest.startswith("sha256:"):
        raise ValueError(f"selected package artifact digest must start with sha256:, got {digest!r}")

    updated = update_acceptance_artifact_metadata(
        packet_dir,
        task_id=task_id,
        artifact_name=str(artifact["name"]),
        artifact_id=str(artifact["id"]),
        artifact_digest=digest,
    )
    updated["artifact_name"] = str(artifact["name"])
    return updated


def _platform_and_task(platform_name: str) -> tuple[str, str]:
    try:
        return PLATFORM_TASKS[platform_name.casefold()]
    except KeyError as exc:
        raise ValueError("platform_name must be Windows, Ubuntu, or Linux") from exc


def _read_packet_summary(packet_dir: Path) -> dict[str, Any]:
    summary_path = packet_dir / "acceptance-summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(summary_path)
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("acceptance-summary.json must contain an object")
    return data


def _read_artifacts(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    artifacts = data.get("artifacts") if isinstance(data, dict) else None
    if not isinstance(artifacts, list):
        raise ValueError("artifacts JSON must contain an artifacts array")
    normalized: list[dict[str, Any]] = []
    for artifact in artifacts:
        if isinstance(artifact, dict):
            normalized.append(artifact)
    return normalized


def _select_package_artifact(
    artifacts: list[dict[str, Any]],
    *,
    platform_name: str,
    run_id: str,
    run_attempt: str | None,
) -> dict[str, Any]:
    suffix = f"-{run_attempt}" if run_attempt else "-"
    prefix = f"data-viewer-package-{platform_name}-{run_id}{suffix}"
    matches = [
        artifact
        for artifact in artifacts
        if str(artifact.get("name", "")).startswith(prefix)
    ]
    if len(matches) != 1:
        names = ", ".join(str(artifact.get("name")) for artifact in matches) or "<none>"
        raise ValueError(f"expected exactly one package artifact matching {prefix!r}, found {names}")
    selected = matches[0]
    for field in ("id", "name", "digest"):
        if field not in selected or selected[field] in {None, ""}:
            raise ValueError(f"selected package artifact is missing {field}")
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet_dir", type=Path)
    parser.add_argument("--artifacts-json", type=Path, required=True)
    parser.add_argument("--platform", choices=["Windows", "Ubuntu", "Linux"], required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt")
    args = parser.parse_args(argv)

    result = hydrate_release_acceptance_packet(
        args.packet_dir,
        artifacts_json=args.artifacts_json,
        platform_name=args.platform,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
