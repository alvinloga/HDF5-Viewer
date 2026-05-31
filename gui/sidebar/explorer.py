"""Explorer — 文件树视图（带右键菜单）"""

from PyQt6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout,
                              QLabel, QMenu, QTreeWidgetItemIterator, QPushButton,
                              QHBoxLayout)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QClipboard
from PyQt6.QtWidgets import QApplication

from core.datasource import TreeNode, NodeType, DataMeta, DataSource, DataSource


class ExplorerTree(QTreeWidget):
    """文件树"""

    node_selected = pyqtSignal(str, object)  # path, DataMeta
    node_double_clicked = pyqtSignal(str)    # path
    open_in_new_tab = pyqtSignal(str)        # path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

        self.setStyleSheet("""
            QTreeWidget {
                background-color: #252526;
                color: #cccccc;
                border: none;
                font-size: 13px;
            }
            QTreeWidget::item {
                height: 24px;
                padding: 2px;
            }
            QTreeWidget::item:selected {
                background-color: #094771;
            }
            QTreeWidget::item:hover {
                background-color: #2a2d2e;
            }
        """)

        self._path_items: dict[str, QTreeWidgetItem] = {}
        self._current_tree: TreeNode | None = None
        self._loaded_file_path: str | None = None
        self._current_source: DataSource | None = None

    def load_tree(self, tree: TreeNode, file_path: str, source=None) -> None:
        """加载树结构

        如果当前已加载同一文件，不会重建树（保留展开状态）。

        Args:
            tree: 树根节点
            file_path: 文件路径
            source: 关联的数据源（可选，供右键操作时获取）
        """
        # 保存 source 引用
        if source is not None:
            self._current_source = source

        # 同一文件不重建，保留展开状态
        if self._loaded_file_path == file_path and self._path_items:
            return

        self.clear()
        self._path_items.clear()
        self._current_tree = tree
        self._loaded_file_path = file_path

        root_item = QTreeWidgetItem(self)
        root_item.setText(0, f"📁 {tree.name}")
        root_item.setData(0, Qt.ItemDataRole.UserRole, tree.path)
        root_item.setExpanded(True)
        self._path_items[tree.path] = root_item

        self._add_children(root_item, tree.children)

    def _add_children(self, parent_item: QTreeWidgetItem, children: list[TreeNode]) -> None:
        """递归添加子节点"""
        for child in children:
            item = QTreeWidgetItem(parent_item)
            item.setData(0, Qt.ItemDataRole.UserRole, child.path)

            if child.node_type == NodeType.GROUP:
                item.setText(0, f"📁 {child.name}")
                self._add_children(item, child.children)
            elif child.node_type == NodeType.DATASET:
                shape_str = ""
                if child.meta and child.meta.shape:
                    shape_str = f" {child.meta.shape}"
                dtype_str = ""
                if child.meta and child.meta.dtype:
                    dtype_str = f" [{child.meta.dtype}]"
                item.setText(0, f"📊 {child.name}{shape_str}{dtype_str}")

            self._path_items[child.path] = item

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """点击节点"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.node_selected.emit(path, None)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """双击节点"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.node_double_clicked.emit(path)

    def contextMenuEvent(self, event) -> None:
        """右键菜单"""
        item = self.itemAt(event.pos())
        if not item:
            return

        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return

        menu = QMenu(self)

        # Open in New Tab
        open_new_tab = QAction("Open in New Tab", self)
        open_new_tab.triggered.connect(lambda: self.open_in_new_tab.emit(path))
        menu.addAction(open_new_tab)

        menu.addSeparator()

        # Copy Path
        copy_path = QAction("Copy Path", self)
        copy_path.triggered.connect(lambda: self._copy_to_clipboard(path))
        menu.addAction(copy_path)

        # Copy Name
        name = path.split("/")[-1] or "/"
        copy_name = QAction(f"Copy Name: {name}", self)
        copy_name.triggered.connect(lambda: self._copy_to_clipboard(name))
        menu.addAction(copy_name)

        menu.exec(event.globalPos())

    def _copy_to_clipboard(self, text: str) -> None:
        """复制到剪贴板"""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def select_path(self, path: str) -> None:
        """选中指定路径的节点"""
        if path in self._path_items:
            item = self._path_items[path]
            self.setCurrentItem(item)
            self.scrollToItem(item)

    def expand_all(self) -> None:
        """展开所有节点"""
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item.childCount() > 0:
                item.setExpanded(True)
            iterator += 1

    def collapse_all(self) -> None:
        """折叠所有节点"""
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item.childCount() > 0:
                item.setExpanded(False)
            iterator += 1

    def toggle_expand_all(self) -> None:
        """切换全部展开/折叠"""
        # 检查是否有折叠的节点
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
        """清除已加载文件记录（文件关闭时调用）"""
        self._loaded_file_path = None
        self._current_source = None

    def get_source(self) -> DataSource | None:
        """获取当前关联的数据源"""
        return self._current_source


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

        # 标题行（标题 + 折叠/展开按钮）
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        header = QLabel("EXPLORER")
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
        header_layout.addWidget(header)

        header_layout.addStretch()

        # 折叠/展开切换按钮
        self._toggle_btn = QPushButton("⊞")
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.setToolTip("Toggle Expand/Collapse All")
        self._toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888888;
                border: none;
                font-size: 14px;
                padding: 0px;
            }
            QPushButton:hover {
                color: #cccccc;
                background-color: #3c3c3c;
            }
        """)
        self._toggle_btn.clicked.connect(self._on_toggle_expand)
        header_layout.addWidget(self._toggle_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        header_widget = QWidget()
        header_widget.setLayout(header_layout)
        header_widget.setStyleSheet("background-color: #252526; border-bottom: 1px solid #1e1e1e;")
        layout.addWidget(header_widget)

        # 文件树
        self.tree = ExplorerTree(self)
        self.tree.node_selected.connect(self.node_selected.emit)
        self.tree.node_double_clicked.connect(self.node_double_clicked.emit)
        self.tree.open_in_new_tab.connect(self.open_in_new_tab.emit)
        layout.addWidget(self.tree)

    def _on_toggle_expand(self) -> None:
        """折叠/展开切换"""
        self.tree.toggle_expand_all()
        # 更新按钮图标
        has_collapsed = False
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.childCount() > 0 and not item.isExpanded():
                has_collapsed = True
                break
            iterator += 1
        self._toggle_btn.setText("⊞" if has_collapsed else "⊟")

    def load_tree(self, tree: TreeNode, file_path: str, source=None) -> None:
        """加载树结构"""
        self.tree.load_tree(tree, file_path, source)

    def select_path(self, path: str) -> None:
        """选中指定路径"""
        self.tree.select_path(path)

    def clear_loaded_file(self) -> None:
        """清除已加载文件记录"""
        self.tree.clear_loaded_file()

    def get_source(self) -> DataSource | None:
        """获取当前关联的数据源"""
        return self.tree.get_source()
