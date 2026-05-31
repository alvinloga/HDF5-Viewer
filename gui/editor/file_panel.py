"""FilePanel — 单文件面板（异步加载 + 数据量限制）"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                              QLabel, QLineEdit, QPushButton, QComboBox,
                              QSpinBox, QCheckBox, QGroupBox, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
import threading
import numpy as np

from core.datasource import DataSource, DataMeta, NodeType
from core.slicer import SliceParser
from core.event_bus import EventBus
from .data_table import DataTablePanel
from .data_editor import DataEditorBar


class DataLoadThread(QThread):
    """数据加载线程"""

    finished = pyqtSignal(object)  # np.ndarray or None
    error = pyqtSignal(str)

    def __init__(self, source: DataSource, path: str, slices: tuple, parent=None):
        super().__init__(parent)
        self._source = source
        self._path = path
        self._slices = slices

    def run(self):
        try:
            with FilePanel._h5_lock:
                data = self._source.read_slice(self._path, self._slices)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class SliceInput(QWidget):
    """增强的切片输入控件"""

    slice_changed = pyqtSignal(str)  # slice_str

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shape = ()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # 手动输入行
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        label = QLabel("Slice:")
        label.setStyleSheet("color: #cccccc; font-size: 12px;")
        input_row.addWidget(label)

        self.input = QLineEdit()
        self.input.setPlaceholderText("[0:100, :]")
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                padding: 4px 8px;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
                border-radius: 2px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        self.input.returnPressed.connect(self._on_apply_manual)
        input_row.addWidget(self.input)

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 4px 12px;
                font-size: 12px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        self.apply_btn.clicked.connect(self._on_apply_manual)
        input_row.addWidget(self.apply_btn)

        layout.addLayout(input_row)

        # 快捷切片按钮行
        quick_row = QHBoxLayout()
        quick_row.setSpacing(4)

        self.first_btn = QPushButton("First 100")
        self.first_btn.setToolTip("Show first 100 rows")
        self.first_btn.clicked.connect(lambda: self._apply_quick_slice("first"))
        quick_row.addWidget(self.first_btn)

        self.last_btn = QPushButton("Last 100")
        self.last_btn.setToolTip("Show last 100 rows")
        self.last_btn.clicked.connect(lambda: self._apply_quick_slice("last"))
        quick_row.addWidget(self.last_btn)

        self.all_btn = QPushButton("All")
        self.all_btn.setToolTip("Show all data (careful with large datasets)")
        self.all_btn.clicked.connect(lambda: self._apply_quick_slice("all"))
        quick_row.addWidget(self.all_btn)

        quick_row.addStretch()

        # 维度选择器（用于高维数据）
        self.dim_combo = QComboBox()
        self.dim_combo.setStyleSheet("""
            QComboBox {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                padding: 2px 8px;
                font-size: 11px;
            }
        """)
        self.dim_combo.currentIndexChanged.connect(self._on_dim_changed)
        quick_row.addWidget(QLabel("View dim:"))
        quick_row.addWidget(self.dim_combo)

        layout.addLayout(quick_row)

        # 按钮样式
        btn_style = """
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                padding: 2px 8px;
                font-size: 11px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """
        self.first_btn.setStyleSheet(btn_style)
        self.last_btn.setStyleSheet(btn_style)
        self.all_btn.setStyleSheet(btn_style)

    def set_shape_hint(self, shape: tuple) -> None:
        """设置形状提示"""
        self._shape = shape
        if shape:
            self.input.setPlaceholderText(f"[0:100, :]  shape={shape}")

            # 更新维度选择器
            self.dim_combo.blockSignals(True)
            self.dim_combo.clear()
            if len(shape) > 2:
                self.dim_combo.addItem("Auto")
                for i in range(len(shape)):
                    self.dim_combo.addItem(f"Slice dim {i} (size={shape[i]})")
                self.dim_combo.setCurrentIndex(0)
                self.dim_combo.show()
            else:
                self.dim_combo.hide()
            self.dim_combo.blockSignals(False)

    def _on_apply_manual(self) -> None:
        """应用手动输入的切片"""
        slice_str = self.input.text().strip()
        if slice_str:
            self.slice_changed.emit(slice_str)

    def _apply_quick_slice(self, mode: str) -> None:
        """应用快捷切片"""
        if not self._shape:
            return

        if mode == "first":
            slices = f"[0:100, :]" if len(self._shape) >= 2 else "[0:100]"
        elif mode == "last":
            last = self._shape[0]
            slices = f"[{max(0, last-100)}:{last}, :]" if len(self._shape) >= 2 else f"[{max(0, last-100)}:{last}]"
        elif mode == "all":
            slices = "[:, :]" if len(self._shape) >= 2 else "[:]"
        else:
            return

        self.input.setText(slices)
        self.slice_changed.emit(slices)

    def _on_dim_changed(self, index: int) -> None:
        """维度选择改变"""
        if index == 0 or not self._shape:
            return

        dim_idx = index - 1
        if dim_idx < len(self._shape):
            size = self._shape[dim_idx]
            parts = [":" for _ in self._shape]
            parts[dim_idx] = f"0:{min(100, size)}"
            slice_str = f"[{', '.join(parts)}]"
            self.input.setText(slice_str)
            self.slice_changed.emit(slice_str)


class FilePanel(QWidget):
    """单文件面板"""

    _h5_lock = threading.Lock()  # 全局锁，保护 h5py 访问

    def __init__(self, source: DataSource, parent=None):
        super().__init__(parent)
        self._source = source
        self._current_path = ""
        self._current_meta: DataMeta | None = None
        self._event_bus = EventBus.get_instance()
        self._load_thread: DataLoadThread | None = None

        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 加载状态标签
        self._loading_label = QLabel("Loading...")
        self._loading_label.setStyleSheet("""
            QLabel {
                background-color: #0e639c;
                color: white;
                padding: 8px;
                font-weight: bold;
            }
        """)
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.hide()
        layout.addWidget(self._loading_label)

        # 切片输入
        self.slice_input = SliceInput(self)
        self.slice_input.slice_changed.connect(self._on_slice_changed)
        layout.addWidget(self.slice_input)

        # 数据编辑工具栏（在切片输入和数据表格之间）
        self.editor_bar = DataEditorBar(self)
        self.editor_bar.hide()  # 默认隐藏，只在 View 菜单中启用
        self.editor_bar.edit_enabled.connect(self._on_edit_enabled)
        self.editor_bar.save_requested.connect(self._on_save_requested)
        layout.addWidget(self.editor_bar)

        # 数据表格
        self.data_table = DataTablePanel(self)
        layout.addWidget(self.data_table)

    def show_dataset(self, path: str, meta: DataMeta) -> None:
        """显示数据集"""
        self._current_path = path
        self._current_meta = meta

        if meta and meta.shape:
            self.slice_input.set_shape_hint(meta.shape)

        self._load_default_slice()

    def _load_default_slice(self) -> None:
        """加载默认切片"""
        if not self._current_path or not self._current_meta:
            return

        if self._current_meta.node_type != NodeType.DATASET:
            return

        shape = self._current_meta.shape
        if not shape:
            return

        slices = SliceParser.default_slice(shape)
        self._load_data_async(slices)

    def _on_slice_changed(self, slice_str: str) -> None:
        """切片改变"""
        if not self._current_path or not self._current_meta:
            return

        try:
            slices = SliceParser.parse(slice_str, self._current_meta.shape)
            self._load_data_async(slices)
        except Exception as e:
            self._event_bus.emit(EventBus.ERROR_OCCURRED, str(e))

    def _on_edit_enabled(self, enabled: bool) -> None:
        """编辑模式切换"""
        self.data_table.set_editable(enabled)

    def _on_save_requested(self) -> None:
        """保存编辑后的数据回文件"""
        if not self._current_path or not self._source:
            return

        try:
            edited_data = self.data_table.get_edited_data()
            if edited_data is None:
                self._event_bus.emit(EventBus.ERROR_OCCURRED, "No data to save")
                return

            self._source.write_data(self._current_path, edited_data)
            self._event_bus.emit(EventBus.STATUS_MESSAGE, f"Saved: {self._current_path}")
        except Exception as e:
            self._event_bus.emit(EventBus.ERROR_OCCURRED, f"Save failed: {e}")

    def _load_data_async(self, slices: tuple) -> None:
        """异步加载数据"""
        if not self._current_path:
            return

        # 如果有正在运行的加载线程，先停止
        if self._load_thread and self._load_thread.isRunning():
            self._load_thread.terminate()
            self._load_thread.wait()

        # 显示加载状态
        self._loading_label.show()
        self._loading_label.setText(f"Loading {self._current_path}...")
        self.data_table.setEnabled(False)

        # 创建并启动加载线程
        self._load_thread = DataLoadThread(
            self._source, self._current_path, slices, self
        )
        self._load_thread.finished.connect(self._on_load_finished)
        self._load_thread.error.connect(self._on_load_error)
        self._load_thread.start()

    @pyqtSlot(object)
    def _on_load_finished(self, data: np.ndarray) -> None:
        """加载完成"""
        self._loading_label.hide()
        self.data_table.setEnabled(True)

        if data is not None:
            # 大数据量保护：截断显示以避免 UI 卡死
            MAX_ELEMENTS = 1_000_000
            if data.size > MAX_ELEMENTS:
                if data.ndim >= 2:
                    max_rows = MAX_ELEMENTS // data.shape[1] if data.shape[1] > 0 else MAX_ELEMENTS
                    max_rows = max(1, min(max_rows, data.shape[0]))
                    data = data[:max_rows]
                elif data.ndim == 1:
                    data = data[:MAX_ELEMENTS]

                self._event_bus.emit(
                    EventBus.STATUS_MESSAGE,
                    f"Loaded {self._current_path} (truncated to {data.shape}, "
                    f"full shape available in slice input)"
                )

            self.data_table.load_data(data)

    @pyqtSlot(str)
    def _on_load_error(self, error: str) -> None:
        """加载错误"""
        self._loading_label.hide()
        self.data_table.setEnabled(True)
        self._event_bus.emit(EventBus.ERROR_OCCURRED, error)

    def get_source(self) -> DataSource:
        """获取数据源"""
        return self._source

    def get_path(self) -> str:
        """获取文件路径"""
        return self._source.get_path()

    def get_current_node(self) -> str:
        """获取当前选中的节点"""
        return self._current_path

    def closeEvent(self, event):
        """关闭时清理线程"""
        if self._load_thread and self._load_thread.isRunning():
            self._load_thread.terminate()
            self._load_thread.wait()
        super().closeEvent(event)
