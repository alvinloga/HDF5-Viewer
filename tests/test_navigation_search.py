"""DV-0904 recent, favorites, history, and global-search contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_viewer.app.navigation import (
    NavigationHistory,
    NavigationService,
    ResourceFavorite,
    SearchIndexEntry,
    SearchQuery,
    SearchQueryError,
)
from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.tasks import CancellationToken
from data_viewer.workspace import WorkspaceManifest


def test_recent_and_pinned_are_app_config_not_workspace_state(tmp_path: Path) -> None:
    existing = tmp_path / "data.csv"
    existing.write_text("a,b\n1,2\n", encoding="utf-8")
    missing = tmp_path / "missing.csv"
    workspace = _workspace()
    service = NavigationService()

    service.add_recent(existing)
    service.add_recent(missing)
    service.set_pinned(existing, True)
    app_config = service.to_app_config()

    assert workspace.preferences == {}
    assert workspace.layout == {}
    assert app_config["recent_files"][0]["path"] == str(existing.resolve())
    assert app_config["recent_files"][0]["pinned"] is True
    assert service.recent_files[1].missing is True
    assert service.recent_remediations(missing) == ("locate", "remove")


def test_favorites_are_resource_identity_not_display_labels() -> None:
    service = NavigationService()

    service.add_favorite(
        ResourceFavorite(
            source_id="src-1",
            resource_path="/group/data",
            resource_domain="array",
            label="Pretty label",
        )
    )
    service.add_favorite(
        ResourceFavorite(
            source_id="src-1",
            resource_path="/group/data",
            resource_domain="array",
            label="Renamed label",
        )
    )

    assert len(service.favorites) == 1
    assert service.favorites[0].identity == ("src-1", "/group/data")
    assert service.favorites[0].label == "Renamed label"


def test_navigation_history_is_semantic_and_active_split_aware() -> None:
    history = NavigationHistory()
    history = history.push(source_id="src-1", resource_path="/a", view_id="view-a", split_id="left")
    history = history.push(source_id="src-1", resource_path="/b", view_id="view-b", split_id="right")

    previous = history.back()
    assert previous.current is not None
    assert previous.current.resource_path == "/a"
    assert previous.current.split_id == "left"

    forward = previous.forward()
    assert forward.current is not None
    assert forward.current.resource_path == "/b"
    assert forward.current.split_id == "right"


def test_global_search_filters_path_name_domain_dtype_shape_and_regex() -> None:
    service = NavigationService()
    entries = (
        _entry("/signals/run1", "voltage", "array", "float64", (10, 2)),
        _entry("/signals/run2", "current", "array", "float32", (10, 2)),
        _entry("/metadata", "notes", "text", "str", ()),
    )

    grouped = service.search(
        entries,
        SearchQuery(
            text="signals",
            name="volt.*",
            domains=("array",),
            dtype="float",
            shape=(10, 2),
            regex=True,
        ),
        cancellation=CancellationToken(),
    )

    assert tuple(grouped) == ("array",)
    assert [item.name for item in grouped["array"]] == ["voltage"]


def test_global_search_reports_regex_errors_and_honors_cancellation() -> None:
    service = NavigationService()
    entries = (_entry("/signals/run1", "voltage", "array", "float64", (10, 2)),)

    with pytest.raises(SearchQueryError) as exc_info:
        service.search(entries, SearchQuery(name="["), cancellation=CancellationToken())
    assert exc_info.value.reason == "invalid_regex"

    cancelled = CancellationToken()
    cancelled.cancel()
    with pytest.raises(DataViewerError) as cancelled_info:
        service.search(entries, SearchQuery(text="signals"), cancellation=cancelled)
    assert cancelled_info.value.code is ErrorCode.TASK_CANCELLED


def _entry(
    path: str,
    name: str,
    domain: str,
    dtype: str,
    shape: tuple[int, ...],
) -> SearchIndexEntry:
    return SearchIndexEntry(
        source_id="src",
        resource_path=path,
        name=name,
        resource_domain=domain,
        dtype=dtype,
        shape=shape,
    )


def _workspace() -> WorkspaceManifest:
    return WorkspaceManifest(
        workspace_id="workspace-1",
        title="workspace",
        created_at="2026-07-15T00:00:00Z",
        updated_at="2026-07-15T00:00:00Z",
    )
