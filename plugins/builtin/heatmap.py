"""Heatmap Plugin — Matplotlib 热力图可视化"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from core.datasource import DataMeta
from plugins.base import VisualizePlugin


class HeatmapWidget(QWidget):
    """热力图控件（Matplotlib 渲染）"""

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
                'text': '#cccccc', 'tick': '#969696', 'error': '#f44747',
                'grid': '#555555',
            }
        else:
            colors = {
                'figure_bg': '#ffffff', 'axes_bg': '#f8f8f8',
                'text': '#333333', 'tick': '#666666', 'error': '#d32f2f',
                'grid': '#cccccc',
            }
        self._colors = colors

        title = QLabel(f"Heatmap: {meta.name}")
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
            if self._data.ndim == 1:
                display_data = self._data.reshape(1, -1)
            elif self._data.ndim == 2:
                display_data = self._data
            else:
                # 高维数据：展平前两维
                shape = self._data.shape
                display_data = self._data.reshape(shape[0], -1)

            # 限制显示大小
            max_rows, max_cols = 200, 200
            if display_data.shape[0] > max_rows:
                display_data = display_data[:max_rows]
            if display_data.shape[1] > max_cols:
                display_data = display_data[:, :max_cols]

            im = ax.imshow(display_data.astype(float), aspect='auto', cmap='viridis',
                          interpolation='nearest')
            cbar = self.figure.colorbar(im, ax=ax)
            cbar.ax.tick_params(colors=self._colors['tick'], labelsize=8)

            ax.set_title(self._meta.name, color=self._colors['text'], fontsize=11)
            ax.tick_params(colors=self._colors['tick'], labelsize=9)

        except Exception as e:
            ax.text(0.5, 0.5, f'Error: {e}', transform=ax.transAxes,
                    ha='center', va='center', color=self._colors['error'])

        self.figure.tight_layout()
        self.canvas.draw()


class HeatmapPlugin(VisualizePlugin):
    """热力图插件"""

    @property
    def name(self) -> str:
        return "Heatmap"

    @property
    def accepts(self) -> list[str]:
        return ['2d', 'image', '3d']

    def create_widget(self, data: np.ndarray, meta: DataMeta) -> QWidget:
        return HeatmapWidget(data, meta)
