"""CommandPalette — Ctrl+Shift+P 命令面板"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLineEdit, QListWidget,
                              QListWidgetItem, QLabel)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction


class CommandPalette(QDialog):
    """命令面板 — 快速搜索和执行操作"""

    command_selected = pyqtSignal(str)  # command_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setMinimumWidth(400)
        self.setMaximumHeight(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type a command...")
        self.search_input.textChanged.connect(self._filter_commands)
        layout.addWidget(self.search_input)

        self.command_list = QListWidget()
        self.command_list.itemClicked.connect(self._on_command_clicked)
        layout.addWidget(self.command_list)

        self._commands: list[tuple[str, str, str]] = []
        self._register_default_commands()

        # 应用默认主题样式
        self.apply_theme("dark")

    def _register_default_commands(self):
        self._commands = [
            ("file.open", "Open File", "Ctrl+O"),
            ("file.open_folder", "Open Folder", "Ctrl+Shift+O"),
            ("file.export_csv", "Export as CSV", "Ctrl+Shift+E"),
            ("file.export_npy", "Export as NumPy", ""),
            ("file.close", "Close Tab", "Ctrl+W"),
            ("file.close_all", "Close All Tabs", ""),
            ("view.explorer", "Show Explorer", "Ctrl+Shift+X"),
            ("view.search", "Show Search", "Ctrl+Shift+F"),
            ("view.plugins", "Show Plugins", ""),
            ("view.bottom_panel", "Toggle Bottom Panel", "Ctrl+J"),
            ("view.toggle_theme", "Toggle Theme", ""),
            ("view.edit_mode", "Toggle Edit Mode", ""),
            ("view.command_palette", "Command Palette", "Ctrl+Shift+P"),
            ("help.about", "About", ""),
        ]
        self._refresh_list()

    def _refresh_list(self, filter_text: str = ""):
        self.command_list.clear()
        for cmd_id, label, shortcut in self._commands:
            if filter_text and filter_text.lower() not in label.lower() and filter_text.lower() not in cmd_id.lower():
                continue
            display = f"{label}" + (f"  [{shortcut}]" if shortcut else "")
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, cmd_id)
            self.command_list.addItem(item)
        if self.command_list.count() > 0:
            self.command_list.setCurrentRow(0)

    def _filter_commands(self, text: str):
        self._refresh_list(text)

    def _on_command_clicked(self, item: QListWidgetItem):
        cmd_id = item.data(Qt.ItemDataRole.UserRole)
        self.command_selected.emit(cmd_id)
        self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        elif event.key() == Qt.Key.Key_Return:
            item = self.command_list.currentItem()
            if item:
                self._on_command_clicked(item)
        elif event.key() == Qt.Key.Key_Up:
            row = self.command_list.currentRow()
            if row > 0:
                self.command_list.setCurrentRow(row - 1)
        elif event.key() == Qt.Key.Key_Down:
            row = self.command_list.currentRow()
            if row < self.command_list.count() - 1:
                self.command_list.setCurrentRow(row + 1)
        else:
            super().keyPressEvent(event)

    def apply_theme(self, theme: str):
        """根据主题切换样式"""
        if theme == "light":
            self.search_input.setStyleSheet("""
                QLineEdit {
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #cccccc;
                    padding: 8px;
                    font-size: 14px;
                    border-radius: 4px;
                }
                QLineEdit:focus {
                    border-color: #0078d4;
                }
            """)
            self.command_list.setStyleSheet("""
                QListWidget {
                    background-color: #ffffff;
                    color: #333333;
                    border: none;
                    font-size: 13px;
                }
                QListWidget::item {
                    padding: 6px 8px;
                }
                QListWidget::item:selected {
                    background-color: #0060c0;
                    color: #ffffff;
                }
            """)
        else:  # dark
            self.search_input.setStyleSheet("""
                QLineEdit {
                    background-color: #3c3c3c;
                    color: #cccccc;
                    border: 1px solid #555555;
                    padding: 8px;
                    font-size: 14px;
                    border-radius: 4px;
                }
                QLineEdit:focus {
                    border-color: #0078d4;
                }
            """)
            self.command_list.setStyleSheet("""
                QListWidget {
                    background-color: #252526;
                    color: #cccccc;
                    border: none;
                    font-size: 13px;
                }
                QListWidget::item {
                    padding: 6px 8px;
                }
                QListWidget::item:selected {
                    background-color: #094771;
                    color: #ffffff;
                }
            """)

    def show_palette(self):
        self.search_input.clear()
        self._refresh_list()
        if self.parent():
            parent = self.parent()
            x = parent.x() + (parent.width() - self.width()) // 2
            y = parent.y() + parent.height() // 4
            self.move(x, y)
        self.show()
        self.search_input.setFocus()
