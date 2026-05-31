"""Line Chart Plugin — Matplotlib 折线图可视化"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from core.datasource import DataMeta
from plugins.base import VisualizePlugin


class LineChartWidget(QWidget):
    """折线图控件（Matplotlib 渲染）"""

    def __init__(self, data: np.ndarray, meta: DataMeta, parent=None):
        super().__init__(parent)
        self._data = data
        self._meta = meta

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 标题
        title = QLabel(f"Line Chart: {meta.name}")
        title.setStyleSheet("color: #cccccc; font-weight: bold; font-size: 13px; padding: 4px;")
        layout.addWidget(title)

        # Matplotlib 图表
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
            if self._data.ndim == 1:
                ax.plot(self._data, color='#4ec9b0', linewidth=1)
            elif self._data.ndim == 2:
                for i in range(min(self._data.shape[1], 10)):
                    ax.plot(self._data[:, i], label=f'Col {i}', linewidth=1)
                if self._data.shape[1] <= 10:
                    ax.legend(fontsize=8, facecolor='#2d2d2d', edgecolor='#555555', labelcolor='#cccccc')
            else:
                flat = self._data.flatten()[:10000]
                ax.plot(flat, color='#4ec9b0', linewidth=1)

            ax.set_title(self._meta.name, color='#cccccc', fontsize=11)
            ax.tick_params(colors='#969696', labelsize=9)
            ax.spines['bottom'].set_color('#555555')
            ax.spines['left'].set_color('#555555')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.grid(True, alpha=0.2, color='#555555')

        except Exception as e:
            ax.text(0.5, 0.5, f'Error: {e}', transform=ax.transAxes,
                    ha='center', va='center', color='#f44747')

        self.figure.tight_layout()
        self.canvas.draw()


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
