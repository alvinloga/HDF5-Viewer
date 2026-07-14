"""Contracts for DV-0605 base data view widgets."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QPlainTextEdit, QTableView

from data_viewer.domain import (
    ArrayPayload,
    AxisSelection,
    ColumnSpec,
    OperationScope,
    ReadResult,
    SelectionSpec,
    TablePayload,
    TextPayload,
)
from data_viewer.gui.views import (
    ArrayViewWidget,
    BaseViewContract,
    ImageViewWidget,
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
