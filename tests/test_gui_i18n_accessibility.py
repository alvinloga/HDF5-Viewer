"""DV-0607 localization, accessibility, and high-DPI GUI contracts."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QTreeWidget, QWidget

from data_viewer.gui.accessibility import (
    AccessibilityIssue,
    PlotAccessibilitySummary,
    audit_accessible_widgets,
    focus_chain_names,
    scaled_metric,
)
from data_viewer.domain import ResourceId, SourceFingerprint
from data_viewer.editing.review import SaveReview, SaveStrategy
from data_viewer.gui.dialogs import SaveSummaryDialog
from data_viewer.gui.i18n import Locale, UiStringKey, missing_catalog_entries, tr
from data_viewer.gui.shell import DataViewerShell
from data_viewer.gui.state_components import StateKind, default_state_model
from data_viewer.gui.views import TableViewWidget
from data_viewer.sources import SourceRegistry
from data_viewer.sources.hdf5 import HDF5Adapter


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(["data-viewer-i18n-accessibility-test"])
    return app


def test_ui_catalog_has_complete_english_and_simplified_chinese_entries() -> None:
    """Every centralized shell/dialog/state string has en-US and zh-CN text."""

    assert missing_catalog_entries() == {}
    assert tr(UiStringKey.APP_TITLE, Locale.EN_US) == "Data Viewer"
    assert tr(UiStringKey.APP_TITLE, Locale.ZH_CN) == "Data Viewer"
    assert tr(UiStringKey.COMMAND_OPEN, Locale.ZH_CN) == "打开"
    assert tr(UiStringKey.STATUS_READY, Locale.EN_US) == "Ready"


def test_shell_uses_centralized_visible_strings_and_accessible_metadata() -> None:
    """Initial shell strings and accessibility metadata come from the UI catalog."""

    app = _qapp()
    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]), locale=Locale.ZH_CN)
    shell.show()
    app.processEvents()

    assert shell.windowTitle() == tr(UiStringKey.APP_TITLE, Locale.ZH_CN)
    assert shell.findChild(QPushButton, "open_button").text() == tr(UiStringKey.COMMAND_OPEN, Locale.ZH_CN)
    assert shell.findChild(QPushButton, "save_button").text() == tr(UiStringKey.COMMAND_SAVE, Locale.ZH_CN)
    assert shell.findChild(QLineEdit, "path_input").placeholderText() == tr(
        UiStringKey.PATH_INPUT_PLACEHOLDER,
        Locale.ZH_CN,
    )
    assert shell.findChild(QTreeWidget, "navigation_region").accessibleName() == tr(
        UiStringKey.ACCESSIBLE_NAVIGATION,
        Locale.ZH_CN,
    )
    assert shell.findChild(QLabel, "status_label").text() == tr(UiStringKey.STATUS_READY, Locale.ZH_CN)
    assert shell.findChild(QLabel, "status_label").accessibleName()
    shell.close()


def test_dialog_and_state_defaults_are_localized_from_catalog() -> None:
    """Dialog titles/buttons and standard state defaults use the shared catalog."""

    app = _qapp()
    review = SaveReview(
        target_uri="file:///tmp/source.h5",
        strategy=SaveStrategy.IN_PLACE,
        source_fingerprint=SourceFingerprint(
            size_bytes=128,
            modified_time_ns=123,
            content_tag="sha256:abc",
        ),
        resources=(ResourceId("file:///tmp/source.h5", "/values"),),
        patch_count=1,
        changed_patch_kinds=(("cell", 1),),
        estimated_size_bytes=64,
    )
    dialog = SaveSummaryDialog(review, locale=Locale.ZH_CN)
    app.processEvents()

    assert dialog.windowTitle() == tr(UiStringKey.DIALOG_SAVE_SUMMARY_TITLE, Locale.ZH_CN)
    assert dialog.findChild(QPushButton, "cancel_button").text() == tr(
        UiStringKey.COMMAND_CANCEL,
        Locale.ZH_CN,
    )
    assert dialog.findChild(QPushButton, "confirm_save_button").text() == tr(
        UiStringKey.DIALOG_SAVE_CONFIRM,
        Locale.ZH_CN,
    )

    model = default_state_model(StateKind.READ_ONLY, target="Workspace", locale=Locale.ZH_CN)
    assert model.title == tr(UiStringKey.STATE_READ_ONLY_TITLE, Locale.ZH_CN)
    assert model.actions[0].label == tr(UiStringKey.COMMAND_SAVE_AS, Locale.ZH_CN)


def test_base_view_chrome_and_plot_summary_contract_are_localized() -> None:
    """Base views and plot descriptions have a localized accessibility contract."""

    app = _qapp()
    view = TableViewWidget(locale=Locale.ZH_CN)
    app.processEvents()

    assert view.findChild(QLabel, "view_scope_label").text() == tr(
        UiStringKey.VIEW_SCOPE_EMPTY,
        Locale.ZH_CN,
    )
    assert view.findChild(QLabel, "view_coordinates_label").text() == tr(
        UiStringKey.VIEW_COORDINATES_EMPTY,
        Locale.ZH_CN,
    )

    summary = PlotAccessibilitySummary(
        title="Intensity histogram",
        axes=("Intensity", "Count"),
        series=("foreground",),
        value_range="0 to 255",
        warnings=("sampled 10%",),
        data_table_available=True,
    )
    assert summary.to_accessible_description(Locale.EN_US) == (
        "Plot: Intensity histogram. Axes: Intensity, Count. "
        "Series: foreground. Range: 0 to 255. Warnings: sampled 10%. "
        "Data table available."
    )
    assert "图表：" in summary.to_accessible_description(Locale.ZH_CN)


def test_shell_focus_order_starts_with_command_path_then_primary_actions() -> None:
    """Keyboard users can reach the path field and primary actions in deterministic order."""

    app = _qapp()
    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    shell.show()
    app.processEvents()

    assert focus_chain_names(shell, start_name="path_input", limit=4) == [
        "path_input",
        "open_button",
        "cancel_open_button",
        "review_changes_button",
    ]
    shell.close()


def test_accessibility_audit_reports_missing_names_without_false_success() -> None:
    """The audit helper detects nameless interactive widgets and passes the shell baseline."""

    app = _qapp()
    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]))
    shell.show()
    app.processEvents()

    assert audit_accessible_widgets(shell) == []

    extra = QPushButton("Unsafe unlabeled button", shell)
    extra.setObjectName("unsafe_unlabeled_button")
    extra.setAccessibleName("")
    issue = AccessibilityIssue(
        object_name="unsafe_unlabeled_button",
        widget_class="QPushButton",
        problem="missing accessible name",
    )
    assert issue in audit_accessible_widgets(extra)
    shell.close()


def test_scaled_metric_uses_four_pixel_grid_at_200_percent() -> None:
    """High-DPI helper scales compact metrics while preserving the 4 px grid."""

    assert scaled_metric(6, scale_factor=2.0) == 12
    assert scaled_metric(7, scale_factor=2.0, grid=4) == 16
    assert scaled_metric(7, scale_factor=1.0, grid=4) == 8
    assert scaled_metric(0, scale_factor=2.0) == 0


def test_shell_renders_core_actions_in_simulated_200_percent_layout(tmp_path: Path) -> None:
    """The shell keeps primary actions visible in a deterministic 200% screenshot."""

    app = _qapp()
    shell = DataViewerShell(source_registry=SourceRegistry([HDF5Adapter()]), locale=Locale.ZH_CN)
    shell.resize(scaled_metric(1024, scale_factor=2.0), scaled_metric(768, scale_factor=2.0))
    shell.show()
    app.processEvents()

    for name in [
        "path_input",
        "open_button",
        "save_button",
        "save_as_button",
        "export_button",
        "navigation_region",
        "workspace_tabs",
        "bottom_panel",
    ]:
        widget = shell.findChild(QWidget, name)
        assert widget is not None, name
        assert widget.isVisible(), name
        assert widget.size().width() > 0, name
        assert widget.size().height() > 0, name

    screenshot = shell.grab()
    screenshot_path = tmp_path / "data-viewer-shell-zh-200pct.png"
    assert not screenshot.isNull()
    assert screenshot.save(str(screenshot_path))
    assert screenshot_path.stat().st_size > 0
    shell.close()
