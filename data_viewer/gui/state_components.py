"""Reusable standard state components for Data Viewer Qt surfaces.

The widget in this module is intentionally small and dependency-light. DV-0604
creates a consistent state vocabulary before every shell/view surface is wired
to it, so later work can replace ad-hoc labels without changing semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from data_viewer.gui.theme import IconName
from data_viewer.gui.i18n import Locale, UiStringKey, tr


class StateKind(StrEnum):
    """Standard async/content states required by the UI/UX specification."""

    INITIAL = "initial"
    LOADING = "loading"
    EMPTY = "empty"
    READY = "ready"
    PARTIAL = "partial"
    ERROR = "error"
    DISABLED = "disabled"
    DIRTY = "dirty"
    READ_ONLY = "read_only"
    CONFLICTED = "conflicted"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class StateAction:
    """One state-local action exposed as a keyboard-reachable button."""

    label: str
    command: str
    enabled: bool = True
    primary: bool = False
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class StateViewModel:
    """Presentation-independent state description for Qt state widgets."""

    kind: StateKind
    title: str
    summary: str
    target: str
    details: str | None = None
    actions: tuple[StateAction, ...] = ()
    busy: bool = False


_STATE_DEFAULTS: dict[StateKind, tuple[str, str, IconName]] = {
    StateKind.INITIAL: (
        "Ready to begin",
        "Choose a source or select a resource to continue.",
        IconName.INFO,
    ),
    StateKind.LOADING: (
        "Loading",
        "Work is running and can be cancelled when the caller provides cancellation.",
        IconName.LOADING,
    ),
    StateKind.EMPTY: (
        "Nothing to show",
        "This state can be valid when the selected source or filter has no results.",
        IconName.INFO,
    ),
    StateKind.READY: (
        "Ready",
        "Content is available with its current scope and provenance.",
        IconName.WORKSPACE,
    ),
    StateKind.PARTIAL: (
        "Partial view",
        "Only a bounded preview, page, slice, or sample is displayed.",
        IconName.WARNING,
    ),
    StateKind.ERROR: (
        "Could not complete operation",
        "A safe error summary is available. Details are limited to this target.",
        IconName.ERROR,
    ),
    StateKind.DISABLED: (
        "Unavailable",
        "This action is disabled until the required context exists.",
        IconName.INFO,
    ),
    StateKind.DIRTY: (
        "Unsaved changes",
        "Review, save, discard, or export changes before closing.",
        IconName.DIRTY,
    ),
    StateKind.READ_ONLY: (
        "Read-only",
        "This source can be inspected and exported, but v1 will not overwrite it.",
        IconName.READ_ONLY,
    ),
    StateKind.CONFLICTED: (
        "Conflict detected",
        "Saving is blocked until the source is reloaded or changes are saved elsewhere.",
        IconName.WARNING,
    ),
    StateKind.STALE: (
        "Stale result",
        "The source, parameters, or selection changed after this result was produced.",
        IconName.WARNING,
    ),
}

_STATE_TEXT_KEYS: dict[StateKind, tuple[UiStringKey, UiStringKey]] = {
    StateKind.INITIAL: (UiStringKey.STATE_INITIAL_TITLE, UiStringKey.STATE_INITIAL_SUMMARY),
    StateKind.LOADING: (UiStringKey.STATE_LOADING_TITLE, UiStringKey.STATE_LOADING_SUMMARY),
    StateKind.EMPTY: (UiStringKey.STATE_EMPTY_TITLE, UiStringKey.STATE_EMPTY_SUMMARY),
    StateKind.READY: (UiStringKey.STATE_READY_TITLE, UiStringKey.STATE_READY_SUMMARY),
    StateKind.PARTIAL: (UiStringKey.STATE_PARTIAL_TITLE, UiStringKey.STATE_PARTIAL_SUMMARY),
    StateKind.ERROR: (UiStringKey.STATE_ERROR_TITLE, UiStringKey.STATE_ERROR_SUMMARY),
    StateKind.DISABLED: (UiStringKey.STATE_DISABLED_TITLE, UiStringKey.STATE_DISABLED_SUMMARY),
    StateKind.DIRTY: (UiStringKey.STATE_DIRTY_TITLE, UiStringKey.STATE_DIRTY_SUMMARY),
    StateKind.READ_ONLY: (UiStringKey.STATE_READ_ONLY_TITLE, UiStringKey.STATE_READ_ONLY_SUMMARY),
    StateKind.CONFLICTED: (UiStringKey.STATE_CONFLICTED_TITLE, UiStringKey.STATE_CONFLICTED_SUMMARY),
    StateKind.STALE: (UiStringKey.STATE_STALE_TITLE, UiStringKey.STATE_STALE_SUMMARY),
}


def default_state_model(
    kind: StateKind,
    *,
    target: str,
    locale: Locale = Locale.EN_US,
) -> StateViewModel:
    """Build a useful default state model for component tests and simple views."""

    title_key, summary_key = _STATE_TEXT_KEYS[kind]
    title = tr(title_key, locale)
    summary = tr(summary_key, locale)
    actions: tuple[StateAction, ...]
    if kind is StateKind.LOADING:
        actions = (StateAction(tr(UiStringKey.COMMAND_CANCEL, locale), "state.cancel", primary=True),)
    elif kind is StateKind.INITIAL:
        actions = (StateAction(tr(UiStringKey.COMMAND_OPEN_SOURCE, locale), "app.open_file", primary=True),)
    elif kind is StateKind.EMPTY:
        actions = (StateAction(tr(UiStringKey.COMMAND_CLEAR_FILTER, locale), "app.clear_filter"),)
    elif kind is StateKind.PARTIAL:
        actions = (StateAction(tr(UiStringKey.COMMAND_REFINE, locale), "state.refine", primary=True),)
    elif kind is StateKind.ERROR:
        actions = (StateAction(tr(UiStringKey.COMMAND_RETRY, locale), "state.retry", primary=True),)
    elif kind is StateKind.DISABLED:
        actions = (
            StateAction(
                tr(UiStringKey.COMMAND_UNAVAILABLE, locale),
                "state.disabled",
                enabled=False,
                reason=summary,
            ),
        )
    elif kind is StateKind.DIRTY:
        actions = (
            StateAction(tr(UiStringKey.COMMAND_REVIEW_CHANGES, locale), "app.review_changes", primary=True),
            StateAction(tr(UiStringKey.COMMAND_SAVE, locale), "app.save_document", primary=True),
        )
    elif kind is StateKind.READ_ONLY:
        actions = (
            StateAction(tr(UiStringKey.COMMAND_SAVE_AS, locale), "app.save_as"),
            StateAction(tr(UiStringKey.COMMAND_EXPORT, locale), "app.export"),
        )
    elif kind is StateKind.CONFLICTED:
        actions = (
            StateAction(tr(UiStringKey.COMMAND_RELOAD_SOURCE, locale), "app.reload_source"),
            StateAction(tr(UiStringKey.COMMAND_SAVE_AS, locale), "app.save_as", primary=True),
        )
    elif kind is StateKind.STALE:
        actions = (StateAction(tr(UiStringKey.COMMAND_RECOMPUTE, locale), "state.recompute", primary=True),)
    else:
        actions = ()
    return StateViewModel(
        kind=kind,
        title=title,
        summary=summary,
        target=target,
        actions=actions,
        busy=kind is StateKind.LOADING,
    )


def error_state_model(
    *,
    target: str,
    summary: str,
    safe_details: str,
    retry_command: str,
    locale: Locale = Locale.EN_US,
) -> StateViewModel:
    """Build a safe error state with retry and details affordances."""

    return StateViewModel(
        kind=StateKind.ERROR,
        title=f"Could not load {target}",
        summary=summary,
        target=target,
        details=safe_details,
        actions=(
            StateAction(tr(UiStringKey.COMMAND_RETRY, locale), retry_command, primary=True),
            StateAction(tr(UiStringKey.COMMAND_DETAILS, locale), "state.show_details"),
        ),
    )


class StandardStateWidget(QFrame):
    """Compact native Qt presentation for one standard Data Viewer state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("standard_state_initial")
        self.setProperty("stateKind", StateKind.INITIAL.value)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)

    def render_state(self, model: StateViewModel) -> None:
        """Render the state model without relying on color as the only cue."""

        self._clear_layout()
        self.setObjectName(f"standard_state_{model.kind.value}")
        self.setProperty("stateKind", model.kind.value)
        self.setAccessibleName(model.title)
        self.setAccessibleDescription(f"{model.target}: {model.summary}")
        self.setProperty("busy", model.busy)

        title, _summary, icon = _STATE_DEFAULTS[model.kind]
        icon_label = QLabel(self)
        icon_label.setObjectName("state_icon_label")
        icon_label.setText(_STATE_DEFAULTS[model.kind][2].value.replace("_", " "))
        icon_label.setAccessibleName(f"{title} icon: {icon.value}")

        kind_label = QLabel(model.kind.value.replace("_", " "), self)
        kind_label.setObjectName("state_kind_label")
        kind_label.setAccessibleName("State kind")

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        header_layout.addWidget(icon_label)
        header_layout.addWidget(kind_label)
        header_layout.addStretch(1)
        self._layout.addWidget(header)

        title_label = QLabel(model.title, self)
        title_label.setObjectName("state_title_label")
        title_label.setAccessibleName("State title")
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._layout.addWidget(title_label)

        summary_label = QLabel(model.summary, self)
        summary_label.setObjectName("state_summary_label")
        summary_label.setAccessibleName("State summary")
        summary_label.setWordWrap(True)
        summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._layout.addWidget(summary_label)

        details_label = QLabel(model.details or "", self)
        details_label.setObjectName("state_details_label")
        details_label.setAccessibleName("Safe state details")
        details_label.setWordWrap(True)
        details_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_label.setVisible(bool(model.details))
        self._layout.addWidget(details_label)

        if model.actions:
            action_row = QWidget(self)
            action_row.setObjectName("state_action_row")
            action_layout = QHBoxLayout(action_row)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(8)
            for index, action in enumerate(model.actions):
                button = QPushButton(action.label, self)
                button.setObjectName(f"state_action_{index}")
                button.setProperty("command", action.command)
                button.setProperty("primary", action.primary)
                button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                is_enabled = action.enabled and action.reason is None
                button.setEnabled(is_enabled)
                if action.reason:
                    button.setToolTip(action.reason)
                    button.setAccessibleDescription(action.reason)
                else:
                    button.setToolTip(action.label)
                action_layout.addWidget(button)
            action_layout.addStretch(1)
            self._layout.addWidget(action_row)
        self._layout.addStretch(1)

    def _clear_layout(self) -> None:
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)


__all__ = [
    "StateAction",
    "StateKind",
    "StateViewModel",
    "StandardStateWidget",
    "default_state_model",
    "error_state_model",
]
