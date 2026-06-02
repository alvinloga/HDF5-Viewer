"""StatusBar — 状态栏"""

from PyQt6.QtWidgets import QStatusBar, QLabel, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt
from core.event_bus import EventBus

from .theme import get_theme_colors


class StatusBar(QWidget):
    """状态栏"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(16)

        self.file_label = QLabel("No file open")
        self.file_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.file_label)

        layout.addStretch()

        self.node_label = QLabel("")
        self.node_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.node_label)

        self.shape_label = QLabel("")
        self.shape_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.shape_label)

        self.dtype_label = QLabel("")
        self.dtype_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.dtype_label)

        event_bus = EventBus.get_instance()
        event_bus.on(EventBus.FILE_OPENED, self._on_file_opened)
        event_bus.on(EventBus.NODE_SELECTED, self._on_node_selected)
        event_bus.on(EventBus.STATUS_MESSAGE, self._on_status_message)

    def _on_file_opened(self, event):
        if isinstance(event.data, dict):
            path = event.data.get('path', '')
            self.file_label.setText(path)
        elif isinstance(event.data, str):
            self.file_label.setText(event.data)

    def _on_node_selected(self, event):
        if isinstance(event.data, dict):
            path = event.data.get('path', '')
            meta = event.data.get('meta')
            self.node_label.setText(path)
            if meta:
                if meta.shape:
                    self.shape_label.setText(f"shape={meta.shape}")
                else:
                    self.shape_label.setText("")
                if meta.dtype:
                    self.dtype_label.setText(meta.dtype)
                else:
                    self.dtype_label.setText("")

    def _on_status_message(self, event):
        if isinstance(event.data, str):
            self.file_label.setText(event.data)

    def set_message(self, message: str) -> None:
        self.file_label.setText(message)

    def apply_theme(self, theme: str):
        colors = get_theme_colors(theme)
        self.setStyleSheet(f"background-color: {colors['bg_status_bar']}; color: white;")
