"""Contracts for DV-0606 dialog primitives."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton

from data_viewer.domain import ResourceId, SourceFingerprint
from data_viewer.editing.review import SaveReview, SaveStrategy
from data_viewer.gui.dialogs import (
    DestructiveConfirmationDialog,
    ImportOptionsDialog,
    PathValidationWidget,
    SaveSummaryDialog,
)


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(["data-viewer-dialog-test"])
    return app


def _fingerprint() -> SourceFingerprint:
    return SourceFingerprint(
        size_bytes=128,
        modified_time_ns=123,
        content_tag="sha256:abc",
    )


def test_path_validation_widget_reports_inline_errors_and_preserves_long_path(tmp_path: Path) -> None:
    """Path validation is inline, selectable, and long paths preserve their filename."""

    app = _qapp()
    widget = PathValidationWidget(mode="save")
    missing_parent = tmp_path / "missing" / "out.npy"
    widget.set_path(missing_parent)
    app.processEvents()

    assert not widget.is_valid()
    assert "Parent directory does not exist" in widget.findChild(QLabel, "path_error_label").text()
    assert widget.findChild(QLineEdit, "path_input").text() == str(missing_parent)

    long_path = tmp_path / ("nested-" + "x" * 80) / "result-with-important-name.csv"
    long_path.parent.mkdir()
    widget.set_path(long_path)
    app.processEvents()

    assert widget.is_valid()
    label = widget.findChild(QLabel, "path_display_label")
    assert label is not None
    assert "result-with-important-name.csv" in label.text()
    assert label.toolTip() == str(long_path)
    assert label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse


def test_save_summary_dialog_is_modal_and_names_target_strategy_and_warnings() -> None:
    """Save summaries authorize disk mutation with target-specific details."""

    app = _qapp()
    review = SaveReview(
        target_uri="file:///tmp/source.h5",
        strategy=SaveStrategy.IN_PLACE,
        source_fingerprint=_fingerprint(),
        resources=(ResourceId("file:///tmp/source.h5", "/values"),),
        patch_count=2,
        changed_patch_kinds=(("cell", 2),),
        estimated_size_bytes=64,
        warnings=("External metadata will be preserved.",),
    )
    dialog = SaveSummaryDialog(review)
    app.processEvents()

    assert dialog.windowModality() is Qt.WindowModality.ApplicationModal
    assert "file:///tmp/source.h5" in dialog.findChild(QLabel, "save_target_label").text()
    assert "in_place" in dialog.findChild(QLabel, "save_strategy_label").text()
    assert "cell: 2" in dialog.findChild(QLabel, "save_patch_kinds_label").text()
    assert "External metadata" in dialog.findChild(QLabel, "save_warnings_label").text()
    assert dialog.default_action() == "cancel"


def test_destructive_confirmation_has_safe_default_and_specific_consequence() -> None:
    """Destructive confirmations are never generic and default to Cancel."""

    app = _qapp()
    dialog = DestructiveConfirmationDialog(
        resource_label="/values",
        consequence="Overwrite 2 reviewed cell patches in file:///tmp/source.h5.",
    )
    app.processEvents()

    assert dialog.windowModality() is Qt.WindowModality.ApplicationModal
    assert "Are you sure" not in dialog.findChild(QLabel, "destructive_summary_label").text()
    assert "/values" in dialog.findChild(QLabel, "destructive_summary_label").text()
    assert "Overwrite 2 reviewed cell patches" in dialog.findChild(QLabel, "destructive_consequence_label").text()
    cancel = dialog.findChild(QPushButton, "cancel_button")
    confirm = dialog.findChild(QPushButton, "confirm_button")
    assert cancel is not None and confirm is not None
    assert cancel.isDefault()
    assert not confirm.isDefault()


def test_import_options_dialog_is_preview_first_and_non_destructive(tmp_path: Path) -> None:
    """Import options expose preview before enabling Apply."""

    app = _qapp()
    source = tmp_path / "table.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    dialog = ImportOptionsDialog(source)
    app.processEvents()

    assert dialog.windowModality() is not Qt.WindowModality.ApplicationModal
    assert dialog.result() == 0
    assert dialog.findChild(QLabel, "import_preview_label").text().startswith("Preview:")
    assert "a,b" in dialog.findChild(QLabel, "import_preview_label").text()
    apply_button = dialog.findChild(QPushButton, "apply_import_button")
    assert apply_button is not None
    assert not apply_button.isDefault()
    assert dialog.findChild(QPushButton, "cancel_button").isDefault()


def test_save_summary_rejects_empty_review() -> None:
    """A save dialog without reviewed changes would authorize the wrong operation."""

    with pytest.raises(ValueError, match="patch"):
        SaveSummaryDialog(
            SaveReview(
                target_uri="file:///tmp/source.h5",
                strategy=SaveStrategy.IN_PLACE,
                source_fingerprint=_fingerprint(),
                resources=(),
                patch_count=0,
                changed_patch_kinds=(),
                estimated_size_bytes=0,
            )
        )
