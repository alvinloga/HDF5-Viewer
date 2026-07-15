"""Generate release evidence for Data Viewer package artifacts.

The script intentionally uses only the standard library so release evidence does
not depend on another unchecked release-time tool. It records checksums, a
minimal dependency SBOM, third-party license notices, and a fail-closed security
review summary for the package upload.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = 1
PYQT_FINDING_ID = "DV-1007-PYQT-LICENSE"


def generate_release_evidence(
    *,
    package_dir: Path,
    evidence_dir: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Generate release evidence files and return the security review summary."""

    package_dir = package_dir.resolve()
    evidence_dir = evidence_dir.resolve()
    project_root = project_root.resolve()
    package_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    artifacts = _artifact_files(package_dir)
    if not artifacts:
        raise FileNotFoundError(f"No DataViewer package artifacts found in {package_dir}")

    checksum_files = [_write_checksum(path) for path in artifacts]
    sbom_path = _write_json(
        package_dir / "sbom.json",
        build_sbom(artifacts=artifacts, project_root=project_root),
    )
    notices_path = _write_text(
        package_dir / "third-party-licenses.txt",
        build_license_notices(project_root=project_root),
    )

    leak_findings = _scan_files_for_leaks([sbom_path, notices_path, *checksum_files])
    findings = []
    pyqt_decision = pyqt_distribution_decision(project_root)
    if pyqt_decision != "satisfied":
        findings.append(
            {
                "id": PYQT_FINDING_ID,
                "severity": "release-blocker",
                "category": "license",
                "summary": "PyQt binary distribution license decision is not resolved.",
                "owner": "project-owner",
                "expiry": "before-public-binary-release",
                "status": "documented",
            }
        )
    if leak_findings:
        findings.append(
            {
                "id": "DV-1007-EVIDENCE-LEAK",
                "severity": "release-blocker",
                "category": "evidence-redaction",
                "summary": "Release evidence contains sensitive path or credential patterns.",
                "owner": "release-owner",
                "expiry": "before-public-binary-release",
                "status": "must-fix",
            }
        )

    review = {
        "schema_version": SCHEMA_VERSION,
        "release_status": "blocked" if findings else "ready",
        "pyqt_distribution_decision": pyqt_decision,
        "artifact_files": [path.name for path in artifacts],
        "checksum_files": [path.name for path in checksum_files],
        "dependency_consistency": {
            "tool": "uv lock --check + uv sync --locked --all-extras + direct import smoke",
            "status": "enforced-by-ci",
        },
        "leak_scan": {
            "status": "failed" if leak_findings else "passed",
            "findings": leak_findings,
        },
        "findings": findings,
    }
    review_path = _write_json(package_dir / "release-security-review.json", review)
    _mirror_evidence(
        [sbom_path, notices_path, review_path, *checksum_files],
        evidence_dir=evidence_dir,
        package_dir=package_dir,
    )
    return review


def build_sbom(*, artifacts: list[Path], project_root: Path) -> dict[str, Any]:
    """Build a minimal JSON SBOM for the locked Python environment."""

    return {
        "schema_version": SCHEMA_VERSION,
        "format": "data-viewer-release-sbom",
        "metadata": {
            "application": "Data Viewer",
            "artifact_files": [path.name for path in artifacts],
            "uv_lock_sha256": _sha256_file(project_root / "uv.lock"),
        },
        "components": [_component_from_distribution(dist) for dist in _sorted_distributions()],
    }


