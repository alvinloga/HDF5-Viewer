"""Activity Bar — 左侧活动栏"""

from PyQt6.QtWidgets import (QVBoxLayout, QWidget, QPushButton, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon


class ActivityBarButton(QPushButton):
    """Activity Bar 按钮"""

    def __init__(self, icon_text: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.setText(icon_text)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setFixedSize(44, 44)
        self.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                font-size: 18px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton:checked {
                background-color: rgba(255, 255, 255, 0.15);
                border-left: 2px solid #0078d4;
            }
        """)


class ActivityBar(QWidget):
    """左侧 Activity Bar"""

    # 信号：切换面板
    panel_changed = pyqtSignal(str)  # panel_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(48)
        self.setStyleSheet("background-color: #333333;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 面板按钮
        self._buttons: dict[str, ActivityBarButton] = {}
        self._current_panel = ""

        # Explorer 按钮
        self._add_button("explorer", "📁", "Explorer (Ctrl+Shift+E)")

        # Search 按钮
        self._add_button("search", "🔍", "Search (Ctrl+Shift+F)")

        # Plugins 按钮
        self._add_button("plugins", "🔌", "Plugins")

        layout.addStretch()

        # Settings 按钮
        self._add_button("settings", "⚙", "Settings")

    def _add_button(self, name: str, icon_text: str, tooltip: str) -> None:
        """添加按钮"""
        btn = ActivityBarButton(icon_text, tooltip, self)
        btn.clicked.connect(lambda checked, n=name: self._on_button_clicked(n))
        self.layout().addWidget(btn)
        self._buttons[name] = btn

    def _on_button_clicked(self, name: str) -> None:
        """按钮点击处理"""
        if name == self._current_panel:
            # 再次点击同一个按钮 = 关闭面板
            self._buttons[name].setChecked(False)
            self._current_panel = ""
            self.panel_changed.emit("")
        else:
            # 切换面板
            for n, btn in self._buttons.items():
                btn.setChecked(n == name)
            self._current_panel = name
            self.panel_changed.emit(name)

    def set_active(self, name: str) -> None:
        """设置活动面板"""
        for n, btn in self._buttons.items():
            btn.setChecked(n == name)
        self._current_panel = name
