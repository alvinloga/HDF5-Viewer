"""Explorer — 文件树视图（带右键菜单）"""

from PyQt6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout,
                              QLabel, QMenu, QTreeWidgetItemIterator, QPushButton,
                              QHBoxLayout)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QClipboard
from PyQt6.QtWidgets import QApplication

from core.datasource import TreeNode, NodeType, DataMeta, DataSource, DataSource

from ..theme import get_theme_colors


class ExplorerTree(QTreeWidget):
    """文件树"""

    node_selected = pyqtSignal(str, object)
    node_double_clicked = pyqtSignal(str)
    open_in_new_tab = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

        self._path_items: dict[str, QTreeWidgetItem] = {}
        self._current_tree: TreeNode | None = None
        self._loaded_file_path: str | None = None
        self._current_source: DataSource | None = None

    def load_tree(self, tree: TreeNode, file_path: str, source=None) -> None:
        if source is not None:
            self._current_source = source

        if self._loaded_file_path == file_path and self._path_items:
            return

        self.clear()
        self._path_items.clear()
        self._current_tree = tree
        self._loaded_file_path = file_path

        root_item = QTreeWidgetItem(self)
        root_item.setText(0, f"\U0001f4c1 {tree.name}")
        root_item.setData(0, Qt.ItemDataRole.UserRole, tree.path)
        root_item.setExpanded(True)
        self._path_items[tree.path] = root_item

        self._add_children(root_item, tree.children)

    def _add_children(self, parent_item: QTreeWidgetItem, children: list[TreeNode]) -> None:
        for child in children:
            item = QTreeWidgetItem(parent_item)
            item.setData(0, Qt.ItemDataRole.UserRole, child.path)

            if child.node_type == NodeType.GROUP:
                item.setText(0, f"\U0001f4c1 {child.name}")
                self._add_children(item, child.children)
            elif child.node_type == NodeType.DATASET:
                shape_str = ""
                if child.meta and child.meta.shape:
                    shape_str = f" {child.meta.shape}"
                dtype_str = ""
                if child.meta and child.meta.dtype:
                    dtype_str = f" [{child.meta.dtype}]"
                item.setText(0, f"\U0001f4ca {child.name}{shape_str}{dtype_str}")

            self._path_items[child.path] = item

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.node_selected.emit(path, None)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.node_double_clicked.emit(path)

    def contextMenuEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        if not item:
            return

        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return

        menu = QMenu(self)

        open_new_tab = QAction("Open in New Tab", self)
        open_new_tab.triggered.connect(lambda: self.open_in_new_tab.emit(path))
        menu.addAction(open_new_tab)

        menu.addSeparator()

        copy_path = QAction("Copy Path", self)
        copy_path.triggered.connect(lambda: self._copy_to_clipboard(path))
        menu.addAction(copy_path)

        name = path.split("/")[-1] or "/"
        copy_name = QAction(f"Copy Name: {name}", self)
        copy_name.triggered.connect(lambda: self._copy_to_clipboard(name))
        menu.addAction(copy_name)

        menu.exec(event.globalPos())

    def _copy_to_clipboard(self, text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def select_path(self, path: str) -> None:
        if path in self._path_items:
            item = self._path_items[path]
            self.setCurrentItem(item)
            self.scrollToItem(item)

    def expand_all(self) -> None:
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item.childCount() > 0:
                item.setExpanded(True)
            iterator += 1

    def collapse_all(self) -> None:
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item.childCount() > 0:
                item.setExpanded(False)
            iterator += 1

    def toggle_expand_all(self) -> None:
        has_collapsed = False
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item.childCount() > 0 and not item.isExpanded():
                has_collapsed = True
                break
            iterator += 1

        if has_collapsed:
            self.expand_all()
        else:
            self.collapse_all()

    def clear_loaded_file(self) -> None:
        self._loaded_file_path = None
        self._current_source = None

    def get_source(self) -> DataSource | None:
        return self._current_source

    def apply_theme(self, colors: dict):
        self.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {colors['bg_secondary']};
                color: {colors['text_primary']};
                border: none;
                font-size: 13px;
            }}
            QTreeWidget::item {{
                height: 24px;
                padding: 2px;
            }}
            QTreeWidget::item:selected {{
                background-color: {colors['bg_selected']};
            }}
            QTreeWidget::item:hover {{
                background-color: {colors['bg_hover']};
            }}
        """)


class ExplorerPanel(QWidget):
    """Explorer 面板"""

    node_selected = pyqtSignal(str, object)
    node_double_clicked = pyqtSignal(str)
    open_in_new_tab = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        self._header_label = QLabel("EXPLORER")
        header_layout.addWidget(self._header_label)

        header_layout.addStretch()

        self._toggle_btn = QPushButton("\u229e")
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.setToolTip("Toggle Expand/Collapse All")
        self._toggle_btn.clicked.connect(self._on_toggle_expand)
        header_layout.addWidget(self._toggle_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._header_widget = QWidget()
        self._header_widget.setLayout(header_layout)
        layout.addWidget(self._header_widget)

        self.tree = ExplorerTree(self)
        self.tree.node_selected.connect(self.node_selected.emit)
        self.tree.node_double_clicked.connect(self.node_double_clicked.emit)
        self.tree.open_in_new_tab.connect(self.open_in_new_tab.emit)
        layout.addWidget(self.tree)

    def _on_toggle_expand(self) -> None:
        self.tree.toggle_expand_all()
        has_collapsed = False
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.childCount() > 0 and not item.isExpanded():
                has_collapsed = True
                break
            iterator += 1
        self._toggle_btn.setText("\u229e" if has_collapsed else "\u229f")

    def load_tree(self, tree: TreeNode, file_path: str, source=None) -> None:
        self.tree.load_tree(tree, file_path, source)

    def select_path(self, path: str) -> None:
        self.tree.select_path(path)

    def clear_loaded_file(self) -> None:
        self.tree.clear_loaded_file()

    def get_source(self) -> DataSource | None:
        return self.tree.get_source()

    def apply_theme(self, theme: str):
        colors = get_theme_colors(theme)
        self._header_label.setStyleSheet(f"""
            QLabel {{
                color: {colors['text_header']};
                font-size: 11px;
                font-weight: bold;
                padding: 8px 12px;
                background-color: {colors['bg_secondary']};
                border-bottom: 1px solid {colors['border_header']};
            }}
        """)
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {colors['text_secondary']};
                border: none;
                font-size: 14px;
                padding: 0px;
            }}
            QPushButton:hover {{
                color: {colors['text_primary']};
                background-color: {colors['bg_input']};
            }}
        """)
        self._header_widget.setStyleSheet(f"background-color: {colors['bg_secondary']}; border-bottom: 1px solid {colors['border_header']};")
        self.tree.apply_theme(colors)
