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

        # Detect theme from QApplication palette
        is_dark = self._detect_dark_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 主题颜色
        if is_dark:
            colors = {
                'figure_bg': '#1e1e1e', 'axes_bg': '#252526',
                'text': '#cccccc', 'tick': '#969696', 'spine': '#555555',
                'bar': '#569cd6', 'bar_edge': '#1e1e1e', 'error': '#f44747',
                'grid': '#555555',
            }
        else:
            colors = {
                'figure_bg': '#ffffff', 'axes_bg': '#f8f8f8',
                'text': '#333333', 'tick': '#666666', 'spine': '#cccccc',
                'bar': '#0078d4', 'bar_edge': '#ffffff', 'error': '#d32f2f',
                'grid': '#cccccc',
            }
        self._colors = colors

        title = QLabel(f"Histogram: {meta.name}")
        title.setStyleSheet(f"color: {colors['text']}; font-weight: bold; font-size: 13px; padding: 4px;")
        layout.addWidget(title)

        self.figure = Figure(figsize=(6, 4), dpi=100, facecolor=colors['figure_bg'])
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
            flat_data = self._data.astype(float).flatten()
            flat_data = flat_data[~np.isnan(flat_data)]

            if len(flat_data) == 0:
                ax.text(0.5, 0.5, 'No valid data', transform=ax.transAxes,
                        ha='center', va='center', color=self._colors['error'])
            else:
                n_bins = min(50, max(10, int(np.sqrt(len(flat_data)))))
                ax.hist(flat_data, bins=n_bins, color=self._colors['bar'],
                        edgecolor=self._colors['bar_edge'], alpha=0.8)

            ax.set_title(self._meta.name, color=self._colors['text'], fontsize=11)
            ax.set_xlabel('Value', color=self._colors['tick'], fontsize=10)
            ax.set_ylabel('Count', color=self._colors['tick'], fontsize=10)
            ax.tick_params(colors=self._colors['tick'], labelsize=9)
            ax.spines['bottom'].set_color(self._colors['spine'])
            ax.spines['left'].set_color(self._colors['spine'])
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.grid(True, alpha=0.2, color=self._colors['grid'], axis='y')

        except Exception as e:
            ax.text(0.5, 0.5, f'Error: {e}', transform=ax.transAxes,
                    ha='center', va='center', color=self._colors['error'])

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
