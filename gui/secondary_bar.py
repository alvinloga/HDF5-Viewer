"""SecondaryBar — 右侧活动栏（Search/Plugins）"""

from PyQt6.QtWidgets import (QVBoxLayout, QWidget, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal


class SecondaryBarButton(QPushButton):
    """右侧 Activity Bar 按钮"""

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
                border-right: 2px solid #0078d4;  /* 注意：右侧边框 */
            }
        """)


class SecondaryBar(QWidget):
    """右侧 Activity Bar"""

    panel_changed = pyqtSignal(str)  # panel_name: "search" | "plugins" | ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(48)
        self.setStyleSheet("background-color: #333333;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._buttons: dict[str, SecondaryBarButton] = {}
        self._current_panel = ""

        # Search 按钮
        self._add_button("search", "🔍", "Search (Ctrl+Shift+F)")

        # Plugins 按钮
        self._add_button("plugins", "🔌", "Plugins")

        layout.addStretch()

    def _add_button(self, name: str, icon_text: str, tooltip: str) -> None:
        btn = SecondaryBarButton(icon_text, tooltip, self)
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
