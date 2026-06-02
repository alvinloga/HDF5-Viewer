"""Activity Bar — 左侧活动栏"""

from PyQt6.QtWidgets import (QVBoxLayout, QWidget, QPushButton, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon

from .theme import get_theme_colors


class ActivityBarButton(QPushButton):
    """Activity Bar 按钮"""

    def __init__(self, icon_text: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.setText(icon_text)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setFixedSize(44, 44)

    def apply_theme(self, colors: dict):
        theme = 'light' if colors['bg_primary'] == '#ffffff' else 'dark'
        hover_alpha = 'rgba(0, 0, 0, 0.1)' if theme == 'light' else 'rgba(255, 255, 255, 0.1)'
        checked_alpha = 'rgba(0, 0, 0, 0.15)' if theme == 'light' else 'rgba(255, 255, 255, 0.15)'
        self.setStyleSheet(f"""
            QPushButton {{
                border: none;
                background-color: transparent;
                font-size: 18px;
                padding: 8px;
            }}
            QPushButton:hover {{
                background-color: {hover_alpha};
            }}
            QPushButton:checked {{
                background-color: {checked_alpha};
                border-left: 2px solid {colors['accent']};
            }}
        """)


class ActivityBar(QWidget):
    """左侧 Activity Bar"""

    panel_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(48)

        self._buttons: dict[str, ActivityBarButton] = {}
        self._current_panel = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._add_button("explorer", "\U0001f4c1", "Explorer (Ctrl+Shift+E)")

        layout.addStretch()

        self._add_button("settings", "\u2699", "Settings")

    def _add_button(self, name: str, icon_text: str, tooltip: str) -> None:
        btn = ActivityBarButton(icon_text, tooltip, self)
        btn.clicked.connect(lambda checked, n=name: self._on_button_clicked(n))
        self.layout().addWidget(btn)
        self._buttons[name] = btn

    def _on_button_clicked(self, name: str) -> None:
        if name == self._current_panel:
            self._buttons[name].setChecked(False)
            self._current_panel = ""
            self.panel_changed.emit("")
        else:
            for n, btn in self._buttons.items():
                btn.setChecked(n == name)
            self._current_panel = name
            self.panel_changed.emit(name)

    def set_active(self, name: str) -> None:
        for n, btn in self._buttons.items():
            btn.setChecked(n == name)
        self._current_panel = name

    def apply_theme(self, theme: str):
        colors = get_theme_colors(theme)
        self.setStyleSheet(f"background-color: {colors['bg_activity_bar']};")
        for btn in self._buttons.values():
            btn.apply_theme(colors)
