"""Heatmap Plugin — 热力图可视化"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from core.datasource import DataMeta
from plugins.base import VisualizePlugin


class HeatmapWidget(QWidget):
    """热力图控件（简化版，使用文本显示）"""

    def __init__(self, data: np.ndarray, meta: DataMeta, parent=None):
        super().__init__(parent)
        self._data = data
        self._meta = meta

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 标题
        title = QLabel(f"Heatmap: {meta.name}")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        # 数据预览
        preview = QLabel()
        preview.setStyleSheet("font-family: Consolas, Monaco, monospace; font-size: 10px;")
        preview.setWordWrap(True)

        try:
            if data.ndim == 2:
                preview.setText(self._format_2d(data))
            elif data.ndim >= 3:
                # 显示第一个 2D 切片
                slice_2d = data[0] if data.ndim == 3 else data.reshape(-1, data.shape[-1])[:100]
                preview.setText(self._format_2d(slice_2d))
            else:
                preview.setText("Heatmap requires 2D+ data")
        except Exception as e:
            preview.setText(f"Error: {e}")

        layout.addWidget(preview)
        layout.addStretch()

    def _format_2d(self, data: np.ndarray) -> str:
        """格式化 2D 数据为 ASCII 热力图"""
        rows, cols = data.shape

        # 限制显示大小
        max_rows = 40
        max_cols = 80

        if rows > max_rows:
            step = rows // max_rows
            data = data[::step][:max_rows]
        if cols > max_cols:
            step = cols // max_cols
            data = data[:, ::step][:, :max_cols]

        # 归一化
        min_val = np.nanmin(data)
        max_val = np.nanmax(data)
        val_range = max_val - min_val

        if val_range == 0:
            return f"Constant value: {min_val}"

        # ASCII 字符梯度
        chars = " .:-=+*#%@"

        lines = []
        for row in data:
            line = ""
            for val in row:
                if np.isnan(val):
                    line += "?"
                else:
                    normalized = (val - min_val) / val_range
                    idx = int(normalized * (len(chars) - 1))
                    line += chars[idx]
            lines.append(line)

        return "\n".join(lines)


class HeatmapPlugin(VisualizePlugin):
    """热力图插件"""

    @property
    def name(self) -> str:
        return "Heatmap"

    @property
    def accepts(self) -> list[str]:
        return ['2d', 'image']

    def create_widget(self, data: np.ndarray, meta: DataMeta) -> QWidget:
        return HeatmapWidget(data, meta)