def build_license_notices(*, project_root: Path) -> str:
    """Build human-readable third-party license notices from installed metadata."""

    lines = [
        "Third-party license notices for Data Viewer",
        "",
        "Generated from the locked Python environment used by CI.",
        f"uv.lock SHA-256: {_sha256_file(project_root / 'uv.lock')}",
        "",
    ]
    for dist in _sorted_distributions():
        component = _component_from_distribution(dist)
        lines.extend(
            [
                f"## {component['name']} {component['version']}",
                f"License: {component['license']}",
            ]
        )
        classifiers = component["license_classifiers"]
        if classifiers:
            lines.append("License classifiers:")
            lines.extend(f"- {classifier}" for classifier in classifiers)
        for license_file in component["license_files"]:
            lines.append(f"Notice file: {license_file['path']}")
            if license_file["text"]:
                lines.append(license_file["text"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def detect_sensitive_text(text: str) -> list[dict[str, str]]:
    """Return fail-closed findings for sensitive paths or credentials in text."""

    checks = [
        (
            "absolute_windows_user_path",
            re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\r\n\t ]+\\"),
        ),
        (
            "absolute_posix_user_path",
            re.compile(r"\B/(?:home|Users)/[^/\r\n\t ]+/"),
        ),
        (
            "github_token",
            re.compile(r"\bgh[opsu]_[A-Za-z0-9_]{10,}\b"),
        ),
        (
            "generic_secret_assignment",
            re.compile(r"(?i)\b(?:api[_-]?key|password|secret|token)\s*[:=]\s*[^*\s][^\r\n]+"),
        ),
    ]
    findings: list[dict[str, str]] = []
    for kind, pattern in checks:
        if pattern.search(text):
            findings.append({"kind": kind, "status": "detected"})
    return findings


def pyqt_distribution_decision(project_root: Path) -> str:
    """Return the documented PyQt distribution decision state."""

    dependencies = (project_root / "docs" / "DEPENDENCIES.md").read_text(encoding="utf-8")
    if "currently **unresolved**" in dependencies or "public binary packaging is blocked" in dependencies:
        return "unresolved"
    return "satisfied"


def _artifact_files(package_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in package_dir.iterdir()
        if path.is_file()
        and path.name.startswith("DataViewer-")
        and (path.suffix == ".zip" or path.name.endswith(".tar.gz"))
    )


def _write_checksum(path: Path) -> Path:
    checksum_path = path.with_name(f"{path.name}.sha256")
    checksum_path.write_text(f"{_sha256_file(path)}  {path.name}\n", encoding="utf-8")
    return checksum_path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sorted_distributions() -> list[importlib.metadata.Distribution]:
    distributions = list(importlib.metadata.distributions())
    return sorted(
        distributions,
        key=lambda dist: (dist.metadata.get("Name") or "").casefold(),
    )


def _component_from_distribution(dist: importlib.metadata.Distribution) -> dict[str, Any]:
    metadata = dist.metadata
    classifiers = [
        value
        for value in metadata.get_all("Classifier", [])
        if value.startswith("License ::")
    ]
    return {
        "type": "python-distribution",
        "name": metadata.get("Name") or "UNKNOWN",
        "version": metadata.get("Version") or "UNKNOWN",
        "summary": metadata.get("Summary") or "",
        "license": _short_license(metadata.get("License") or metadata.get("License-Expression")),
        "license_classifiers": classifiers,
        "license_files": _license_files(dist),
    }


def _short_license(raw: str | None) -> str:
    if not raw:
        return "UNKNOWN"
    compact = " ".join(raw.split())
    return compact[:500] + ("..." if len(compact) > 500 else "")


def _license_files(dist: importlib.metadata.Distribution) -> list[dict[str, str]]:
    files = dist.files or []
    notices: list[dict[str, str]] = []
    for package_path in files:
        path_text = str(package_path).replace("\\", "/")
        name = Path(path_text).name.casefold()
        if not any(token in name for token in ("license", "licence", "notice", "copying")):
            continue
        try:
            text = dist.locate_file(package_path).read_text()
        except (OSError, UnicodeError):
            text = ""
        notices.append(
            {
                "path": path_text,
                "text": " ".join(text.split())[:2000],
            }
        )
        if len(notices) >= 5:
            break
    return notices


def _scan_files_for_leaks(paths: list[Path]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for finding in detect_sensitive_text(text):
            findings.append({"file": path.name, **finding})
    return findings


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _mirror_evidence(paths: list[Path], *, evidence_dir: Path, package_dir: Path) -> None:
    for path in paths:
        target = evidence_dir / path.relative_to(package_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.resolve() != target.resolve():
            shutil.copy2(path, target)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--project-root", default=PROJECT_ROOT, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    review = generate_release_evidence(
        package_dir=args.package_dir,
        evidence_dir=args.evidence_dir,
        project_root=args.project_root,
    )
    print(json.dumps(review, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
