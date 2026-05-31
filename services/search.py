"""SearchService — 全局搜索服务"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                              QTreeWidget, QTreeWidgetItem, QLabel, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal
from core.event_bus import EventBus
from core.datasource import DataSource


class SearchResult(QTreeWidget):
    """搜索结果"""

    result_clicked = pyqtSignal(str)  # path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Path", "Type"])
        self.setAlternatingRowColors(True)

        self.setStyleSheet("""
            QTreeWidget {
                background-color: #252526;
                color: #cccccc;
                border: none;
                font-size: 12px;
            }
            QTreeWidget::item {
                height: 22px;
            }
            QTreeWidget::item:selected {
                background-color: #094771;
            }
        """)

        self.itemDoubleClicked.connect(self._on_item_clicked)

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
        self._source: DataSource | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题
        header = QLabel("SEARCH")
        header.setStyleSheet("""
            QLabel {
                color: #bbbbbb;
                font-size: 11px;
                font-weight: bold;
                padding: 8px 12px;
                background-color: #252526;
                border-bottom: 1px solid #1e1e1e;
            }
        """)
        layout.addWidget(header)

        # 搜索输入
        search_row = QHBoxLayout()
        search_row.setContentsMargins(8, 8, 8, 8)
        search_row.setSpacing(4)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search nodes...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                padding: 4px 8px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        self.search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self.search_input)

        search_btn = QPushButton("Search")
        search_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        search_btn.clicked.connect(self._on_search)
        search_row.addWidget(search_btn)

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
            print(f"Search error: {e}")
