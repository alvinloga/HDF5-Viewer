"""BottomPanel — 底部面板（属性/输出/日志）"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                              QTextEdit, QTreeWidget, QTreeWidgetItem, QLabel)
from PyQt6.QtCore import Qt, pyqtSignal
from core.event_bus import EventBus
from core.datasource import DataMeta

from .theme import get_theme_colors


class PropertiesView(QTreeWidget):
    """属性视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Property", "Value"])
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(False)

    def load_metadata(self, meta: DataMeta) -> None:
        self.clear()

        if not meta:
            return

        self._add_item("Path", meta.path)
        self._add_item("Name", meta.name)
        self._add_item("Type", meta.node_type.value)

        if meta.shape:
            self._add_item("Shape", str(meta.shape))
        if meta.dtype:
            self._add_item("DType", meta.dtype)
        if meta.ndim:
            self._add_item("Dimensions", str(meta.ndim))
        if meta.size:
            self._add_item("Size", f"{meta.size:,}")
        if meta.chunks:
            self._add_item("Chunks", str(meta.chunks))
        if meta.compression:
            self._add_item("Compression", meta.compression)

    def _add_item(self, name: str, value: str) -> None:
        item = QTreeWidgetItem(self)
        item.setText(0, name)
        item.setText(1, value)

    def apply_theme(self, colors: dict):
        self.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {colors['bg_primary']};
                color: {colors['text_primary']};
                border: none;
                font-size: 12px;
                alternate-background-color: {colors['bg_alternate']};
            }}
            QTreeWidget::item {{
                height: 22px;
                padding: 2px 4px;
            }}
            QTreeWidget::item:selected {{
                background-color: {colors['bg_selected']};
                color: {colors['text_selected']};
            }}
            QTreeWidget::item:hover {{
                background-color: {colors['bg_hover']};
            }}
            QHeaderView::section {{
                background-color: {colors['bg_header']};
                color: {colors['text_primary']};
                padding: 4px 8px;
                border: none;
                border-bottom: 1px solid {colors['border']};
                font-size: 12px;
            }}
        """)


class AttributesView(QTreeWidget):
    """属性视图"""

    attr_double_clicked = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Name", "Value"])
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(False)
        self._attrs_raw: dict = {}

    def load_attrs(self, attrs: dict) -> None:
        self.clear()
        self._attrs_raw = {}

        if not attrs:
            item = QTreeWidgetItem(self)
            item.setText(0, "(No attributes)")
            item.setForeground(0, Qt.GlobalColor.gray)
            return

        for key, value in attrs.items():
            preview = self._preview_value(value)
            self._add_attr_item(key, preview)
            self._attrs_raw[key] = value

    def _add_attr_item(self, name: str, preview: str) -> None:
        item = QTreeWidgetItem(self)
        item.setText(0, name)
        item.setText(1, preview)
        item.setData(0, Qt.ItemDataRole.UserRole, "attr")
        item.setData(1, Qt.ItemDataRole.UserRole, name)
        font = item.font(1)
        font.setItalic(True)
        item.setFont(1, font)

    def _preview_value(self, value) -> str:
        import numpy as np
        if isinstance(value, np.ndarray):
            if value.ndim == 0:
                return str(value.item())
            elif value.size <= 6:
                return str(value)
            else:
                return f"array {value.shape} {value.dtype}"
        elif isinstance(value, (list, tuple)):
            if len(value) <= 6:
                return str(value)
            else:
                return f"[{type(value[0]).__name__} x{len(value)}]"
        elif isinstance(value, bytes):
            try:
                decoded = value.decode('utf-8')
                if len(decoded) > 50:
                    return f'"{decoded[:50]}..."'
                return f'"{decoded}"'
            except Exception:
                return f"bytes({len(value)})"
        elif isinstance(value, str):
            if len(value) > 50:
                return f'"{value[:50]}..."'
            return f'"{value}"'
        else:
            return str(value)

    def mouseDoubleClickEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        if item and item.data(0, Qt.ItemDataRole.UserRole) == "attr":
            attr_name = item.data(1, Qt.ItemDataRole.UserRole)
            if attr_name and attr_name in self._attrs_raw:
                attr_value = self._attrs_raw[attr_name]
                self.attr_double_clicked.emit(attr_name, attr_value)
                return
        super().mouseDoubleClickEvent(event)

    def apply_theme(self, colors: dict):
        self.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {colors['bg_primary']};
                color: {colors['text_primary']};
                border: none;
                font-size: 12px;
                alternate-background-color: {colors['bg_alternate']};
            }}
            QTreeWidget::item {{
                height: 22px;
                padding: 2px 4px;
            }}
            QTreeWidget::item:selected {{
                background-color: {colors['bg_selected']};
                color: {colors['text_selected']};
            }}
            QTreeWidget::item:hover {{
                background-color: {colors['bg_hover']};
            }}
            QHeaderView::section {{
                background-color: {colors['bg_header']};
                color: {colors['text_primary']};
                padding: 4px 8px;
                border: none;
                border-bottom: 1px solid {colors['border']};
                font-size: 12px;
            }}
        """)


class OutputView(QTextEdit):
    """输出/日志视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

    def append_log(self, message: str, level: str = "info") -> None:
        color_map = {
            "info": "#cccccc",
            "warning": "#cca700",
            "error": "#f44747",
            "success": "#6a9955"
        }
        color = color_map.get(level, "#cccccc")
        self.append(f'<span style="color: {color}">{message}</span>')

    def apply_theme(self, colors: dict):
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {colors['bg_primary']};
                color: {colors['text_primary']};
                border: none;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
            }}
        """)


class BottomPanel(QWidget):
    """底部面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(200)
        self._event_bus = EventBus.get_instance()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()

        self.properties = PropertiesView()
        self.tabs.addTab(self.properties, "Properties")

        self.attributes = AttributesView()
        self.tabs.addTab(self.attributes, "Attributes")

        self.output = OutputView()
        self.tabs.addTab(self.output, "Output")

        layout.addWidget(self.tabs)

        self._event_bus.on(EventBus.NODE_SELECTED, self._on_node_selected)
        self._event_bus.on(EventBus.STATUS_MESSAGE, self._on_status_message)
        self._event_bus.on(EventBus.ERROR_OCCURRED, self._on_error)

    def _on_node_selected(self, event) -> None:
        if isinstance(event.data, dict):
            meta = event.data.get('meta')
            if meta:
                self.properties.load_metadata(meta)
                if meta.attrs:
                    self.attributes.load_attrs(meta.attrs)
                else:
                    self.attributes.load_attrs({})

    def _on_status_message(self, event) -> None:
        if isinstance(event.data, str):
            self.output.append_log(event.data, "info")

    def _on_error(self, event) -> None:
        if isinstance(event.data, str):
            self.output.append_log(event.data, "error")
            self.tabs.setCurrentWidget(self.output)

    def apply_theme(self, theme: str):
        colors = get_theme_colors(theme)
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: {colors['bg_primary']};
            }}
            QTabBar::tab {{
                background-color: {colors['bg_tab']};
                color: {colors['text_secondary']};
                padding: 6px 12px;
                margin-right: 1px;
            }}
            QTabBar::tab:selected {{
                background-color: {colors['bg_primary']};
                color: {colors['text_selected']};
            }}
        """)
        self.properties.apply_theme(colors)
        self.attributes.apply_theme(colors)
        self.output.apply_theme(colors)
