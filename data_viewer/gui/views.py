"""Base data view contracts and widgets for Data Viewer.

DV-0605 starts the reusable view layer without replacing every existing shell
path at once. The widgets here are intentionally bounded presentations over
already-bounded payloads; they do not read sources or infer active resources.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

import numpy as np
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from data_viewer.domain import (
    ArrayPayload,
    OperationScope,
    ReadResult,
    TablePayload,
    TextPayload,
)
from data_viewer.domain.selection import NormalizedSelection
from data_viewer.gui.i18n import Locale, UiStringKey, tr


class ViewKind(StrEnum):
    """Stable base view kinds for workspace tabs and plugin result routing."""

    TABLE = "table"
    ARRAY = "array"
    TEXT = "text"
    IMAGE = "image"


@dataclass(frozen=True, slots=True)
class BaseViewContract:
    """Public contract exposed by base workspace views."""

    kind: ViewKind
    result_channel: str
    supports_selection: bool
    supports_export: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", ViewKind(self.kind))
        if not self.result_channel:
            raise ValueError("view result channel must not be empty")


class _PayloadTableModel(QAbstractTableModel):
    """Virtual Qt table model over array or table payloads."""

    def __init__(self) -> None:
        super().__init__()
        self._payload: TablePayload | ArrayPayload | None = None
        self._column_headers: list[str] = []

    def set_payload(self, payload: TablePayload | ArrayPayload) -> None:
        self.beginResetModel()
        self._payload = payload
        if isinstance(payload, TablePayload):
            self._column_headers = [column.name for column in payload.columns]
        else:
            values = np.asarray(payload.values)
            if values.ndim == 0:
                self._column_headers = ["value"]
            elif values.ndim == 1:
                self._column_headers = ["value"]
            else:
                self._column_headers = [f"C{column}" for column in range(values.shape[1])]
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid() or self._payload is None:
            return 0
        if isinstance(self._payload, TablePayload):
            return self._payload.row_count
        values = np.asarray(self._payload.values)
        if values.ndim == 0:
            return 1
        if values.ndim == 1:
            return values.shape[0]
        return values.shape[0]

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid() or self._payload is None:
            return 0
        return len(self._column_headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole or self._payload is None or not index.isValid():
            return None
        row = index.row()
        column = index.column()
        if isinstance(self._payload, TablePayload):
            if not (0 <= column < len(self._payload.column_values)):
                return None
            return _format_cell(self._payload.column_values[column][row])
        values = np.asarray(self._payload.values)
        if values.ndim == 0:
            return _format_cell(values.item())
        if values.ndim == 1:
            return _format_cell(values[row])
        return _format_cell(values[row, column])

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole or self._payload is None:
            return None
        if orientation is Qt.Orientation.Horizontal:
            if 0 <= section < len(self._column_headers):
                return self._column_headers[section]
            return None
        if isinstance(self._payload, TablePayload):
            return str(self._payload.source_row(section))
        if isinstance(self._payload, ArrayPayload):
            values = np.asarray(self._payload.values)
            if values.ndim == 0:
                return str(self._payload.source_coordinates(()))
            if values.ndim == 1:
                return str(self._payload.source_coordinates((section,)))
            return str(self._payload.source_coordinates((section, 0)))
        return None


class _BaseDataView(QWidget):
    """Common labels for scope/provenance visible in every base view."""

    def __init__(self, contract: BaseViewContract, *, locale: Locale = Locale.EN_US) -> None:
        super().__init__()
        self._contract = contract
        self._locale = Locale(locale)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._scope_label = QLabel(tr(UiStringKey.VIEW_SCOPE_EMPTY, self._locale), self)
        self._scope_label.setObjectName("view_scope_label")
        self._coordinates_label = QLabel(
            tr(UiStringKey.VIEW_COORDINATES_EMPTY, self._locale),
            self,
        )
        self._coordinates_label.setObjectName("view_coordinates_label")
        self._shape_label = QLabel(tr(UiStringKey.VIEW_SHAPE_EMPTY, self._locale), self)
        self._shape_label.setObjectName("view_shape_label")
        self._slice_label = QLabel(tr(UiStringKey.VIEW_SLICE_EMPTY, self._locale), self)
        self._slice_label.setObjectName("view_slice_label")
        for label in (
            self._scope_label,
            self._coordinates_label,
            self._shape_label,
            self._slice_label,
        ):
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        header_layout.addWidget(self._scope_label)
        header_layout.addWidget(self._coordinates_label)
        header_layout.addWidget(self._shape_label)
        header_layout.addWidget(self._slice_label)
        header_layout.addStretch(1)
        self._layout.addWidget(header)

    def contract(self) -> BaseViewContract:
        """Return the stable view contract."""

        return self._contract

    def _set_scope(self, result: ReadResult) -> None:
        self._scope_label.setText(
            tr(
                UiStringKey.VIEW_SCOPE_VALUE,
                self._locale,
                scope=OperationScope(result.scope).value,
            )
        )


class TableViewWidget(_BaseDataView):
    """Virtual table/page view using source rows as headers."""

    def __init__(self, *, locale: Locale = Locale.EN_US) -> None:
        super().__init__(
            BaseViewContract(
                kind=ViewKind.TABLE,
                result_channel="workspace.table",
                supports_selection=True,
                supports_export=True,
            ),
            locale=locale,
        )
        self._model = _PayloadTableModel()
        self._table = QTableView(self)
        self._table.setObjectName("table_view")
        self._table.setAccessibleName("Virtual table view")
        self._table.setModel(self._model)
        self._layout.addWidget(self._table, 1)

    def render_read_result(self, result: ReadResult) -> None:
        if not isinstance(result.payload, TablePayload):
            raise TypeError("TableViewWidget requires TablePayload")
        payload = result.payload
        self._set_scope(result)
        row_stop = payload.row_offset + payload.row_count
        self._coordinates_label.setText(f"rows: {payload.row_offset}:{row_stop}")
        self._shape_label.setText(f"shape: ({payload.total_rows or '?'}, {len(payload.columns)})")
        self._slice_label.setText("slice: table page")
        self._model.set_payload(payload)


class ArrayViewWidget(_BaseDataView):
    """Array view that renders only explicit bounded projections."""

    def __init__(self, *, locale: Locale = Locale.EN_US) -> None:
        super().__init__(
            BaseViewContract(
                kind=ViewKind.ARRAY,
                result_channel="workspace.array",
                supports_selection=True,
                supports_export=True,
            ),
            locale=locale,
        )
        self._model = _PayloadTableModel()
        self._table = QTableView(self)
        self._table.setObjectName("array_view")
        self._table.setAccessibleName("Array slice view")
        self._table.setModel(self._model)
        self._layout.addWidget(self._table, 1)

    def render_read_result(self, result: ReadResult) -> None:
        if not isinstance(result.payload, ArrayPayload):
            raise TypeError("ArrayViewWidget requires ArrayPayload")
        payload = result.payload
        values = np.asarray(payload.values)
        if values.ndim > 2:
            raise ValueError("array view requires an explicit 0D, 1D, or 2D projection")
        selection = cast(NormalizedSelection, payload.selection)
        self._set_scope(result)
        self._coordinates_label.setText(f"coordinates: {_selection_coordinates(selection)}")
        self._shape_label.setText(f"shape: {payload.original_shape} -> {values.shape}")
        self._slice_label.setText(f"slice: {_format_selection(selection)}")
        self._model.set_payload(payload)


class TextViewWidget(_BaseDataView):
    """Paged/streamed text view with explicit partial banner."""

    def __init__(self, *, locale: Locale = Locale.EN_US) -> None:
        super().__init__(
            BaseViewContract(
                kind=ViewKind.TEXT,
                result_channel="workspace.text",
                supports_selection=True,
                supports_export=True,
            ),
            locale=locale,
        )
        self._partial_banner = QLabel("", self)
        self._partial_banner.setObjectName("text_partial_banner")
        self._partial_banner.setAccessibleName("Text partial view banner")
        self._partial_banner.setVisible(False)
        self._editor = QPlainTextEdit(self)
        self._editor.setObjectName("text_view")
        self._editor.setAccessibleName("Text preview")
        self._editor.setReadOnly(True)
        self._layout.addWidget(self._partial_banner)
        self._layout.addWidget(self._editor, 1)

    def render_read_result(self, result: ReadResult) -> None:
        if not isinstance(result.payload, TextPayload):
            raise TypeError("TextViewWidget requires TextPayload")
        payload = result.payload
        self._set_scope(result)
        stop = payload.offset + len(payload.text)
        self._coordinates_label.setText(f"chars: offset {payload.offset}:{stop}")
        self._shape_label.setText(f"shape: {len(payload.text)} chars")
        self._slice_label.setText("slice: text page")
        self._editor.setPlainText(payload.text)
        if payload.is_complete:
            self._partial_banner.setVisible(False)
            self._partial_banner.setText("")
        else:
            self._partial_banner.setText(
                "Partial text preview: refine the page or load more to inspect additional text."
            )
            self._partial_banner.setVisible(True)


class ImageViewWidget(_BaseDataView):
    """Image-like array view preserving aspect and cursor provenance."""

    def __init__(self, *, locale: Locale = Locale.EN_US) -> None:
        super().__init__(
            BaseViewContract(
                kind=ViewKind.IMAGE,
                result_channel="workspace.image",
                supports_selection=True,
                supports_export=True,
            ),
            locale=locale,
        )
        self._payload: ArrayPayload | None = None
        self._image_label = QLabel("Image preview", self)
        self._image_label.setObjectName("image_view")
        self._image_label.setAccessibleName("Image preview")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._aspect_label = QLabel("aspect: preserved", self)
        self._aspect_label.setObjectName("image_aspect_label")
        self._zoom_label = QLabel("zoom: 100%", self)
        self._zoom_label.setObjectName("image_zoom_label")
        self._interpolation_label = QLabel("interpolation: nearest", self)
        self._interpolation_label.setObjectName("image_interpolation_label")
        self._cursor_label = QLabel("cursor: -", self)
        self._cursor_label.setObjectName("image_cursor_label")
        controls = QWidget(self)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        controls_layout.addWidget(self._aspect_label)
        controls_layout.addWidget(self._zoom_label)
        controls_layout.addWidget(self._interpolation_label)
        controls_layout.addWidget(self._cursor_label)
        controls_layout.addStretch(1)
        self._layout.addWidget(controls)
        self._layout.addWidget(self._image_label, 1)

    def render_read_result(self, result: ReadResult) -> None:
        if not isinstance(result.payload, ArrayPayload):
            raise TypeError("ImageViewWidget requires ArrayPayload")
        payload = result.payload
        values = np.asarray(payload.values)
        if values.ndim != 2:
            raise ValueError("image view requires a 2D array projection")
        self._payload = payload
        selection = cast(NormalizedSelection, payload.selection)
        self._set_scope(result)
        self._coordinates_label.setText(f"coordinates: {_selection_coordinates(selection)}")
        self._shape_label.setText(f"shape: {payload.original_shape} -> {values.shape}")
        self._slice_label.setText(f"slice: {_format_selection(selection)}")
        self._image_label.setText(f"{values.shape[0]} x {values.shape[1]} image projection")
        self._cursor_label.setText("cursor: -")

    def set_cursor_display_index(self, display_index: tuple[int, int]) -> None:
        """Update cursor label with display and original source coordinates."""

        if self._payload is None:
            self._cursor_label.setText("cursor: -")
            return
        values = np.asarray(self._payload.values)
        row, column = display_index
        value = values[row, column]
        source = self._payload.source_coordinates(display_index)
        self._cursor_label.setText(
            f"cursor: display {display_index} source {source} value {_format_cell(value)}"
        )


def _format_cell(value: Any) -> str:
    if isinstance(value, np.ndarray):
        if value.shape == ():
            value = value.item()
        else:
            return repr(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    if isinstance(value, np.generic):
        return str(value.item())
    return str(value)


def _format_selection(selection: NormalizedSelection) -> str:
    parts: list[str] = []
    for axis in selection.axes:
        if axis.kind.value == "index":
            parts.append(f"[{axis.axis}:{axis.index}]")
        else:
            parts.append(f"[{axis.axis}:{axis.start}:{axis.stop}:{axis.step}]")
    return " ".join(parts) if parts else "full"


def _selection_coordinates(selection: NormalizedSelection) -> str:
    return f"original {selection.original_shape} result {selection.result_shape}"


__all__ = [
    "ArrayViewWidget",
    "BaseViewContract",
    "ImageViewWidget",
    "TableViewWidget",
    "TextViewWidget",
    "ViewKind",
]
