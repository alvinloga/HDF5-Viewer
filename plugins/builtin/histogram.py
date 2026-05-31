"""Histogram Plugin — 直方图可视化"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from core.datasource import DataMeta
from plugins.base import VisualizePlugin


class HistogramWidget(QWidget):
    """直方图控件（简化版，使用文本显示）"""

    def __init__(self, data: np.ndarray, meta: DataMeta, parent=None):
        super().__init__(parent)
        self._data = data
        self._meta = meta

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 标题
        title = QLabel(f"Histogram: {meta.name}")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        # 统计信息
        stats_label = QLabel()
        stats_label.setStyleSheet("font-size: 12px; color: #cccccc;")
        stats_label.setWordWrap(True)

        try:
            float_data = data.astype(float)
            valid = float_data[~np.isnan(float_data)]

            if len(valid) > 0:
                mean = np.mean(valid)
                std = np.std(valid)
                min_val = np.min(valid)
                max_val = np.max(valid)

                stats_text = (
                    f"Count: {len(valid):,}\n"
                    f"Mean: {mean:.6g}\n"
                    f"Std: {std:.6g}\n"
                    f"Min: {min_val:.6g}\n"
                    f"Max: {max_val:.6g}\n\n"
                )

                # 简单的文本直方图
                hist, bins = np.histogram(valid, bins=20)
                max_count = max(hist) if len(hist) > 0 else 1

                stats_text += "Distribution:\n"
                for i in range(len(hist)):
                    bar_len = int(hist[i] / max_count * 40)
                    bar = "█" * bar_len
                    stats_text += f"{bins[i]:10.4g} |{bar} ({hist[i]})\n"

                stats_label.setText(stats_text)
            else:
                stats_label.setText("No valid numeric data")

        except Exception as e:
            stats_label.setText(f"Error: {e}")

        layout.addWidget(stats_label)
        layout.addStretch()


class HistogramPlugin(VisualizePlugin):
    """直方图插件"""

    @property
    def name(self) -> str:
        return "Histogram"

    @property
    def accepts(self) -> list[str]:
        return ['1d', '2d', 'numeric']

    def create_widget(self, data: np.ndarray, meta: DataMeta) -> QWidget:
        return HistogramWidget(data, meta)
