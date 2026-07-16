"""Contracts for standard Data Viewer GUI state components."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from data_viewer.gui.state_components import (
    StateAction,
    StateKind,
    StateViewModel,
    StandardStateWidget,
    default_state_model,
    error_state_model,
)


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(["data-viewer-state-test"])
    return app


def test_every_standard_state_has_text_icon_and_accessibility() -> None:
    """Each required state is explicit without relying on color alone."""

    app = _qapp()
    widget = StandardStateWidget()
    for state in StateKind:
        model = default_state_model(state, target="Workspace")
        widget.render_state(model)
        app.processEvents()

        assert widget.property("stateKind") == state.value
        assert widget.objectName() == f"standard_state_{state.value}"
        assert widget.accessibleName() == model.title
        assert widget.findChild(QLabel, "state_icon_label").text()
        assert widget.findChild(QLabel, "state_kind_label").text() == state.value.replace("_", " ")
        assert widget.findChild(QLabel, "state_title_label").text() == model.title
        assert widget.findChild(QLabel, "state_summary_label").text() == model.summary
        assert widget.findChild(QLabel, "state_icon_label").accessibleName()


def test_error_state_exposes_safe_details_and_retry_action() -> None:
    """Error states expose safe summary/details and a keyboard-reachable retry."""

    app = _qapp()
    widget = StandardStateWidget()
    widget.render_state(
        error_state_model(
            target="sample.h5",
            summary="Could not open source.",
            safe_details="HDF5 signature was not found.",
            retry_command="app.open_file",
        )
    )

    assert widget.property("stateKind") == StateKind.ERROR.value
    assert "Could not open source." in widget.findChild(QLabel, "state_summary_label").text()
    assert "HDF5 signature" in widget.findChild(QLabel, "state_details_label").text()
    buttons = widget.findChildren(QPushButton)
    assert [button.text() for button in buttons] == ["Retry", "Details"]
    assert all(button.focusPolicy() is Qt.FocusPolicy.StrongFocus for button in buttons)
    assert buttons[0].property("command") == "app.open_file"
    app.processEvents()


def test_disabled_and_dirty_states_carry_actionable_reasons() -> None:
    """Disabled and dirty states keep their reason/action in text and tooltip semantics."""

    app = _qapp()
    widget = StandardStateWidget()
    widget.render_state(
        StateViewModel(
            kind=StateKind.DISABLED,
            title="Export disabled",
            summary="No active resource.",
            target="Export command",
            actions=(StateAction(label="Select resource", command="app.find_current", reason="No active resource."),),
        )
    )
    button = widget.findChild(QPushButton, "state_action_0")
    assert button is not None
    assert not button.isEnabled()
    assert "No active resource." in button.toolTip()

    widget.render_state(
        StateViewModel(
            kind=StateKind.DIRTY,
            title="Unsaved changes",
            summary="1 pending patch is ready for review.",
            target="Active document",
            actions=(
                StateAction(label="Review changes", command="app.review_changes", primary=True),
                StateAction(label="Save", command="app.save_document", primary=True),
            ),
        )
    )
    texts = [button.text() for button in widget.findChildren(QPushButton)]
    assert texts == ["Review changes", "Save"]
    app.processEvents()
