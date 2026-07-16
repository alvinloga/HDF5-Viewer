"""Render a human reviewer handoff for a Data Viewer acceptance packet.

This helper turns the conservative validator output into a concise Markdown
todo sheet for DV-1101/DV-1102 reviewers. It does not change the checklist,
does not mark rows complete, and does not replace manual execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.validate_release_acceptance_packet import (
    ValidationIssue,
    validate_acceptance_packet,
)


def render_acceptance_handoff(packet_dir: Path, *, task_id: str | None = None) -> str:
    """Return Markdown describing what a human reviewer still needs to do."""

    packet_dir = packet_dir.resolve()
    summary = _read_summary(packet_dir / "acceptance-summary.json")
    expected_task = task_id or str(summary.get("task_id") or "")
    issues = validate_acceptance_packet(packet_dir, task_id=expected_task or None)
    raw_artifact = summary.get("artifact")
    artifact: dict[str, Any] = raw_artifact if isinstance(raw_artifact, dict) else {}
    issue_counts = Counter(issue.code for issue in issues)
    missing_fields = _messages_after_prefix(issues, "checklist-required-field", "Missing or pending checklist field ")
    functional_rows = _messages_before_suffix(issues, "functional-not-accepted", " status is not acceptable")
    visual_issue_count = issue_counts["visual-not-accepted"] + issue_counts["visual-row-missing"]

    lines = [
        f"# Data Viewer {expected_task or 'release acceptance'} reviewer handoff",
        "",
        "This handoff summarizes the remaining human review work for a generated acceptance packet.",
        f"This handoff does not complete {expected_task or 'the acceptance task'} and must not be used as a signature.",
        "",
        "## Packet identity",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Packet directory | `{packet_dir}` |",
        f"| Task | `{summary.get('task_id', '')}` |",
        f"| Platform | `{summary.get('platform', '')}` |",
        f"| Candidate commit | `{summary.get('candidate_commit', '')}` |",
        f"| GitHub Actions run | `{summary.get('github_actions_run', '')}` |",
        f"| Job ID | `{summary.get('job_id', '')}` |",
        f"| Package artifact name | `{artifact.get('name', '')}` |",
        f"| Package artifact ID | `{artifact.get('id', '')}` |",
        f"| GitHub artifact digest | `{artifact.get('github_digest', '')}` |",
        f"| Archive SHA-256 | `{artifact.get('archive_sha256', '')}` |",
        "",
        "## Validator status",
        "",
        f"- Current validator issue count: `{len(issues)}`.",
    ]
    if issue_counts:
        for code, count in sorted(issue_counts.items()):
            lines.append(f"- `{code}`: {count}")
    else:
        lines.append("- No validator issues remain.")

    lines.extend(["", "## Missing reviewer fields", ""])
    if missing_fields:
        lines.extend(f"- {field}" for field in missing_fields)
    else:
        lines.append("- None.")

    lines.extend(["", "## Functional rows still requiring human review", ""])
    if functional_rows:
        lines.extend(f"- {row}" for row in functional_rows)
    else:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Visual/accessibility/localization rows still requiring screenshots",
            "",
            f"- Validator currently reports `{visual_issue_count}` visual/accessibility/localization issue(s).",
            "- Capture screenshots on the native interactive display stack named in the checklist.",
            "",
            "## Final reviewer command",
            "",
            "Run this after the checklist is completed and signed:",
            "",
            "```bash",
            f"python tools/validate_release_acceptance_packet.py {packet_dir} --task-id {expected_task}",
            "```",
            "",
            "The packet is not accepted until that command passes with zero issues.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_acceptance_handoff(
    packet_dir: Path,
    *,
    task_id: str | None = None,
    output: Path | None = None,
) -> Path:
    """Write reviewer handoff Markdown and return the output path."""

    packet_dir = packet_dir.resolve()
    output_path = output.resolve() if output else packet_dir / "REVIEWER_HANDOFF.md"
    output_path.write_text(render_acceptance_handoff(packet_dir, task_id=task_id), encoding="utf-8")
    return output_path


def _read_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("acceptance-summary.json must contain an object")
    return data


def _messages_after_prefix(
    issues: list[ValidationIssue],
    code: str,
    prefix: str,
) -> list[str]:
    values: list[str] = []
    for issue in issues:
        if issue.code == code and issue.message.startswith(prefix):
            values.append(issue.message.removeprefix(prefix))
    return values


def _messages_before_suffix(
    issues: list[ValidationIssue],
    code: str,
    suffix: str,
) -> list[str]:
    values: list[str] = []
    for issue in issues:
        if issue.code == code and suffix in issue.message:
            values.append(issue.message.split(suffix, 1)[0])
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet_dir", type=Path)
    parser.add_argument("--task-id", choices=["DV-1101", "DV-1102"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    output_path = write_acceptance_handoff(
        args.packet_dir,
        task_id=args.task_id,
        output=args.output,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
