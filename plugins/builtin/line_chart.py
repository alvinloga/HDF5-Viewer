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

        # Detect theme from QApplication palette
        self._is_dark = self._detect_dark_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 主题颜色
        if self._is_dark:
            self._colors = {
                'figure_bg': '#1e1e1e', 'axes_bg': '#252526',
                'text': '#cccccc', 'tick': '#969696', 'spine': '#555555',
                'line': '#4ec9b0', 'legend_bg': '#2d2d2d', 'legend_edge': '#555555',
                'legend_text': '#cccccc', 'error': '#f44747', 'grid': '#555555',
            }
        else:
            self._colors = {
                'figure_bg': '#ffffff', 'axes_bg': '#f8f8f8',
                'text': '#333333', 'tick': '#666666', 'spine': '#cccccc',
                'line': '#0078d4', 'legend_bg': '#ffffff', 'legend_edge': '#cccccc',
                'legend_text': '#333333', 'error': '#d32f2f', 'grid': '#cccccc',
            }

        # 标题
        title = QLabel(f"Line Chart: {meta.name}")
        title.setStyleSheet(f"color: {self._colors['text']}; font-weight: bold; font-size: 13px; padding: 4px;")
        layout.addWidget(title)

        # Matplotlib 图表
        self.figure = Figure(figsize=(6, 4), dpi=100, facecolor=self._colors['figure_bg'])
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self._plot()

    @staticmethod
    def _detect_dark_theme() -> bool:
        """Detect dark/light theme from QApplication palette"""
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                bg = app.palette().window().color()
                return bg.lightness() < 128
        except Exception as e:
            pass
        return True  # default dark

    def _plot(self):
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(self._colors['axes_bg'])

        try:
            if self._data.ndim == 1:
                ax.plot(self._data, color=self._colors['line'], linewidth=1)
            elif self._data.ndim == 2:
                for i in range(min(self._data.shape[1], 10)):
                    ax.plot(self._data[:, i], label=f'Col {i}', linewidth=1)
                if self._data.shape[1] <= 10:
                    ax.legend(fontsize=8, facecolor=self._colors['legend_bg'],
                              edgecolor=self._colors['legend_edge'], labelcolor=self._colors['legend_text'])
            else:
                flat = self._data.flatten()[:10000]
                ax.plot(flat, color=self._colors['line'], linewidth=1)

            ax.set_title(self._meta.name, color=self._colors['text'], fontsize=11)
            ax.tick_params(colors=self._colors['tick'], labelsize=9)
            ax.spines['bottom'].set_color(self._colors['spine'])
            ax.spines['left'].set_color(self._colors['spine'])
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.grid(True, alpha=0.2, color=self._colors['grid'])

        except Exception as e:
            ax.text(0.5, 0.5, f'Error: {e}', transform=ax.transAxes,
                    ha='center', va='center', color=self._colors['error'])

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
