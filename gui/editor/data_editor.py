"""DataEditor — 简单数据编辑功能"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel)
from PyQt6.QtCore import Qt, pyqtSignal


class DataEditorBar(QWidget):
    """数据编辑工具栏 — 在数据表格上方显示"""

    edit_enabled = pyqtSignal(bool)  # 是否启用编辑模式
    cell_edited = pyqtSignal(str, tuple, object)  # path, index, new_value

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        self.edit_btn = QPushButton("Edit Mode")
        self.edit_btn.setCheckable(True)
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                padding: 4px 12px;
                font-size: 11px;
                border-radius: 2px;
            }
            QPushButton:checked {
                background-color: #d44040;
                color: white;
                border-color: #d44040;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        self.edit_btn.toggled.connect(self._on_edit_toggled)
        layout.addWidget(self.edit_btn)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 4px 12px;
                font-size: 11px;
                border-radius: 2px;
            }
            QPushButton:disabled {
                background-color: #3c3c3c;
                color: #666666;
            }
        """)
        self.save_btn.clicked.connect(self._on_save)
        layout.addWidget(self.save_btn)

        self.status_label = QLabel("Read Only")
        self.status_label.setStyleSheet("color: #969696; font-size: 11px; padding: 2px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        self.warning_label = QLabel("⚠ Editing modifies the file directly")
        self.warning_label.setStyleSheet("color: #d44040; font-size: 11px;")
        self.warning_label.hide()
        layout.addWidget(self.warning_label)

    def _on_edit_toggled(self, checked: bool):
        self._editing = checked
        self.save_btn.setEnabled(checked)
        self.status_label.setText("Edit Mode" if checked else "Read Only")
        self.warning_label.setVisible(checked)
        self.edit_enabled.emit(checked)

    def _on_save(self):
        """保存修改 — 通知父组件回写数据"""
        # 由 FilePanel 监听并实际执行保存
        self.save_requested.emit()
        self.edit_btn.setChecked(False)

    save_requested = pyqtSignal()  # 请求保存信号

    def is_editing(self) -> bool:
        return self._editing
