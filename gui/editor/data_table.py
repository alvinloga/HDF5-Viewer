"""DataTable — 数据表格视图（优化版：虚拟模型 + 分页）"""

from PyQt6.QtWidgets import (QTableView, QWidget, QVBoxLayout, QHeaderView,
                              QAbstractItemView, QLabel, QHBoxLayout, QPushButton)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal
import numpy as np


class DataTableModel(QAbstractTableModel):
    """虚拟表格模型 — 只在需要时渲染数据"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: np.ndarray | None = None
        self._headers: list[str] = []
        self._row_start = 0

    def rowCount(self, parent=QModelIndex()) -> int:
        if self._data is None:
            return 0
        return self._data.shape[0]

    def columnCount(self, parent=QModelIndex()) -> int:
        if self._data is None:
            return 0
        return self._data.shape[1] if self._data.ndim >= 2 else 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self._data is None:
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            row = index.row()
            col = index.column()

            try:
                if self._data.ndim == 1:
                    val = self._data[row]
                else:
                    val = self._data[row, col]
                return self._format_value(val)
            except:
                return ""

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        return None

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if section < len(self._headers):
                    return self._headers[section]
                return f"Col {section}"
            else:
                return str(self._row_start + section)
        return None

    def load_data(self, data: np.ndarray, row_start: int = 0) -> None:
        """加载数据"""
        self.beginResetModel()

        if data is None or data.size == 0:
            self._data = None
            self._headers = []
            self._row_start = 0
        else:
            # 限制显示行数
            MAX_ROWS = 5000
            if data.ndim == 1:
                if len(data) > MAX_ROWS:
                    data = data[:MAX_ROWS]
                # 转换为 2D: [Index, Value]
                self._data = np.column_stack([np.arange(len(data)), data])
                self._headers = ["Index", "Value"]
            elif data.ndim == 2:
                if data.shape[0] > MAX_ROWS:
                    data = data[:MAX_ROWS]
                self._data = data
                self._headers = [f"Col {i}" for i in range(data.shape[1])]
            else:
                # 高维：展平
                flat = data.flatten()
                if len(flat) > MAX_ROWS:
                    flat = flat[:MAX_ROWS]
                self._data = np.column_stack([np.arange(len(flat)), flat])
                self._headers = ["Index", "Value"]

            self._row_start = row_start

        self.endResetModel()

    def clear_data(self) -> None:
        """清空数据"""
        self.beginResetModel()
        self._data = None
        self._headers = []
        self._row_start = 0
        self.endResetModel()

    def _format_value(self, val) -> str:
        """格式化数值"""
        if isinstance(val, (np.floating, float)):
            if np.isnan(val):
                return "NaN"
            elif np.isinf(val):
                return "Inf" if val > 0 else "-Inf"
            else:
                return f"{val:.6g}"
        elif isinstance(val, (np.integer, int)):
            return str(val)
        elif isinstance(val, bytes):
            try:
                return val.decode('utf-8')
            except:
                return str(val)
        else:
            return str(val)


class DataTable(QTableView):
    """数据表格视图（使用虚拟模型）"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 使用虚拟模型
        self._model = DataTableModel(self)
        self.setModel(self._model)

        # 配置
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ContiguousSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(False)

        # 样式
        self.setStyleSheet("""
            QTableView {
                background-color: #1e1e1e;
                alternate-background-color: #252526;
                color: #cccccc;
                gridline-color: #333333;
                border: none;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
            }
            QTableView::item {
                padding: 4px 8px;
            }
            QTableView::item:selected {
                background-color: #264f78;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 4px 8px;
                border: 1px solid #333333;
                font-weight: bold;
            }
        """)

        # 表头
        self.horizontalHeader().setSectionsMovable(True)
        self.horizontalHeader().setStretchLastSection(False)
        self.verticalHeader().setDefaultSectionSize(25)

    def load_data(self, data: np.ndarray, row_start: int = 0) -> None:
        """加载数据"""
        self._model.load_data(data, row_start)

        # 自动调整列宽
        self.horizontalHeader().resizeSections(QHeaderView.ResizeMode.ResizeToContents)

    def clear_data(self) -> None:
        """清空"""
        self._model.clear_data()


class DataTablePanel(QWidget):
    """数据表格面板（带状态信息）"""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 状态栏
        self._status_bar = QWidget()
        status_layout = QHBoxLayout(self._status_bar)
        status_layout.setContentsMargins(8, 4, 8, 4)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #888888; font-size: 11px;")
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()

        layout.addWidget(self._status_bar)

        # 表格
        self.table = DataTable(self)
        layout.addWidget(self.table)

    def load_data(self, data: np.ndarray, row_start: int = 0) -> None:
        """加载数据"""
        self.table.load_data(data, row_start)

        # 更新状态
        if data is not None and data.size > 0:
            self._status_label.setText(
                f"Shape: {data.shape} | Dtype: {data.dtype} | Size: {data.size:,}"
            )
        else:
            self._status_label.setText("")

    def clear(self) -> None:
        """清空"""
        self.table.clear_data()
        self._status_label.setText("")
