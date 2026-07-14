"""Stable command registry for Data Viewer UI actions.

The registry is deliberately application-level: command labels, shortcuts,
semantic actions, and enabled reasons are defined without importing Qt widgets.
Concrete GUI handlers bind to the semantic ``action`` values in later tasks.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum

from data_viewer.app.active_context import ActiveContextSnapshot


class CommandId(StrEnum):
    """Stable command identifiers for the v1 shell."""

    OPEN_FILE = "open_file"
    OPEN_WORKSPACE = "open_workspace"
    SAVE_DOCUMENT = "save_document"
    SAVE_AS = "save_as"
    EXPORT = "export"
    CLOSE_VIEW = "close_view"
    COMMAND_PALETTE = "command_palette"
    FIND_CURRENT = "find_current"
    GLOBAL_SEARCH = "global_search"
    SPLIT_VIEW = "split_view"
    TOGGLE_BOTTOM_PANEL = "toggle_bottom_panel"
    UNDO = "undo"
    REDO = "redo"


type CommandPredicate = Callable[[ActiveContextSnapshot], tuple[bool, str | None]]


@dataclass(frozen=True, slots=True)
class CommandDefinition:
    """One public command contract entry."""

    command_id: CommandId
    label: str
    shortcut: str
    action: str
    enabled_when: CommandPredicate
    linux_shortcut: str | None = None
    description: str = ""


@dataclass(frozen=True, slots=True)
class CommandEvaluation:
    """Evaluated command state for one context snapshot."""

    command_id: CommandId
    label: str
    shortcut: str
    action: str
    enabled: bool
    disabled_reason: str | None


class CommandRegistry:
    """Read-only command registry with deterministic ordering."""

    def __init__(self, definitions: Iterable[CommandDefinition]) -> None:
        ordered = tuple(definitions)
        by_id: dict[CommandId, CommandDefinition] = {}
        for definition in ordered:
            if definition.command_id in by_id:
                raise ValueError(f"Duplicate command id: {definition.command_id.value}")
            by_id[definition.command_id] = definition
        self._ordered = ordered
        self._by_id = by_id

    def definitions(self) -> tuple[CommandDefinition, ...]:
        """Return commands in stable presentation order."""

        return self._ordered

    def get(self, command_id: CommandId) -> CommandDefinition:
        """Return one command definition or raise KeyError for unknown IDs."""

        return self._by_id[command_id]

    def shortcut_for(
        self,
        command_id: CommandId,
        *,
        platform: str = "Windows",
    ) -> str:
        """Return platform-appropriate shortcut text."""

        definition = self.get(command_id)
        if platform.lower().startswith("linux") and definition.linux_shortcut:
            return definition.linux_shortcut
        return definition.shortcut

    def evaluate(
        self,
        command_id: CommandId,
        context: ActiveContextSnapshot,
        *,
        platform: str = "Windows",
    ) -> CommandEvaluation:
        """Evaluate whether a command is currently available."""

        definition = self.get(command_id)
        enabled, reason = definition.enabled_when(context)
        if enabled:
            reason = None
        return CommandEvaluation(
            command_id=definition.command_id,
            label=definition.label,
            shortcut=self.shortcut_for(command_id, platform=platform),
            action=definition.action,
            enabled=enabled,
            disabled_reason=reason,
        )


def default_command_registry() -> CommandRegistry:
    """Build the v1 baseline command registry from the UI/UX specification."""

    return CommandRegistry(
        [
            _command(CommandId.OPEN_FILE, "Open file", "Ctrl+O", "app.open_file"),
            _command(
                CommandId.OPEN_WORKSPACE,
                "Open workspace",
                "Ctrl+Shift+O",
                "app.open_workspace",
            ),
            _command(
                CommandId.SAVE_DOCUMENT,
                "Save document",
                "Ctrl+S",
                "app.save_document",
                _dirty_required("No unsaved changes."),
            ),
            _command(
                CommandId.SAVE_AS,
                "Save As",
                "Ctrl+Shift+S",
                "app.save_as",
                _document_required,
            ),
            _command(
                CommandId.EXPORT,
                "Export",
                "Ctrl+E",
                "app.export",
                _resource_required,
            ),
            _command(
                CommandId.CLOSE_VIEW,
                "Close view",
                "Ctrl+W",
                "app.close_view",
                _view_required,
            ),
            _command(
                CommandId.COMMAND_PALETTE,
                "Command palette",
                "Ctrl+Shift+P",
                "app.command_palette",
            ),
            _command(
                CommandId.FIND_CURRENT,
                "Find in current context",
                "Ctrl+F",
                "app.find_current",
                _resource_required,
            ),
            _command(
                CommandId.GLOBAL_SEARCH,
                "Global resource search",
                "Ctrl+Shift+F",
                "app.global_search",
            ),
            _command(
                CommandId.SPLIT_VIEW,
                "Split view",
                "Ctrl+\\",
                "app.split_view",
                _view_required,
            ),
            _command(
                CommandId.TOGGLE_BOTTOM_PANEL,
                "Toggle bottom panel",
                "Ctrl+J",
                "app.toggle_bottom_panel",
            ),
            _command(
                CommandId.UNDO,
                "Undo",
                "Ctrl+Z",
                "app.undo",
                lambda context: (
                    (True, None) if context.can_undo else (False, "Nothing to undo.")
                ),
            ),
            _command(
                CommandId.REDO,
                "Redo",
                "Ctrl+Shift+Z",
                "app.redo",
                lambda context: (
                    (True, None) if context.can_redo else (False, "Nothing to redo.")
                ),
            ),
        ]
    )


def _command(
    command_id: CommandId,
    label: str,
    shortcut: str,
    action: str,
    enabled_when: CommandPredicate | None = None,
) -> CommandDefinition:
    return CommandDefinition(
        command_id=command_id,
        label=label,
        shortcut=shortcut,
        action=action,
        enabled_when=enabled_when or _always_enabled,
    )


def _always_enabled(context: ActiveContextSnapshot) -> tuple[bool, str | None]:
    return True, None


def _document_required(context: ActiveContextSnapshot) -> tuple[bool, str | None]:
    if context.document_id is None:
        return False, "No active document."
    return True, None


def _resource_required(context: ActiveContextSnapshot) -> tuple[bool, str | None]:
    if context.resource_id is None:
        return False, "No active resource."
    return True, None


def _view_required(context: ActiveContextSnapshot) -> tuple[bool, str | None]:
    if context.active_view_id is None:
        return False, "No active view."
    return True, None


def _dirty_required(reason: str) -> CommandPredicate:
    def predicate(context: ActiveContextSnapshot) -> tuple[bool, str | None]:
        if not context.has_dirty_changes:
            return False, reason
        return True, None

    return predicate


__all__ = [
    "CommandDefinition",
    "CommandEvaluation",
    "CommandId",
    "CommandRegistry",
    "default_command_registry",
]
