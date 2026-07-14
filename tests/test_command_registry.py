"""Command registry and ActiveContext contract tests for DV-0602."""

from __future__ import annotations

from data_viewer.app.active_context import ActiveContext, ActiveContextSnapshot
from data_viewer.app.commands import CommandId, default_command_registry
from data_viewer.domain import ResourceId


def test_default_command_registry_covers_ui_shortcut_baseline() -> None:
    """Shortcut text comes from one command registry, not duplicated labels."""

    registry = default_command_registry()

    assert registry.shortcut_for(CommandId.OPEN_FILE) == "Ctrl+O"
    assert registry.shortcut_for(CommandId.OPEN_WORKSPACE) == "Ctrl+Shift+O"
    assert registry.shortcut_for(CommandId.SAVE_DOCUMENT) == "Ctrl+S"
    assert registry.shortcut_for(CommandId.SAVE_AS) == "Ctrl+Shift+S"
    assert registry.shortcut_for(CommandId.EXPORT) == "Ctrl+E"
    assert registry.shortcut_for(CommandId.CLOSE_VIEW) == "Ctrl+W"
    assert registry.shortcut_for(CommandId.COMMAND_PALETTE) == "Ctrl+Shift+P"
    assert registry.shortcut_for(CommandId.FIND_CURRENT) == "Ctrl+F"
    assert registry.shortcut_for(CommandId.GLOBAL_SEARCH) == "Ctrl+Shift+F"
    assert registry.shortcut_for(CommandId.SPLIT_VIEW) == "Ctrl+\\"
    assert registry.shortcut_for(CommandId.TOGGLE_BOTTOM_PANEL) == "Ctrl+J"
    assert registry.shortcut_for(CommandId.UNDO) == "Ctrl+Z"
    assert registry.shortcut_for(CommandId.REDO) == "Ctrl+Shift+Z"

    labels = [definition.label for definition in registry.definitions()]
    actions = [definition.action for definition in registry.definitions()]
    assert len(labels) == len(set(labels))
    assert all(action.startswith("app.") for action in actions)


def test_command_enabled_reasons_follow_active_context_matrix() -> None:
    """Command availability is derived from explicit ActiveContext fields."""

    registry = default_command_registry()
    empty = ActiveContextSnapshot()

    assert registry.evaluate(CommandId.OPEN_FILE, empty).enabled is True
    save = registry.evaluate(CommandId.SAVE_DOCUMENT, empty)
    assert save.enabled is False
    assert save.disabled_reason == "No unsaved changes."
    export = registry.evaluate(CommandId.EXPORT, empty)
    assert export.enabled is False
    assert export.disabled_reason == "No active resource."

    resource = ResourceId("file:///tmp/sample.h5", "/values")
    active = ActiveContextSnapshot(
        document_id="doc-1",
        resource_id=resource,
        request_generation=3,
        active_split_id="split-main",
        active_view_id="view-table",
    )

    assert registry.evaluate(CommandId.EXPORT, active).enabled is True
    assert registry.evaluate(CommandId.FIND_CURRENT, active).enabled is True
    assert registry.evaluate(CommandId.SPLIT_VIEW, active).enabled is True
    assert registry.evaluate(CommandId.CLOSE_VIEW, active).enabled is True
    assert registry.evaluate(CommandId.SAVE_DOCUMENT, active).enabled is False

    dirty = active.with_edit_state(
        has_dirty_changes=True,
        can_undo=True,
        can_redo=False,
    )
    assert registry.evaluate(CommandId.SAVE_DOCUMENT, dirty).enabled is True
    assert registry.evaluate(CommandId.UNDO, dirty).enabled is True
    redo = registry.evaluate(CommandId.REDO, dirty)
    assert redo.enabled is False
    assert redo.disabled_reason == "Nothing to redo."


def test_active_context_tracks_view_selection_task_and_dirty_state() -> None:
    """ActiveContext records explicit app state without GUI widget coupling."""

    context = ActiveContext()
    resource = ResourceId("file:///tmp/table.csv", "/table")

    snapshot = context.activate_view(
        document_id="doc-7",
        resource_id=resource,
        request_generation=5,
        active_split_id="split-a",
        active_view_id="view-a",
        selection_label="rows 0:100",
    )
    assert snapshot.document_id == "doc-7"
    assert snapshot.resource_id == resource
    assert snapshot.active_split_id == "split-a"
    assert snapshot.active_view_id == "view-a"
    assert snapshot.selection_label == "rows 0:100"

    snapshot = context.set_edit_state(
        has_dirty_changes=True,
        can_undo=True,
        can_redo=True,
    )
    assert snapshot.has_dirty_changes is True
    assert snapshot.can_undo is True
    assert snapshot.can_redo is True

    snapshot = context.set_task_state(has_active_task=True)
    assert snapshot.has_active_task is True

    snapshot = context.set_bottom_panel_visible(False)
    assert snapshot.bottom_panel_visible is False

    assert context.clear() == ActiveContextSnapshot()
