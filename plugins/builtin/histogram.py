"""Histogram Plugin — Matplotlib 直方图可视化"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from core.datasource import DataMeta
from plugins.base import VisualizePlugin


class HistogramWidget(QWidget):
    """直方图控件（Matplotlib 渲染）"""

    def __init__(self, data: np.ndarray, meta: DataMeta, parent=None):
        super().__init__(parent)
        self._data = data
        self._meta = meta

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel(f"Histogram: {meta.name}")
        title.setStyleSheet("color: #cccccc; font-weight: bold; font-size: 13px; padding: 4px;")
        layout.addWidget(title)

        self.figure = Figure(figsize=(6, 4), dpi=100, facecolor='#1e1e1e')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self._plot()

    def _plot(self):
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('#252526')

        try:
            flat_data = self._data.astype(float).flatten()
            flat_data = flat_data[~np.isnan(flat_data)]

            if len(flat_data) == 0:
                ax.text(0.5, 0.5, 'No valid data', transform=ax.transAxes,
                        ha='center', va='center', color='#f44747')
            else:
                n_bins = min(50, max(10, int(np.sqrt(len(flat_data)))))
                ax.hist(flat_data, bins=n_bins, color='#569cd6', edgecolor='#1e1e1e', alpha=0.8)

            ax.set_title(self._meta.name, color='#cccccc', fontsize=11)
            ax.set_xlabel('Value', color='#969696', fontsize=10)
            ax.set_ylabel('Count', color='#969696', fontsize=10)
            ax.tick_params(colors='#969696', labelsize=9)
            ax.spines['bottom'].set_color('#555555')
            ax.spines['left'].set_color('#555555')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.grid(True, alpha=0.2, color='#555555', axis='y')

        except Exception as e:
            ax.text(0.5, 0.5, f'Error: {e}', transform=ax.transAxes,
                    ha='center', va='center', color='#f44747')

        self.figure.tight_layout()
        self.canvas.draw()


class HistogramPlugin(VisualizePlugin):
    """直方图插件"""

    @property
    def name(self) -> str:
        return "Histogram"

    @property
    def accepts(self) -> list[str]:
        return ['numeric', '1d', '2d']

    def create_widget(self, data: np.ndarray, meta: DataMeta) -> QWidget:
        return HistogramWidget(data, meta)
