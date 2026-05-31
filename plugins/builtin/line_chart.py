"""Line Chart Plugin — 折线图可视化"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from core.datasource import DataMeta
from plugins.base import VisualizePlugin


class LineChartWidget(QWidget):
    """折线图控件（简化版，使用文本显示）"""

    def __init__(self, data: np.ndarray, meta: DataMeta, parent=None):
        super().__init__(parent)
        self._data = data
        self._meta = meta

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 标题
        title = QLabel(f"Line Chart: {meta.name}")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        # 数据预览
        preview = QLabel()
        preview.setStyleSheet("font-family: Consolas, Monaco, monospace; font-size: 11px;")
        preview.setWordWrap(True)

        try:
            if data.ndim == 1:
                preview.setText(self._format_1d(data))
            elif data.ndim == 2:
                # 显示第一列
                preview.setText(self._format_1d(data[:, 0]) + f"\n\n(Showing column 0 of {data.shape[1]} columns)")
            else:
                flat = data.flatten()[:1000]
                preview.setText(self._format_1d(flat))
        except Exception as e:
            preview.setText(f"Error: {e}")

        layout.addWidget(preview)
        layout.addStretch()

    def _format_1d(self, data: np.ndarray) -> str:
        """格式化 1D 数据为简单的 ASCII 图"""
        if len(data) == 0:
            return "No data"

        # 采样
        max_points = 100
        if len(data) > max_points:
            indices = np.linspace(0, len(data) - 1, max_points, dtype=int)
            sampled = data[indices]
        else:
            sampled = data

        # 归一化到 0-40
        min_val = np.nanmin(sampled)
        max_val = np.nanmax(sampled)
        val_range = max_val - min_val

        if val_range == 0:
            return f"Constant value: {min_val}"

        lines = []
        for i, val in enumerate(sampled):
            if np.isnan(val):
                bar = "?"
            else:
                normalized = int((val - min_val) / val_range * 40)
                bar = "─" * normalized + "●"
            lines.append(f"{i:4d} |{bar}")

        return "\n".join(lines)


class LineChartPlugin(VisualizePlugin):
    """折线图插件"""

    @property
    def name(self) -> str:
        return "Line Chart"

    @property
    def accepts(self) -> list[str]:
        return ['1d', '2d']

    def create_widget(self, data: np.ndarray, meta: DataMeta) -> QWidget:
        return LineChartWidget(data, meta)
