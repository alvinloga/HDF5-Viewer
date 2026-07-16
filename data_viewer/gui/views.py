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
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSpinBox,
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
    VolumePayload,
)
from data_viewer.domain.selection import NormalizedAxisSelection, NormalizedSelection
from data_viewer.gui.i18n import Locale, UiStringKey, tr


class ViewKind(StrEnum):
    """Stable base view kinds for workspace tabs and plugin result routing."""

    TABLE = "table"
    ARRAY = "array"
    TEXT = "text"
    IMAGE = "image"
    VOLUME = "volume"


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

    def rowCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
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

    def columnCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
        if parent.isValid() or self._payload is None:
            return 0
        return len(self._column_headers)

    def data(  # noqa: N802
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
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


class MultidimensionalSliceNavigatorWidget(ImageViewWidget):
    """Image projection view with explicit high-dimensional slice controls."""

    def __init__(self, *, locale: Locale = Locale.EN_US) -> None:
        super().__init__(locale=locale)
        self._selection: NormalizedSelection | None = None
        self._axis_index_overrides: dict[int, int] = {}
        self._display_mode = "raw"
        self._linked_slices = False
        self._mode_label = QLabel("mode: raw", self)
        self._mode_label.setObjectName("slice_navigator_mode_label")
        self._mode_label.setAccessibleName("Slice navigator display mode")
        self._linked_label = QLabel("linked slices: off", self)
        self._linked_label.setObjectName("slice_navigator_linked_label")
        self._linked_label.setAccessibleName("Linked slice state")
        self._bounds_label = QLabel("bounded read: -", self)
        self._bounds_label.setObjectName("slice_navigator_bounds_label")
        self._bounds_label.setAccessibleName("Slice read bounds")
        self._axis_summary_label = QLabel("axes: -", self)
        self._axis_summary_label.setObjectName("slice_navigator_axis_summary_label")
        self._axis_summary_label.setAccessibleName("Slice axis summary")
        self._axis_summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._axis_controls = QWidget(self)
        self._axis_controls.setObjectName("slice_navigator_axis_controls")
        self._axis_controls.setAccessibleName("Slice navigator axis controls")
        self._axis_controls_layout = QHBoxLayout(self._axis_controls)
        self._axis_controls_layout.setContentsMargins(0, 0, 0, 0)
        self._axis_controls_layout.setSpacing(8)

        navigator_header = QWidget(self)
        navigator_layout = QHBoxLayout(navigator_header)
        navigator_layout.setContentsMargins(0, 0, 0, 0)
        navigator_layout.setSpacing(8)
        navigator_layout.addWidget(self._mode_label)
        navigator_layout.addWidget(self._linked_label)
        navigator_layout.addWidget(self._bounds_label)
        navigator_layout.addStretch(1)
        self._layout.insertWidget(1, navigator_header)
        self._layout.insertWidget(2, self._axis_summary_label)
        self._layout.insertWidget(3, self._axis_controls)

    def render_read_result(self, result: ReadResult) -> None:
        super().render_read_result(result)
        payload = cast(ArrayPayload, result.payload)
        selection = cast(NormalizedSelection, payload.selection)
        self._selection = selection
        self._axis_index_overrides = {
            axis.axis: axis.index
            for axis in selection.axes
            if axis.kind.value == "index" and axis.index is not None
        }
        self._bounds_label.setText(
            f"bounded read: {OperationScope(result.scope).value}, {result.bytes_read} bytes"
        )
        self._refresh_axis_summary()
        self._rebuild_axis_controls()

    def set_display_mode(self, mode: str) -> None:
        """Set raw/display presentation mode without mutating source data."""

        normalized = mode.strip().lower()
        if normalized not in {"raw", "display"}:
            raise ValueError("display mode must be 'raw' or 'display'")
        self._display_mode = normalized
        self._mode_label.setText(f"mode: {self._display_mode}")

    def set_linked_slices(self, enabled: bool) -> None:
        """Expose whether cursor/slice changes are linked to sibling views."""

        if not isinstance(enabled, bool):
            raise ValueError("linked slices state must be boolean")
        self._linked_slices = enabled
        state = "on" if enabled else "off"
        self._linked_label.setText(f"linked slices: {state}")

    def set_axis_index(self, *, axis: int, index: int) -> None:
        """Record a requested fixed-axis index for the next bounded slice read."""

        if self._selection is None:
            raise ValueError("slice navigator has no rendered selection")
        if isinstance(axis, bool) or not isinstance(axis, int):
            raise ValueError("axis must be an integer")
        if isinstance(index, bool) or not isinstance(index, int):
            raise ValueError("index must be an integer")
        if axis < 0 or axis >= len(self._selection.original_shape):
            raise ValueError("axis is out of bounds")
        dimension = self._selection.original_shape[axis]
        if index < 0 or index >= dimension:
            raise ValueError("index is out of bounds")
        self._axis_index_overrides[axis] = index
        self._refresh_axis_summary()
        spin_box = self.findChild(QSpinBox, f"slice_axis_{axis}_index")
        if spin_box is not None and spin_box.value() != index:
            spin_box.setValue(index)

    def _rebuild_axis_controls(self) -> None:
        while self._axis_controls_layout.count():
            item = self._axis_controls_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if self._selection is None:
            self._axis_controls_layout.addWidget(QLabel("axes: -", self._axis_controls))
            return
        for axis in self._selection.axes:
            if axis.kind.value == "index":
                spin_box = QSpinBox(self._axis_controls)
                spin_box.setObjectName(f"slice_axis_{axis.axis}_index")
                spin_box.setAccessibleName(f"Slice axis {axis.axis} fixed index")
                spin_box.setRange(0, self._selection.original_shape[axis.axis] - 1)
                spin_box.setValue(self._axis_index_overrides.get(axis.axis, axis.index or 0))
                spin_box.valueChanged.connect(
                    lambda value, axis_number=axis.axis: self.set_axis_index(
                        axis=axis_number,
                        index=int(value),
                    )
                )
                self._axis_controls_layout.addWidget(QLabel(f"axis {axis.axis}", self._axis_controls))
                self._axis_controls_layout.addWidget(spin_box)
            else:
                label = QLabel(_describe_slice_axis(axis, self._display_axis_role(axis)), self._axis_controls)
                label.setObjectName(f"slice_axis_{axis.axis}_label")
                self._axis_controls_layout.addWidget(label)
        self._axis_controls_layout.addStretch(1)

    def _refresh_axis_summary(self) -> None:
        if self._selection is None:
            self._axis_summary_label.setText("axes: -")
            return
        parts: list[str] = []
        for axis in self._selection.axes:
            if axis.kind.value == "index":
                index = self._axis_index_overrides.get(axis.axis, axis.index or 0)
                maximum = self._selection.original_shape[axis.axis] - 1
                parts.append(f"axis {axis.axis}: index {index} / 0..{maximum}")
            else:
                parts.append(_describe_slice_axis(axis, self._display_axis_role(axis)))
        self._axis_summary_label.setText("axes: " + "; ".join(parts))

    def _display_axis_role(self, axis: NormalizedAxisSelection) -> str:
        if self._selection is None:
            return "display axis"
        display_axes = [
            selection_axis.axis
            for selection_axis in self._selection.axes
            if selection_axis.contributes_display_axis
        ]
        position = display_axes.index(axis.axis)
        if position == 0:
            return "display row"
        if position == 1:
            return "display column"
        return f"display axis {position}"


class NiftiOrthogonalViewerWidget(_BaseDataView):
    """NIfTI orthogonal volume view over an already-bounded VolumePayload."""

    def __init__(self, *, locale: Locale = Locale.EN_US) -> None:
        super().__init__(
            BaseViewContract(
                kind=ViewKind.VOLUME,
                result_channel="workspace.volume",
                supports_selection=True,
                supports_export=True,
            ),
            locale=locale,
        )
        self._payload: VolumePayload | None = None
        self._warnings: tuple[str, ...] = ()
        self._axial_label = QLabel("axial: -", self)
        self._axial_label.setObjectName("nifti_axial_label")
        self._coronal_label = QLabel("coronal: -", self)
        self._coronal_label.setObjectName("nifti_coronal_label")
        self._sagittal_label = QLabel("sagittal: -", self)
        self._sagittal_label.setObjectName("nifti_sagittal_label")
        self._crosshair_label = QLabel("voxel: -", self)
        self._crosshair_label.setObjectName("nifti_crosshair_label")
        self._volume_index_label = QLabel("volume/time index: -", self)
        self._volume_index_label.setObjectName("nifti_volume_index_label")
        self._window_level_label = QLabel("window/level: auto", self)
        self._window_level_label.setObjectName("nifti_window_level_label")
        self._resampling_label = QLabel("resampling: none", self)
        self._resampling_label.setObjectName("nifti_resampling_label")
        for label in (
            self._axial_label,
            self._coronal_label,
            self._sagittal_label,
            self._crosshair_label,
            self._volume_index_label,
            self._window_level_label,
            self._resampling_label,
        ):
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._layout.addWidget(label)
        self._inspector = QPlainTextEdit(self)
        self._inspector.setObjectName("nifti_header_inspector")
        self._inspector.setAccessibleName("NIfTI header and affine inspector")
        self._inspector.setReadOnly(True)
        self._layout.addWidget(self._inspector, 1)

    def render_read_result(self, result: ReadResult) -> None:
        if not isinstance(result.payload, VolumePayload):
            raise TypeError("NiftiOrthogonalViewerWidget requires VolumePayload")
        payload = result.payload
        values = np.asarray(payload.values)
        if values.ndim not in {3, 4}:
            raise ValueError("NIfTI orthogonal viewer requires a 3D or 4D volume payload")
        self._payload = payload
        self._warnings = tuple(result.warnings)
        selection = cast(NormalizedSelection, payload.selection)
        self._set_scope(result)
        self._coordinates_label.setText(f"coordinates: {_selection_coordinates(selection)}")
        self._shape_label.setText(f"shape: {selection.original_shape} -> {values.shape}")
        self._slice_label.setText(f"slice: {_format_selection(selection)}")
        self._resampling_label.setText("resampling: none")
        self._update_plane_labels((0, 0, 0))
        self._update_volume_index(0)
        self._crosshair_label.setText("voxel: -")
        self._inspector.setPlainText(_nifti_inspector_text(payload))

    def set_crosshair(self, voxel: tuple[int, int, int], *, volume_index: int = 0) -> None:
        """Update linked orthogonal crosshairs and voxel/world/value labels."""

        if self._payload is None:
            self._crosshair_label.setText("voxel: -")
            return
        values = np.asarray(self._payload.values)
        x, y, z = voxel
        _validate_index(x, values.shape[0], "x")
        _validate_index(y, values.shape[1], "y")
        _validate_index(z, values.shape[2], "z")
        if values.ndim == 4:
            _validate_index(volume_index, values.shape[3], "volume index")
            source = self._payload.source_coordinates((x, y, z, volume_index))
            value = values[x, y, z, volume_index]
        else:
            source = self._payload.source_coordinates((x, y, z))
            value = values[x, y, z]
        source_voxel = (int(source[0]), int(source[1]), int(source[2]))
        world = _voxel_to_world(self._payload, source_voxel)
        self._update_plane_labels(source_voxel)
        self._update_volume_index(volume_index)
        self._crosshair_label.setText(
            f"voxel: {source} world: {_format_tuple(world)} "
            f"value: {_format_display_value(value)} ({_nifti_value_semantics(self._warnings)})"
        )

    def set_window_level(self, *, window: float, level: float) -> None:
        """Expose display-only window/level without modifying source values."""

        if window <= 0:
            raise ValueError("window must be positive")
        self._window_level_label.setText(
            f"window/level: {_format_number(window)} / {_format_number(level)}"
        )

    def _update_plane_labels(self, voxel: tuple[int, int, int]) -> None:
        if self._payload is None:
            return
        codes = self._payload.spatial.axis_codes
        x_label, y_label, z_label = (_orientation_axis_label(code) for code in codes[:3])
        self._axial_label.setText(f"axial: {x_label} / {y_label} @ {codes[2]}={voxel[2]}")
        self._coronal_label.setText(f"coronal: {x_label} / {z_label} @ {codes[1]}={voxel[1]}")
        self._sagittal_label.setText(f"sagittal: {y_label} / {z_label} @ {codes[0]}={voxel[0]}")

    def _update_volume_index(self, volume_index: int) -> None:
        if self._payload is None:
            self._volume_index_label.setText("volume/time index: -")
            return
        values = np.asarray(self._payload.values)
        if values.ndim == 4:
            self._volume_index_label.setText(
                f"volume/time index: {volume_index} / 0..{values.shape[3] - 1}"
            )
        else:
            self._volume_index_label.setText("volume/time index: n/a")


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


def _describe_slice_axis(axis: NormalizedAxisSelection, role: str) -> str:
    return f"axis {axis.axis}: {role} [{axis.start}:{axis.stop}:{axis.step}]"


def _orientation_axis_label(code: str) -> str:
    return {
        "R": "L->R",
        "L": "R->L",
        "A": "P->A",
        "P": "A->P",
        "S": "I->S",
        "I": "S->I",
    }.get(code, f"?->{code}")


def _voxel_to_world(payload: VolumePayload, voxel: tuple[int, int, int]) -> tuple[float, float, float]:
    affine = np.asarray(payload.spatial.affine, dtype=np.float64)
    vector = np.array([voxel[0], voxel[1], voxel[2], 1.0], dtype=np.float64)
    world = affine @ vector
    return (float(world[0]), float(world[1]), float(world[2]))


def _nifti_value_semantics(warnings: tuple[str, ...]) -> str:
    if any("scaled" in warning.lower() for warning in warnings):
        return "scaled proxy; raw unavailable"
    return "display value; raw unavailable"


def _nifti_inspector_text(payload: VolumePayload) -> str:
    spatial = payload.spatial
    affine_rows = "\n".join(
        f"  [{', '.join(_format_number(value) for value in row)}]"
        for row in spatial.affine
    )
    return "\n".join(
        (
            f"axis codes: {', '.join(spatial.axis_codes)}",
            f"voxel sizes: {', '.join(_format_number(value) for value in spatial.voxel_sizes)}",
            f"units: {', '.join(spatial.units)}",
            "affine:",
            affine_rows,
        )
    )


def _format_tuple(values: tuple[float, ...]) -> str:
    return f"({', '.join(_format_number(value) for value in values)})"


def _format_display_value(value: Any) -> str:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, int | float) and not isinstance(value, bool):
        return _format_number(float(value))
    return _format_cell(value)


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.6g}"


def _validate_index(value: int, size: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} index must be an integer")
    if value < 0 or value >= size:
        raise ValueError(f"{label} index is out of bounds")


__all__ = [
    "ArrayViewWidget",
    "BaseViewContract",
    "ImageViewWidget",
    "MultidimensionalSliceNavigatorWidget",
    "NiftiOrthogonalViewerWidget",
    "TableViewWidget",
    "TextViewWidget",
    "ViewKind",
]
