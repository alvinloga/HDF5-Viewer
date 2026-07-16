"""Validate a completed Data Viewer release-acceptance evidence packet.

This validator is intentionally conservative. It cannot decide whether a human
review was thorough, but it can fail closed on evidence packets that still look
like generated preflight packets: pending rows, missing signatures, unresolved
blockers, missing artifact identity, or visual rows without screenshot links.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.prepare_release_acceptance_packet import FUNCTIONAL_ROWS


PENDING_MARKERS = ("pending-manual", "pending-after-upload")
PASS_STATUS = "pass"
NA_PREFIX = "not applicable"


@dataclass(frozen=True)
class ValidationIssue:
    """A release-acceptance packet validation issue."""

    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def validate_acceptance_packet(packet_dir: Path, *, task_id: str | None = None) -> list[ValidationIssue]:
    """Return validation issues for a completed platform acceptance packet."""

    packet_dir = packet_dir.resolve()
    issues: list[ValidationIssue] = []
    summary_path = packet_dir / "acceptance-summary.json"
    summary = _read_summary(summary_path, issues)

    expected_task = task_id or str(summary.get("task_id") or "")
    checklist_path = _find_checklist(packet_dir, expected_task, issues)
    checklist_text = checklist_path.read_text(encoding="utf-8") if checklist_path else ""

    if summary:
        issues.extend(_validate_summary(summary, expected_task))
    if checklist_text:
        issues.extend(_validate_checklist(checklist_text, expected_task))

    return issues


def _read_summary(path: Path, issues: list[ValidationIssue]) -> dict[str, Any]:
    if not path.exists():
        issues.append(ValidationIssue("missing-summary", f"Missing {path.name}"))
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(ValidationIssue("invalid-summary-json", f"Invalid summary JSON: {exc}"))
        return {}
    if not isinstance(data, dict):
        issues.append(ValidationIssue("invalid-summary-shape", "acceptance-summary.json must contain an object"))
        return {}
    return data


def _find_checklist(
    packet_dir: Path,
    expected_task: str,
    issues: list[ValidationIssue],
) -> Path | None:
    if expected_task:
        expected = packet_dir / f"{expected_task}-checklist.md"
        if expected.exists():
            return expected

    checklists = sorted(packet_dir.glob("DV-110*-checklist.md"))
    if len(checklists) == 1:
        return checklists[0]
    if not checklists:
        issues.append(ValidationIssue("missing-checklist", "Missing DV-1101/DV-1102 checklist"))
    else:
        issues.append(
            ValidationIssue(
                "ambiguous-checklist",
                f"Expected one checklist, found: {', '.join(path.name for path in checklists)}",
            )
        )
    return None


def _validate_summary(summary: dict[str, Any], expected_task: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if summary.get("schema_version") != 1:
        issues.append(ValidationIssue("summary-schema", "summary schema_version must be 1"))
    if expected_task and summary.get("task_id") != expected_task:
        issues.append(
            ValidationIssue(
                "task-mismatch",
                f"summary task_id {summary.get('task_id')!r} does not match {expected_task!r}",
            )
        )

    for path in (
        ("candidate_commit",),
        ("github_actions_run",),
        ("job_id",),
        ("artifact", "name"),
        ("artifact", "id"),
        ("artifact", "github_digest"),
        ("artifact", "archive_sha256"),
    ):
        value = _nested_get(summary, path)
        if _is_blank_or_pending(value):
            issues.append(ValidationIssue("summary-required-field", f"Missing or pending summary field {'.'.join(path)}"))

    artifact_digest = _nested_get(summary, ("artifact", "github_digest"))
    if isinstance(artifact_digest, str) and not artifact_digest.startswith("sha256:"):
        issues.append(ValidationIssue("artifact-digest", "GitHub artifact digest must start with sha256:"))

    preflight = summary.get("preflight")
    if not isinstance(preflight, dict):
        issues.append(ValidationIssue("summary-preflight", "summary preflight must be an object"))
    else:
        for key, value in sorted(preflight.items()):
            if value is not True:
                issues.append(ValidationIssue("preflight-not-passed", f"Preflight {key} is not true"))

    blockers = summary.get("blockers")
    if blockers:
        issues.append(ValidationIssue("summary-blockers", "summary contains release blockers"))

    return issues


def _validate_checklist(text: str, expected_task: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    lowered = text.casefold()
    for marker in PENDING_MARKERS:
        if marker in lowered:
            issues.append(ValidationIssue("pending-marker", f"Checklist still contains {marker}"))

    if expected_task and f"- Task: {expected_task}" not in text:
        issues.append(ValidationIssue("checklist-task", f"Checklist does not identify task {expected_task}"))

    for label in (
        "Platform",
        "OS version/build",
        "Display server / scaling mechanism",
        "Reviewer",
        "Package artifact ID",
        "GitHub artifact digest",
        "Archive SHA-256",
        "`Data Viewer --version` output",
        "Evidence directory or URL",
        "Signature",
        "Date",
    ):
        value = _metadata_value(text, label)
        if _is_blank_or_pending(value):
            issues.append(ValidationIssue("checklist-required-field", f"Missing or pending checklist field {label}"))

    issues.extend(_validate_functional_rows(text))
    issues.extend(_validate_visual_rows(text))
    return issues


def _validate_functional_rows(text: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    rows = _table_rows_between(text, "## Functional matrix", "## Visual/accessibility/localization matrix")
    by_id = {cells[0]: cells for cells in rows if cells}
    for row_id in FUNCTIONAL_ROWS:
        cells = by_id.get(row_id)
        if cells is None:
            issues.append(ValidationIssue("functional-row-missing", f"Missing functional row {row_id}"))
            continue
        status = cells[1].strip().casefold() if len(cells) > 1 else ""
        evidence = cells[2].strip() if len(cells) > 2 else ""
        notes = cells[3].strip() if len(cells) > 3 else ""
        if status == PASS_STATUS:
            if not evidence:
                issues.append(ValidationIssue("functional-evidence-missing", f"{row_id} pass row lacks evidence path or URL"))
        elif status.startswith(NA_PREFIX):
            if not notes:
                issues.append(ValidationIssue("functional-na-reason-missing", f"{row_id} not-applicable row lacks reason"))
        else:
            issues.append(ValidationIssue("functional-not-accepted", f"{row_id} status is not acceptable: {status or '<blank>'}"))
    return issues


def _validate_visual_rows(text: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    rows = _table_rows_between(text, "## Visual/accessibility/localization matrix", "## Platform differences")
    if not rows:
        return [ValidationIssue("visual-row-missing", "No visual/accessibility/localization matrix rows recorded")]

    for index, cells in enumerate(rows, start=1):
        if len(cells) < 7:
            issues.append(ValidationIssue("visual-row-shape", f"Visual row {index} has too few columns"))
            continue
        status = cells[4].strip().casefold()
        screenshot = cells[5].strip()
        notes = cells[6].strip()
        if status == PASS_STATUS:
            if not screenshot:
                issues.append(ValidationIssue("visual-screenshot-missing", f"Visual row {index} pass lacks screenshot path or URL"))
        elif status.startswith(NA_PREFIX):
            if not notes:
                issues.append(ValidationIssue("visual-na-reason-missing", f"Visual row {index} not-applicable row lacks reason"))
        else:
            issues.append(ValidationIssue("visual-not-accepted", f"Visual row {index} status is not acceptable: {status or '<blank>'}"))
    return issues


def _table_rows_between(text: str, start_heading: str, end_heading: str) -> list[list[str]]:
    start = text.find(start_heading)
    if start < 0:
        return []
    end = text.find(end_heading, start + len(start_heading))
    section = text[start:] if end < 0 else text[start:end]
    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or cells[0] in {"ID", "Scaling"} or set(cells[0]) <= {"-", ":"}:
            continue
        rows.append(cells)
    return rows


def _metadata_value(text: str, label: str) -> str | None:
    prefix = f"- {label}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return None


def _nested_get(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _is_blank_or_pending(value: object) -> bool:
    if not isinstance(value, str):
        return value is None
    stripped = value.strip()
    return not stripped or stripped.casefold() in PENDING_MARKERS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet_dir", type=Path)
    parser.add_argument("--task-id", choices=["DV-1101", "DV-1102"])
    parser.add_argument("--json", action="store_true", help="Print machine-readable issue JSON")
    args = parser.parse_args(argv)

    issues = validate_acceptance_packet(args.packet_dir, task_id=args.task_id)
    payload = {"packet_dir": str(args.packet_dir), "issue_count": len(issues), "issues": [issue.as_dict() for issue in issues]}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif issues:
        for issue in issues:
            print(f"{issue.code}: {issue.message}")
    else:
        print(f"{args.packet_dir} passed release-acceptance packet validation")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
