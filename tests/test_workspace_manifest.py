"""DV-0901 workspace manifest schema/model/persistence contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_viewer.persistence.transaction import TransactionStep
from data_viewer.workspace import (
    WORKSPACE_SCHEMA_VERSION,
    WorkspaceManifest,
    WorkspaceService,
    WorkspaceSource,
    WorkspaceValidationError,
    WorkspaceVersionError,
    WorkspaceView,
)


def _manifest() -> WorkspaceManifest:
    return WorkspaceManifest(
        workspace_id="018f73cf-d5aa-7bd0-8b80-1fd928f9c714",
        title="实验 comparison",
        created_at="2026-07-11T08:00:00Z",
        updated_at="2026-07-11T09:30:00Z",
        sources=(
            WorkspaceSource(
                source_id="src-01",
                display_name="run_04.h5",
                path="data/run_04.h5",
                path_kind="relative",
                format_id="hdf5",
                fingerprint={
                    "size": 8493210,
                    "mtime_ns": 1783756800000000000,
                    "prefix_sha256": "abc123",
                },
                open_options={"encoding": "utf-8"},
                status_hint="available",
            ),
        ),
        views=(
            WorkspaceView(
                view_id="view-01",
                source_id="src-01",
                resource_path="/results/field",
                resource_domain="array",
                view_type="table",
                selection={"kind": "all"},
                cursor=(0, 12, 20),
                scroll={"row": 0, "column": 0},
                display={"numeric_precision": 6, "value_mode": "raw"},
                split_group="split-left",
                pinned=False,
            ),
        ),
        layout={"active_view_id": "view-01"},
        preferences={"theme": "system"},
    )


def test_workspace_schema_file_is_packaged_and_validates_minimal_manifest() -> None:
    """The v1 JSON Schema is discoverable and accepts a minimal manifest."""

    service = WorkspaceService()
    minimal = WorkspaceManifest(
        workspace_id="018f73cf-d5aa-7bd0-8b80-1fd928f9c714",
        title="Minimal",
        created_at="2026-07-11T08:00:00Z",
        updated_at="2026-07-11T08:00:00Z",
    )

    data = service.loads(service.dumps(minimal))

    assert service.schema_path().name == "workspace-v1.schema.json"
    assert WORKSPACE_SCHEMA_VERSION == 1
    assert data.schema_version == 1
    assert data.sources == ()
    assert data.views == ()


def test_workspace_round_trip_is_deterministic_utf8_and_preserves_unknown_fields() -> None:
    """Unknown JSON-safe fields survive read/write and output is stable."""

    service = WorkspaceService()
    raw = json.loads(service.dumps(_manifest()))
    raw["future_top"] = {"kept": True}
    raw["sources"][0]["future_source"] = "preserved"

    loaded = service.loads(json.dumps(raw, ensure_ascii=False))
    first = service.dumps(loaded)
    second = service.dumps(loaded)
    reparsed = json.loads(first)

    assert first == second
    assert first.endswith("\n")
    assert "实验 comparison" in first
    assert reparsed["future_top"] == {"kept": True}
    assert reparsed["sources"][0]["future_source"] == "preserved"


def test_workspace_resolves_relative_and_absolute_source_paths(tmp_path: Path) -> None:
    """Relative paths resolve against the workspace directory without mutating the manifest."""

    service = WorkspaceService()
    workspace_path = tmp_path / "project" / "session.dvw"
    relative = WorkspaceSource(
        source_id="src-relative",
        display_name="run.csv",
        path="data/run.csv",
        path_kind="relative",
        format_id="csv",
        fingerprint={},
    )
    absolute_path = tmp_path / "external" / "run.csv"
    absolute = WorkspaceSource(
        source_id="src-absolute",
        display_name="external.csv",
        path=str(absolute_path),
        path_kind="absolute",
        format_id="csv",
        fingerprint={},
    )

    assert service.resolve_source_path(relative, workspace_path) == workspace_path.parent / "data" / "run.csv"
    assert service.resolve_source_path(absolute, workspace_path) == absolute_path
    assert relative.path == "data/run.csv"


def test_workspace_rejects_newer_versions_executable_content_and_budget_abuse() -> None:
    """Workspace loading fails closed for unsafe manifests before restore."""

    service = WorkspaceService(max_bytes=4096, max_depth=12)
    newer = json.loads(service.dumps(_manifest()))
    newer["schema_version"] = 2
    unsafe = json.loads(service.dumps(_manifest()))
    unsafe["extensions"] = {"python_object": "print('nope')"}

    with pytest.raises(WorkspaceVersionError):
        service.loads(json.dumps(newer))
    with pytest.raises(WorkspaceValidationError, match="forbidden workspace key"):
        service.loads(json.dumps(unsafe))
    with pytest.raises(WorkspaceValidationError, match="exceeds workspace byte budget"):
        WorkspaceService(max_bytes=512).loads(" " * 513)
    with pytest.raises(WorkspaceValidationError, match="exceeds workspace nesting budget"):
        service.loads('{"schema_version": 1, "app": {}, "workspace_id": "x", "title": "x", "created_at": "x", "updated_at": "x", "sources": [[[[[[[[[[[[[]]]]]]]]]]]]], "views": [], "comparisons": [], "plugin_results": [], "layout": {}, "preferences": {}, "extensions": {}}')


def test_workspace_save_is_atomic_and_does_not_modify_source_dirty_state(tmp_path: Path) -> None:
    """A failed workspace save leaves the previous .dvw manifest unchanged."""

    service = WorkspaceService()
    path = tmp_path / "session.dvw"
    old_text = service.dumps(_manifest())
    path.write_text(old_text, encoding="utf-8")
    updated = _manifest().with_updates(title="Updated title", source_dirty=False, workspace_dirty=True)

    with pytest.raises(Exception):
        service.save(
            path,
            updated,
            failure_injector=lambda step: (_ for _ in ()).throw(RuntimeError("boom"))
            if step is TransactionStep.WRITE
            else None,
        )

    assert path.read_text(encoding="utf-8") == old_text
    service.save(path, updated)
    loaded = service.load(path)
    assert loaded.title == "Updated title"
    assert loaded.source_dirty is False
    assert loaded.workspace_dirty is False
