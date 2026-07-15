"""Workspace restore, relocation, and degraded-mode contracts."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.tasks import CancellationToken
from data_viewer.workspace import WorkspaceManifest, WorkspaceSource, WorkspaceView
from data_viewer.workspace.restore import (
    PluginResultRestoreStatus,
    WorkspaceRestoreCoordinator,
    WorkspaceSourceRestoreStatus,
    WorkspaceViewPayloadStatus,
)


def test_restore_matrix_is_explicit_and_never_silently_relinks(tmp_path: Path) -> None:
    workspace_path = tmp_path / "study.dvw"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    relocation_root = tmp_path / "relocated"
    relocation_root.mkdir()

    available = _write(data_dir / "available.csv", "a,b\n1,2\n")
    changed = _write(data_dir / "changed.csv", "new-content\n")
    moved = _write(relocation_root / "moved.csv", "moved payload\n")
    ambiguous_one = _write(relocation_root / "nested-a" / "ambiguous.csv", "same payload\n")
    ambiguous_two = _write(relocation_root / "nested-b" / "ambiguous.csv", "same payload\n")

    manifest = _manifest(
        workspace_path,
        sources=(
            _source("available", available, workspace_path, _fingerprint(available)),
            _source("missing", data_dir / "missing.csv", workspace_path, {"size": 100}),
            _source("changed", changed, workspace_path, {"size": 100}),
            _source("moved", data_dir / "moved.csv", workspace_path, _fingerprint(moved)),
            _source(
                "ambiguous",
                data_dir / "ambiguous.csv",
                workspace_path,
                _fingerprint(ambiguous_one),
            ),
        ),
    )

    plan = WorkspaceRestoreCoordinator().plan_restore(
        manifest,
        workspace_path=workspace_path,
        replacement_roots=(relocation_root,),
    )

    assert plan.degraded
    assert plan.source("available").status is WorkspaceSourceRestoreStatus.AVAILABLE
    assert plan.source("missing").status is WorkspaceSourceRestoreStatus.MISSING
    assert plan.source("changed").status is WorkspaceSourceRestoreStatus.CHANGED
    assert plan.source("moved").status is WorkspaceSourceRestoreStatus.MOVED_CANDIDATE
    assert plan.source("moved").resolved_path == moved.resolve()
    assert plan.source("ambiguous").status is WorkspaceSourceRestoreStatus.AMBIGUOUS
    assert set(plan.source("ambiguous").candidates) == {
        ambiguous_one.resolve(),
        ambiguous_two.resolve(),
    }
    assert manifest.sources[3].path == "data/moved.csv"


def test_confirmed_relocations_update_only_explicit_sources(tmp_path: Path) -> None:
    workspace_path = tmp_path / "study.dvw"
    data_dir = tmp_path / "data"
    moved_root = tmp_path / "new-root"
    data_dir.mkdir()
    moved_root.mkdir()
    moved = _write(moved_root / "moved.csv", "moved payload\n")
    other = _write(moved_root / "other.csv", "other payload\n")
    manifest = _manifest(
        workspace_path,
        sources=(
            _source("moved", data_dir / "moved.csv", workspace_path, _fingerprint(moved)),
            _source("other", data_dir / "other.csv", workspace_path, _fingerprint(other)),
        ),
    )

    updated = WorkspaceRestoreCoordinator().apply_confirmed_relocations(
        manifest,
        workspace_path=workspace_path,
        confirmations={"moved": moved},
    )

    assert updated.workspace_dirty
    assert updated.sources[0].path == "new-root/moved.csv"
    assert updated.sources[0].path_kind == "relative"
    assert updated.sources[1].path == "data/other.csv"


def test_view_shells_and_stale_plugin_results_survive_partial_restore(tmp_path: Path) -> None:
    workspace_path = tmp_path / "study.dvw"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    available = _write(data_dir / "available.csv", "a,b\n1,2\n")
    manifest = _manifest(
        workspace_path,
        sources=(
            _source("available", available, workspace_path, _fingerprint(available)),
            _source("missing", data_dir / "missing.csv", workspace_path, {"size": 100}),
        ),
        views=(
            _view("available-view", "available"),
            _view("missing-view", "missing"),
        ),
        plugin_results=(
            {
                "result_id": "profile-current",
                "plugin_id": "dataviewer.dataset_profile",
                "plugin_version": "1.0.0",
                "inputs": [{"source_id": "available", "fingerprint": _fingerprint(available)}],
            },
            {
                "result_id": "profile-stale",
                "plugin_id": "dataviewer.dataset_profile",
                "plugin_version": "1.0.0",
                "inputs": [{"source_id": "missing", "fingerprint": {"size": 100}}],
            },
        ),
    )

    plan = WorkspaceRestoreCoordinator().plan_restore(manifest, workspace_path=workspace_path)

    assert plan.view_shell("available-view").payload_status is WorkspaceViewPayloadStatus.PENDING
    assert plan.view_shell("missing-view").payload_status is WorkspaceViewPayloadStatus.BLOCKED
    assert plan.plugin_result("profile-current").status is PluginResultRestoreStatus.CURRENT
    assert plan.plugin_result("profile-stale").status is PluginResultRestoreStatus.STALE


def test_async_restore_cancel_and_non_ascii_relative_paths(tmp_path: Path) -> None:
    workspace_path = tmp_path / "研究.dvw"
    source_path = _write(tmp_path / "数据" / "源.csv", "值\n1\n")
    manifest = _manifest(
        workspace_path,
        sources=(_source("non-ascii", source_path, workspace_path, _fingerprint(source_path)),),
    )

    async_plan = asyncio.run(
        WorkspaceRestoreCoordinator().plan_restore_async(
            manifest,
            workspace_path=workspace_path,
            cancellation=CancellationToken(),
        )
    )
    assert async_plan.source("non-ascii").status is WorkspaceSourceRestoreStatus.AVAILABLE

    cancelled = CancellationToken()
    cancelled.cancel()
    with pytest.raises(DataViewerError) as exc_info:
        asyncio.run(
            WorkspaceRestoreCoordinator().plan_restore_async(
                manifest,
                workspace_path=workspace_path,
                cancellation=cancelled,
            )
        )
    assert exc_info.value.code is ErrorCode.TASK_CANCELLED


def _manifest(
    workspace_path: Path,
    *,
    sources: tuple[WorkspaceSource, ...],
    views: tuple[WorkspaceView, ...] = (),
    plugin_results: tuple[dict[str, object], ...] = (),
) -> WorkspaceManifest:
    return WorkspaceManifest(
        workspace_id="workspace-1",
        title=workspace_path.stem,
        created_at="2026-07-15T00:00:00Z",
        updated_at="2026-07-15T00:00:00Z",
        sources=sources,
        views=views,
        plugin_results=plugin_results,  # type: ignore[arg-type]
    )


def _source(
    source_id: str,
    path: Path,
    workspace_path: Path,
    fingerprint: dict[str, object],
) -> WorkspaceSource:
    return WorkspaceSource(
        source_id=source_id,
        display_name=source_id,
        path=path.relative_to(workspace_path.parent).as_posix(),
        path_kind="relative",
        format_id="csv",
        fingerprint=fingerprint,  # type: ignore[arg-type]
    )


def _view(view_id: str, source_id: str) -> WorkspaceView:
    return WorkspaceView(
        view_id=view_id,
        source_id=source_id,
        resource_path="/",
        resource_domain="table",
        view_type="table",
        selection={"kind": "all"},
    )


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _fingerprint(path: Path) -> dict[str, object]:
    return {"size": path.stat().st_size}
