"""SearchService — 全局搜索服务"""

import logging

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                              QTreeWidget, QTreeWidgetItem, QLabel, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal
from core.event_bus import EventBus
from typing import Optional
from core.datasource import DataSource
from gui.theme import get_theme_colors


class SearchResult(QTreeWidget):
    """搜索结果"""

    result_clicked = pyqtSignal(str)  # path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Path", "Type"])
        self.setAlternatingRowColors(True)

        self.itemDoubleClicked.connect(self._on_item_clicked)

    def apply_theme(self, theme: str):
        colors = get_theme_colors(theme)
        self.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {colors['bg_secondary']};
                color: {colors['text_primary']};
                border: none;
                font-size: 12px;
            }}
            QTreeWidget::item {{
                height: 22px;
            }}
            QTreeWidget::item:selected {{
                background-color: {colors['bg_selected']};
            }}
        """)

    def load_results(self, results: list[str]) -> None:
        """加载搜索结果"""
        self.clear()
        for path in results:
            item = QTreeWidgetItem(self)
            item.setText(0, path)
            item.setText(1, "dataset" if "/" in path else "group")
            item.setData(0, Qt.ItemDataRole.UserRole, path)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """点击结果"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.result_clicked.emit(path)


class SearchPanel(QWidget):
    """搜索面板"""

    node_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source: Optional[DataSource] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题
        self._header = QLabel("SEARCH")
        layout.addWidget(self._header)

        # 搜索输入
        search_row = QHBoxLayout()
        search_row.setContentsMargins(8, 8, 8, 8)
        search_row.setSpacing(4)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search nodes...")
        self.search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self.search_input)

        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self._search_btn)

        layout.addLayout(search_row)

        # 搜索结果
        self.results = SearchResult()
        self.results.result_clicked.connect(self.node_selected.emit)
        layout.addWidget(self.results)

    def set_source(self, source: DataSource) -> None:
        """设置数据源"""
        self._source = source

    def _on_search(self) -> None:
        """执行搜索"""
        if not self._source:
            return

        keyword = self.search_input.text().strip()
        if not keyword:
            return

        try:
            results = self._source.search(keyword)
            self.results.load_results(results)
        except Exception as e:
            logger.error(f"Search error: {e}")

    def apply_theme(self, theme: str):
        colors = get_theme_colors(theme)
        self._header.setStyleSheet(f"""
            QLabel {{
                color: {colors['text_header']};
                font-size: 11px;
                font-weight: bold;
                padding: 8px 12px;
                background-color: {colors['bg_secondary']};
                border-bottom: 1px solid {colors['border_header']};
            }}
        """)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {colors['bg_input']};
                color: {colors['text_primary']};
                border: 1px solid {colors['border_input']};
                padding: 4px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {colors['accent']};
            }}
        """)
        self._search_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors['bg_button']};
                color: white;
                border: none;
                padding: 4px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {colors['bg_button_hover']};
            }}
        """)
        self.results.apply_theme(theme)
