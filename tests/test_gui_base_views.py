"""Contracts for DV-0605 base data view widgets."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit, QTableView

from data_viewer.domain import (
    ArrayPayload,
    AxisSelection,
    ColumnSpec,
    OperationScope,
    ReadResult,
    SelectionSpec,
    SpatialMetadata,
    TablePayload,
    TextPayload,
    VolumePayload,
)
from data_viewer.gui.views import (
    ArrayViewWidget,
    BaseViewContract,
    ImageViewWidget,
    MultidimensionalSliceNavigatorWidget,
    NiftiOrthogonalViewerWidget,
    TableViewWidget,
    TextViewWidget,
    ViewKind,
)


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(["data-viewer-base-views-test"])
    return app


def test_table_view_is_virtual_and_keeps_source_rows_as_headers() -> None:
    """Tables expose paged source coordinates without injecting row-number columns."""

    app = _qapp()
    payload = TablePayload(
        columns=(
            ColumnSpec("alpha", "int64", nullable=False),
            ColumnSpec("beta", "float64", nullable=False),
        ),
        column_values=(np.arange(10_000), np.arange(10_000, dtype=np.float64) / 10),
        row_offset=500,
        total_rows=50_000,
    )
    widget = TableViewWidget()
    widget.render_read_result(
        ReadResult(
            payload=payload,
            scope=OperationScope.PAGE,
            bytes_read=160_000,
            is_sampled=False,
            sample=None,
        )
    )
    app.processEvents()

    table = widget.findChild(QTableView, "table_view")
    assert table is not None
    model = table.model()
    assert model is not None
    assert model.rowCount() == 10_000
    assert model.columnCount() == 2
    assert model.headerData(0, Qt.Orientation.Horizontal) == "alpha"
    assert model.headerData(1, Qt.Orientation.Vertical) == "501"
    assert model.data(model.index(1, 1)) == "0.1"
    assert widget.findChild(QLabel, "view_scope_label").text() == "scope: page"
    assert widget.findChild(QLabel, "view_coordinates_label").text() == "rows: 500:10500"
    assert len(table.findChildren(QLabel)) == 0


def test_array_view_does_not_flatten_high_dimensional_payloads() -> None:
    """High-dimensional arrays keep their slice expression visible and refuse flattening."""

    app = _qapp()
    selection = SelectionSpec.hyperslab(
        AxisSelection(axis=0, index=1),
        AxisSelection.slice(1, start=2, stop=5),
        AxisSelection.slice(2, start=0, stop=4),
    ).normalize((3, 6, 4)).unwrap()
    payload = ArrayPayload(
        values=np.arange(12).reshape(3, 4),
        original_shape=(3, 6, 4),
        selection=selection,
    )
    widget = ArrayViewWidget()
    widget.render_read_result(
        ReadResult(
            payload=payload,
            scope=OperationScope.SLICE,
            bytes_read=96,
            is_sampled=False,
            sample=None,
        )
    )
    app.processEvents()

    assert widget.findChild(QLabel, "view_shape_label").text() == "shape: (3, 6, 4) -> (3, 4)"
    assert widget.findChild(QLabel, "view_scope_label").text() == "scope: slice"
    assert "[0:1]" in widget.findChild(QLabel, "view_slice_label").text()
    table = widget.findChild(QTableView, "array_view")
    assert table is not None
    assert table.model().rowCount() == 3
    assert table.model().columnCount() == 4


def test_text_view_shows_partial_banner_and_line_numbers_are_presentation_only() -> None:
    """Large text previews expose truncation without mutating source text."""

    app = _qapp()
    payload = TextPayload("alpha\nbeta\n", offset=2048, is_complete=False)
    widget = TextViewWidget()
    widget.show()
    widget.render_read_result(
        ReadResult(
            payload=payload,
            scope=OperationScope.PAGE,
            bytes_read=len(payload.text),
            is_sampled=False,
            sample=None,
            warnings=("preview truncated",),
        )
    )
    app.processEvents()

    banner = widget.findChild(QLabel, "text_partial_banner")
    editor = widget.findChild(QPlainTextEdit, "text_view")
    assert banner is not None and banner.isVisible()
    assert "partial" in banner.text().lower()
    assert "offset 2048" in widget.findChild(QLabel, "view_coordinates_label").text()
    assert editor is not None
    assert editor.toPlainText() == "alpha\nbeta\n"
    assert "1 " not in editor.toPlainText()


def test_image_view_keeps_aspect_zoom_interpolation_and_cursor_metadata() -> None:
    """Image-like arrays expose display controls and source cursor coordinates."""

    app = _qapp()
    selection = SelectionSpec.hyperslab(
        AxisSelection.slice(0, start=10, stop=14),
        AxisSelection.slice(1, start=20, stop=25),
    ).normalize((100, 200)).unwrap()
    payload = ArrayPayload(
        values=np.arange(20, dtype=np.uint8).reshape(4, 5),
        original_shape=(100, 200),
        selection=selection,
    )
    widget = ImageViewWidget()
    widget.render_read_result(
        ReadResult(
            payload=payload,
            scope=OperationScope.SLICE,
            bytes_read=20,
            is_sampled=False,
            sample=None,
        )
    )
    widget.set_cursor_display_index((2, 3))
    app.processEvents()

    assert widget.contract().kind is ViewKind.IMAGE
    assert widget.contract().result_channel == "workspace.image"
    assert widget.findChild(QLabel, "image_aspect_label").text() == "aspect: preserved"
    assert widget.findChild(QLabel, "image_zoom_label").text() == "zoom: 100%"
    assert widget.findChild(QLabel, "image_interpolation_label").text() == "interpolation: nearest"
    assert widget.findChild(QLabel, "image_cursor_label").text() == "cursor: display (2, 3) source (12, 23) value 13"


def test_slice_navigator_exposes_axes_mode_and_linked_slice_state() -> None:
    """High-dimensional image projections expose explicit navigation state."""

    app = _qapp()
    selection = SelectionSpec.hyperslab(
        AxisSelection(axis=0, index=1),
        AxisSelection.slice(1, start=2, stop=6),
        AxisSelection.slice(2, start=10, stop=15),
    ).normalize((3, 12, 20)).unwrap()
    payload = ArrayPayload(
        values=np.arange(20, dtype=np.float32).reshape(4, 5),
        original_shape=(3, 12, 20),
        selection=selection,
    )
    widget = MultidimensionalSliceNavigatorWidget()
    widget.render_read_result(
        ReadResult(
            payload=payload,
            scope=OperationScope.SLICE,
            bytes_read=80,
            is_sampled=False,
            sample=None,
        )
    )
    widget.set_display_mode("display")
    widget.set_linked_slices(True)
    widget.set_axis_index(axis=0, index=2)
    app.processEvents()

    assert widget.contract().kind is ViewKind.IMAGE
    assert widget.findChild(QLabel, "slice_navigator_mode_label").text() == "mode: display"
    assert widget.findChild(QLabel, "slice_navigator_linked_label").text() == "linked slices: on"
    assert widget.findChild(QLabel, "slice_navigator_bounds_label").text() == "bounded read: slice, 80 bytes"
    axis_label = widget.findChild(QLabel, "slice_navigator_axis_summary_label")
    assert axis_label is not None
    assert "axis 0: index 2 / 0..2" in axis_label.text()
    assert "axis 1: display row [2:6:1]" in axis_label.text()
    assert "axis 2: display column [10:15:1]" in axis_label.text()


def test_slice_navigator_maps_cursor_to_high_dimensional_source_coordinates() -> None:
    """Cursor metadata includes fixed axes and displayed slice axes."""

    app = _qapp()
    selection = SelectionSpec.hyperslab(
        AxisSelection(axis=0, index=1),
        AxisSelection.slice(1, start=10, stop=14),
        AxisSelection.slice(2, start=20, stop=25),
    ).normalize((3, 30, 40)).unwrap()
    payload = ArrayPayload(
        values=np.arange(20, dtype=np.int16).reshape(4, 5),
        original_shape=(3, 30, 40),
        selection=selection,
    )
    widget = MultidimensionalSliceNavigatorWidget()
    widget.render_read_result(
        ReadResult(
            payload=payload,
            scope=OperationScope.SLICE,
            bytes_read=40,
            is_sampled=False,
            sample=None,
        )
    )
    widget.set_cursor_display_index((2, 3))
    app.processEvents()

    assert (
        widget.findChild(QLabel, "image_cursor_label").text()
        == "cursor: display (2, 3) source (1, 12, 23) value 13"
    )


def test_nifti_orthogonal_viewer_reports_planes_voxel_world_and_4d_index() -> None:
    """NIfTI orthogonal views keep orientation, crosshair, and world coordinates visible."""

    app = _qapp()
    selection = SelectionSpec.all().normalize((2, 3, 4, 5)).unwrap()
    payload = VolumePayload(
        values=np.arange(2 * 3 * 4 * 5, dtype=np.float32).reshape(2, 3, 4, 5),
        selection=selection,
        spatial=SpatialMetadata(
            affine=(
                (2.0, 0.0, 0.0, 10.0),
                (0.0, 3.0, 0.0, 20.0),
                (0.0, 0.0, 4.0, 30.0),
                (0.0, 0.0, 0.0, 1.0),
            ),
            voxel_sizes=(2.0, 3.0, 4.0, 1.0),
            axis_codes=("R", "A", "S"),
            units=("mm", "sec"),
        ),
    )
    widget = NiftiOrthogonalViewerWidget()
    widget.render_read_result(
        ReadResult(
            payload=payload,
            scope=OperationScope.SLICE,
            bytes_read=int(payload.values.nbytes),
            is_sampled=False,
            sample=None,
            warnings=("NIfTI values are scaled by the source proxy.",),
        )
    )
    widget.set_crosshair((1, 2, 3), volume_index=4)
    app.processEvents()

    assert widget.contract().kind is ViewKind.VOLUME
    assert widget.findChild(QLabel, "nifti_axial_label").text() == "axial: L->R / P->A @ S=3"
    assert widget.findChild(QLabel, "nifti_coronal_label").text() == "coronal: L->R / I->S @ A=2"
    assert widget.findChild(QLabel, "nifti_sagittal_label").text() == "sagittal: P->A / I->S @ R=1"
    assert widget.findChild(QLabel, "nifti_crosshair_label").text() == (
        "voxel: (1, 2, 3, 4) world: (12, 26, 42) value: 119 (scaled proxy; raw unavailable)"
    )
    assert widget.findChild(QLabel, "nifti_volume_index_label").text() == "volume/time index: 4 / 0..4"
    assert widget.findChild(QLabel, "nifti_resampling_label").text() == "resampling: none"


def test_nifti_orthogonal_viewer_exposes_window_level_and_affine_inspector() -> None:
    """NIfTI inspector exposes header/affine state without source resampling."""

    app = _qapp()
    selection = SelectionSpec.all().normalize((2, 3, 4)).unwrap()
    payload = VolumePayload(
        values=np.arange(24, dtype=np.int16).reshape(2, 3, 4),
        selection=selection,
        spatial=SpatialMetadata(
            affine=(
                (1.0, 0.0, 0.0, -1.0),
                (0.0, 2.0, 0.0, -2.0),
                (0.0, 0.0, 3.0, -3.0),
                (0.0, 0.0, 0.0, 1.0),
            ),
            voxel_sizes=(1.0, 2.0, 3.0),
            axis_codes=("L", "P", "I"),
            units=("mm", "unknown"),
        ),
    )
    widget = NiftiOrthogonalViewerWidget()
    widget.render_read_result(
        ReadResult(
            payload=payload,
            scope=OperationScope.SLICE,
            bytes_read=int(payload.values.nbytes),
            is_sampled=False,
            sample=None,
        )
    )
    widget.set_window_level(window=400.0, level=40.0)
    widget.set_crosshair((1, 1, 2), volume_index=0)
    app.processEvents()

    assert widget.findChild(QLabel, "nifti_window_level_label").text() == "window/level: 400 / 40"
    assert widget.findChild(QLabel, "nifti_crosshair_label").text() == (
        "voxel: (1, 1, 2) world: (0, 0, 3) value: 18 (display value; raw unavailable)"
    )
    inspector = widget.findChild(QPlainTextEdit, "nifti_header_inspector")
    assert inspector is not None
    text = inspector.toPlainText()
    assert "axis codes: L, P, I" in text
    assert "voxel sizes: 1, 2, 3" in text
    assert "affine:" in text
    assert "[1, 0, 0, -1]" in text


def test_base_view_contract_is_plugin_result_extensible() -> None:
    """Base view contracts expose stable result channels for later plugin renderers."""

    contract = BaseViewContract(
        kind=ViewKind.TABLE,
        result_channel="plugin.summary_table",
        supports_selection=True,
        supports_export=True,
    )

    assert contract.kind is ViewKind.TABLE
    assert contract.result_channel == "plugin.summary_table"
    assert contract.supports_selection
    assert contract.supports_export
