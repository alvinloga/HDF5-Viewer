"""BottomPanel — 底部面板（属性/输出/日志）"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                              QTextEdit, QTreeWidget, QTreeWidgetItem, QLabel)
from PyQt6.QtCore import Qt, pyqtSignal
from core.event_bus import EventBus
from core.datasource import DataMeta


class PropertiesView(QTreeWidget):
    """属性视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Property", "Value"])
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(False)

        self.setStyleSheet("""
            QTreeWidget {
                background-color: #1e1e1e;
                color: #cccccc;
                border: none;
                font-size: 12px;
                alternate-background-color: #252526;
            }
            QTreeWidget::item {
                height: 22px;
                padding: 2px 4px;
            }
            QTreeWidget::item:selected {
                background-color: #094771;
                color: #ffffff;
            }
            QTreeWidget::item:hover {
                background-color: #2a2d2e;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 4px 8px;
                border: none;
                border-bottom: 1px solid #333333;
                font-size: 12px;
            }
        """)

    def load_metadata(self, meta: DataMeta) -> None:
        """加载元数据"""
        self.clear()

        if not meta:
            return

        # 基本信息
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
        """添加属性项"""
        item = QTreeWidgetItem(self)
        item.setText(0, name)
        item.setText(1, value)


class AttributesView(QTreeWidget):
    """属性视图"""

    attr_double_clicked = pyqtSignal(str, object)  # attr_name, attr_value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Name", "Value"])
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(False)
        self._attrs_raw: dict = {}

        self.setStyleSheet("""
            QTreeWidget {
                background-color: #1e1e1e;
                color: #cccccc;
                border: none;
                font-size: 12px;
                alternate-background-color: #252526;
            }
            QTreeWidget::item {
                height: 22px;
                padding: 2px 4px;
            }
            QTreeWidget::item:selected {
                background-color: #094771;
                color: #ffffff;
            }
            QTreeWidget::item:hover {
                background-color: #2a2d2e;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 4px 8px;
                border: none;
                border-bottom: 1px solid #333333;
                font-size: 12px;
            }
        """)

    def load_attrs(self, attrs: dict) -> None:
        """加载属性"""
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
        """添加属性行（可双击打开详细视图）"""
        item = QTreeWidgetItem(self)
        item.setText(0, name)
        item.setText(1, preview)
        item.setData(0, Qt.ItemDataRole.UserRole, "attr")  # 标记为属性行
        item.setData(1, Qt.ItemDataRole.UserRole, name)     # 保存属性名
        # 用斜体提示可双击
        font = item.font(1)
        font.setItalic(True)
        item.setFont(1, font)

    def _preview_value(self, value) -> str:
        """生成属性值的预览文本"""
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
        """双击属性行 → 发出 attr_double_clicked 信号"""
        item = self.itemAt(event.pos())
        if item and item.data(0, Qt.ItemDataRole.UserRole) == "attr":
            attr_name = item.data(1, Qt.ItemDataRole.UserRole)
            if attr_name and attr_name in self._attrs_raw:
                attr_value = self._attrs_raw[attr_name]
                self.attr_double_clicked.emit(attr_name, attr_value)
                return
        super().mouseDoubleClickEvent(event)


class OutputView(QTextEdit):
    """输出/日志视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #cccccc;
                border: none;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
            }
        """)

    def append_log(self, message: str, level: str = "info") -> None:
        """添加日志"""
        color_map = {
            "info": "#cccccc",
            "warning": "#cca700",
            "error": "#f44747",
            "success": "#6a9955"
        }
        color = color_map.get(level, "#cccccc")
        self.append(f'<span style="color: {color}">{message}</span>')


class BottomPanel(QWidget):
    """底部面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(200)
        self._event_bus = EventBus.get_instance()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #969696;
                padding: 6px 12px;
                margin-right: 1px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #ffffff;
            }
        """)

        # Properties 标签
        self.properties = PropertiesView()
        self.tabs.addTab(self.properties, "Properties")

        # Attributes 标签
        self.attributes = AttributesView()
        self.tabs.addTab(self.attributes, "Attributes")

        # Output 标签
        self.output = OutputView()
        self.tabs.addTab(self.output, "Output")

        layout.addWidget(self.tabs)

        # 注册事件
        self._event_bus.on(EventBus.NODE_SELECTED, self._on_node_selected)
        self._event_bus.on(EventBus.STATUS_MESSAGE, self._on_status_message)
        self._event_bus.on(EventBus.ERROR_OCCURRED, self._on_error)

    def _on_node_selected(self, event) -> None:
        """节点选中"""
        if isinstance(event.data, dict):
            meta = event.data.get('meta')
            if meta:
                self.properties.load_metadata(meta)
                if meta.attrs:
                    self.attributes.load_attrs(meta.attrs)
                else:
                    self.attributes.load_attrs({})

    def _on_status_message(self, event) -> None:
        """状态消息"""
        if isinstance(event.data, str):
            self.output.append_log(event.data, "info")

    def _on_error(self, event) -> None:
        """错误消息"""
        if isinstance(event.data, str):
            self.output.append_log(event.data, "error")
            self.tabs.setCurrentWidget(self.output)
