"""Contract tests for the target Data Viewer package entrypoint."""

from __future__ import annotations

import sys
from unittest.mock import Mock

import data_viewer
from data_viewer import __version__
import data_viewer.__main__ as entrypoint


def test_package_exports_its_canonical_development_version() -> None:
    """The target package exposes the single version used by build metadata."""
    assert data_viewer.__version__ == __version__


def test_workspace_manifest_uses_canonical_runtime_version() -> None:
    """Workspace app metadata reads the package version instead of a hard-coded release."""
    from data_viewer.workspace import WorkspaceManifest

    manifest = WorkspaceManifest(
        workspace_id="workspace",
        title="workspace",
        created_at="2026-07-15T00:00:00Z",
        updated_at="2026-07-15T00:00:00Z",
    )

    assert manifest.app["name"] == "Data Viewer"
    assert manifest.app["version"] == __version__


def test_target_runtime_surfaces_do_not_use_old_product_name() -> None:
    """The target package may mention the old name only for explicit legacy/migration text."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "data_viewer"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        # Historical/legacy product spellings are scanned explicitly below.
        for old_name in ("HDF5 Viewer", "HDF5Viewer", "hdf5viewer"):
            if old_name not in text:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if old_name in line and "legacy" not in line.lower():
                    offenders.append(f"{path.relative_to(root)}:{line_number}:{line.strip()}")

    assert offenders == []


def test_repository_old_product_name_references_are_explicitly_historical() -> None:
    """Repository-wide old-name references must be migration/history/legacy context."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    ignored_parts = {
        ".git",
        ".hypothesis",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
        "venv",
    }
    historical_markers = (
        "legacy",
        "historical",
        "history",
        "migration",
        "migrate",
        "rejected",
        "旧版",
        "历史",
        "迁移",
        "旧名",
    )
    offenders: list[str] = []
    for path in root.rglob("*"):
        if any(part in ignored_parts for part in path.parts):
            continue
        if path.suffix.lower() in {".pyc", ".png", ".svg", ".zip"}:
            continue
        if path.is_dir():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lines = text.splitlines()
        for line_number, line in enumerate(lines, start=1):
            if not any(old_name in line for old_name in ("HDF5 Viewer", "HDF5Viewer", "hdf5viewer")):
                continue
            context = " ".join(lines[max(0, line_number - 4) : line_number + 3]).lower()
            if not any(marker in context for marker in historical_markers):
                offenders.append(f"{path.relative_to(root)}:{line_number}:{line.strip()}")

    assert offenders == []


def _run_with_argv(
    argv: list[str],
    *,
    run_data_viewer,
) -> int:
    """Run parser+dispatch with injectable handlers for testability."""

    old_argv = list(sys.argv)
    sys.argv = argv
    try:
        return entrypoint.main_with_handlers(
            run_data_viewer=run_data_viewer,
        )
    finally:
        sys.argv = old_argv


def test_package_cli_version() -> None:
    """`--version` exits without launching any bootstrap."""
    called_bootstrap = False

    def fake_bootstrap(*, path: str | None = None, app_args=None) -> int:
        nonlocal called_bootstrap
        called_bootstrap = True
        return 0

    exit_code = _run_with_argv(
        ["data-viewer", "--version"],
        run_data_viewer=fake_bootstrap,
    )
    assert exit_code == 0
    assert not called_bootstrap


def test_cli_defaults_to_target_bootstrap() -> None:
    """The default CLI path starts the target bootstrap."""
    fake_bootstrap = Mock(return_value=123)
    exit_code = _run_with_argv(
        ["data-viewer", "file.h5"],
        run_data_viewer=fake_bootstrap,
    )
    assert exit_code == 123
    fake_bootstrap.assert_called_once_with(path="file.h5")


def test_cli_rejects_removed_legacy_fallback() -> None:
    """DV-1008 removes the broken legacy CLI fallback from the target entrypoint."""

    fake_bootstrap = Mock(return_value=0)
    old_argv = list(sys.argv)
    sys.argv = ["data-viewer", "--legacy", "legacy.h5"]
    try:
        try:
            entrypoint.main_with_handlers(run_data_viewer=fake_bootstrap)
        except SystemExit as exc:
            assert exc.code != 0
        else:  # pragma: no cover - documents the required failure path
            raise AssertionError("--legacy unexpectedly launched a bootstrap")
    finally:
        sys.argv = old_argv
    fake_bootstrap.assert_not_called()


def test_legacy_environment_flag_does_not_override_target_bootstrap(monkeypatch) -> None:
    """The old environment escape hatch is ignored after the target bootstrap becomes default."""

    monkeypatch.setenv("DATA_VIEWER_LEGACY", "1")
    fake_bootstrap = Mock(return_value=11)

    exit_code = _run_with_argv(
        ["data-viewer", "file.h5"],
        run_data_viewer=fake_bootstrap,
    )

    assert exit_code == 11
    fake_bootstrap.assert_called_once_with(path="file.h5")
