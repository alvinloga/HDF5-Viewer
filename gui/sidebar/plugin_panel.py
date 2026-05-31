"""PluginPanel — 插件面板，用户可选择和执行分析/可视化插件"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                              QListWidgetItem, QPushButton, QLabel, QComboBox,
                              QStackedWidget, QTextEdit)
from PyQt6.QtCore import Qt, pyqtSignal
import numpy as np

from core.event_bus import EventBus
from core.datasource import DataMeta
from core.registry import PluginManager


class PluginPanel(QWidget):
    """插件面板 — 显示可用插件，执行分析/可视化"""

    plugin_executed = pyqtSignal(str, object)  # plugin_name, result

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_source = None
        self._current_path = ""
        self._current_meta: DataMeta | None = None
        self._current_data: np.ndarray | None = None
        self._event_bus = EventBus.get_instance()

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        title_bar = QWidget()
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(8, 8, 8, 4)
        title = QLabel("PLUGINS")
        title.setStyleSheet("color: #cccccc; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        title_layout.addWidget(title)
        title_layout.addStretch()

        # 过滤器
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Analyze", "Visualize"])
        self.filter_combo.setStyleSheet("""
            QComboBox {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                padding: 2px 8px;
                font-size: 11px;
                border-radius: 2px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #cccccc;
                selection-background-color: #094771;
            }
        """)
        title_layout.addWidget(self.filter_combo)
        layout.addWidget(title_bar)

        # 插件列表
        self.plugin_list = QListWidget()
        self.plugin_list.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                color: #cccccc;
                border: none;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #2d2d2d;
            }
            QListWidget::item:selected {
                background-color: #094771;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #2a2d2e;
            }
        """)
        layout.addWidget(self.plugin_list)

        # 执行按钮
        self.execute_btn = QPushButton("Execute Plugin")
        self.execute_btn.setEnabled(False)
        self.execute_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:disabled {
                background-color: #3c3c3c;
                color: #666666;
            }
        """)
        self.execute_btn.clicked.connect(self._on_execute)
        layout.addWidget(self.execute_btn)

        # 结果区域
        self.result_stack = QStackedWidget()

        # 文本结果页
        self.text_result = QTextEdit()
        self.text_result.setReadOnly(True)
        self.text_result.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #cccccc;
                border: none;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
                padding: 8px;
            }
        """)
        self.result_stack.addWidget(self.text_result)

        # 可视化结果页（占位，运行时动态替换）
        self.viz_placeholder = QLabel("Select a visualization plugin and click Execute")
        self.viz_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viz_placeholder.setStyleSheet("color: #666666; font-size: 12px; background-color: #1e1e1e;")
        self.result_stack.addWidget(self.viz_placeholder)

        layout.addWidget(self.result_stack)

        # 初始加载插件列表
        self._refresh_plugin_list()

    def _setup_connections(self):
        self.plugin_list.currentItemChanged.connect(self._on_plugin_selected)
        self.filter_combo.currentIndexChanged.connect(self._refresh_plugin_list)
        self._event_bus.on(EventBus.NODE_SELECTED, self._on_node_selected)

    def _refresh_plugin_list(self):
        self.plugin_list.clear()
        filter_type = self.filter_combo.currentText()

        # 获取所有插件
        analyzers = PluginManager.get_analyzers()
        visualizers = PluginManager.get_visualizers()

        if filter_type in ("All", "Analyze"):
            for name, plugin in analyzers.items():
                item = QListWidgetItem(f"\U0001f4ca {name}")
                item.setData(Qt.ItemDataRole.UserRole, ("analyze", plugin))
                self.plugin_list.addItem(item)

        if filter_type in ("All", "Visualize"):
            for name, plugin in visualizers.items():
                item = QListWidgetItem(f"\U0001f4c8 {name}")
                item.setData(Qt.ItemDataRole.UserRole, ("visualize", plugin))
                self.plugin_list.addItem(item)

    def _on_plugin_selected(self, current, previous):
        self.execute_btn.setEnabled(current is not None)

    def _on_node_selected(self, event):
        if isinstance(event.data, dict):
            meta = event.data.get('meta')
            if meta:
                self._current_meta = meta
                self._filter_by_data(meta)

    def set_data(self, source, path: str, meta: DataMeta):
        self._current_source = source
        self._current_path = path
        self._current_meta = meta
        self._filter_by_data(meta)

    def _filter_by_data(self, meta: DataMeta):
        if not meta or not meta.shape:
            return

        dtype = meta.dtype or "float64"
        shape = meta.shape

        self.plugin_list.clear()
        filter_type = self.filter_combo.currentText()

        analyzers = PluginManager.get_matching_analyzers(shape, dtype)
        visualizers = PluginManager.get_matching_visualizers(shape, dtype)

        if filter_type in ("All", "Analyze"):
            for plugin in analyzers:
                item = QListWidgetItem(f"\U0001f4ca {plugin.name}")
                item.setData(Qt.ItemDataRole.UserRole, ("analyze", plugin))
                self.plugin_list.addItem(item)

        if filter_type in ("All", "Visualize"):
            for plugin in visualizers:
                item = QListWidgetItem(f"\U0001f4c8 {plugin.name}")
                item.setData(Qt.ItemDataRole.UserRole, ("visualize", plugin))
                self.plugin_list.addItem(item)

    def _on_execute(self):
        item = self.plugin_list.currentItem()
        if not item:
            return

        plugin_type, plugin = item.data(Qt.ItemDataRole.UserRole)

        if not self._current_source or not self._current_path:
            self.text_result.setText("No dataset selected. Double-click a dataset in Explorer first.")
            self.result_stack.setCurrentIndex(0)
            return

        try:
            # 读取数据
            from core.slicer import SliceParser
            if self._current_meta and self._current_meta.shape:
                slices = SliceParser.default_slice(self._current_meta.shape)
            else:
                slices = ()
            data = self._current_source.read_slice(self._current_path, slices)

            if plugin_type == "analyze":
                result = plugin.run(data, self._current_meta)
                self._show_analyze_result(result)
            elif plugin_type == "visualize":
                widget = plugin.create_widget(data, self._current_meta)
                self._show_visualize_result(widget)

            self.plugin_executed.emit(plugin.name, None)

        except Exception as e:
            self.text_result.setText(f"Error executing plugin:\n{e}")
            self.result_stack.setCurrentIndex(0)

    def _show_analyze_result(self, result: dict):
        name = result.get('name', 'Unknown')
        summary = result.get('summary', '')
        data = result.get('result')

        text = f"=== {name} ===\n\n"
        text += f"Summary: {summary}\n\n"

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, float):
                    text += f"  {key}: {value:.6g}\n"
                else:
                    text += f"  {key}: {value}\n"

        self.text_result.setText(text)
        self.result_stack.setCurrentIndex(0)

    def _show_visualize_result(self, widget: 'QWidget'):
        # 移除旧的可视化控件
        old_widget = self.result_stack.widget(1)
        if old_widget is not None and old_widget is not self.viz_placeholder:
            self.result_stack.removeWidget(old_widget)
            old_widget.deleteLater()

        # 移除当前 index 1 的控件（可能是占位符或已删除的旧控件）
        current_widget = self.result_stack.widget(1)
        if current_widget is not None:
            self.result_stack.removeWidget(current_widget)

        self.result_stack.insertWidget(1, widget)
        self.result_stack.setCurrentIndex(1)

    def clear_results(self):
        self.text_result.clear()
        # 恢复占位符
        old_widget = self.result_stack.widget(1)
        if old_widget is not None and old_widget is not self.viz_placeholder:
            self.result_stack.removeWidget(old_widget)
            old_widget.deleteLater()
        elif old_widget is None or old_widget is self.viz_placeholder:
            # 确保占位符在正确位置
            current = self.result_stack.widget(1)
            if current is not None:
                self.result_stack.removeWidget(current)
        self.result_stack.insertWidget(1, self.viz_placeholder)
        self.result_stack.setCurrentIndex(0)
