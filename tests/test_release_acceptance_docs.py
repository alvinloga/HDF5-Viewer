"""Release acceptance documentation contracts."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = PROJECT_ROOT / "docs" / "RELEASE_ACCEPTANCE.md"
RELEASE = PROJECT_ROOT / "RELEASE.md"
DOC_INDEX = PROJECT_ROOT / "docs" / "INDEX.md"


def test_release_acceptance_runbook_exists_and_names_p11_tasks() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    for task_id in ("DV-1101", "DV-1102", "DV-1103", "DV-1104"):
        assert task_id in text

    assert "Windows x86-64" in text
    assert "supported Linux x86-64" in text
    assert "packaged artifacts" in text
    assert "Source-tree checks may support diagnosis" in text
    assert "prepare_release_acceptance_packet.py" in text


def test_release_acceptance_runbook_covers_required_functional_rows() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    required_rows = (
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

    for row_id in required_rows:
        assert f"| {row_id} " in text

    assert "read-only" in text
    assert "safe edit" in text
    assert "gzip wrapper" in text
    assert "release-security-review.json" in text


def test_release_acceptance_runbook_covers_visual_matrix_and_signoff() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    for required in (
        "100%",
        "150%",
        "200%",
        "1024x768 minimum",
        "1440x900 typical",
        "2560x1440 large",
        "light, dark",
        "English and Simplified Chinese",
        "visible focus indicator",
        "Reviewer:",
        "Signature:",
        "no unresolved integrity or security blocker remains",
    ):
        assert required in text


def test_release_acceptance_requires_native_visual_evidence() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    for required in (
        "native interactive display stack",
        "Offscreen/headless screenshots may support CI smoke diagnostics",
        "do not satisfy the manual visual, accessibility, localization, or DPI evidence",
        "default UI font observed by the packaged application",
        "display server (`x11`/`xcb` or Wayland)",
    ):
        assert required in text


def test_release_gate_status_matches_p11_reality() -> None:
    release_text = RELEASE.read_text(encoding="utf-8")
    index_text = DOC_INDEX.read_text(encoding="utf-8")

    assert "DV-1009" in release_text
    assert "automated release-candidate checkpoint" in release_text
    assert "not publicly released yet" in release_text
    for task_id in ("DV-1101", "DV-1102", "DV-1103", "DV-1104"):
        assert task_id in release_text

    assert "specified but not implemented" not in release_text
    assert "legacy release history only" not in index_text
    assert "current Data Viewer v1 release gate" in index_text
