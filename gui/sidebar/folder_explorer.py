"""FolderExplorer — 文件夹浏览器组件（懒加载、右键菜单）"""

import os
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout,
                              QHBoxLayout, QLabel, QMenu, QToolButton, QFileDialog,
                              QApplication)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction


# ---------------------------------------------------------------------------
# FolderExplorerTree
# ---------------------------------------------------------------------------

class FolderExplorerTree(QTreeWidget):
    """文件夹浏览树

    显示磁盘上的文件夹 / 文件树，只显示支持的 HDF5 格式文件。
    支持懒加载：点击文件夹时才扫描子目录。

    Signals:
        file_clicked(str):         单击文件，发出文件绝对路径
        file_double_clicked(str):  双击文件，发出文件绝对路径
    """

    file_clicked = pyqtSignal(str)
    file_double_clicked = pyqtSignal(str)

    # 默认配置（当 config 中缺少对应 key 时回退）
    _DEFAULT_FILE_FILTERS: list[str] = [".h5", ".hdf5", ".hdf", ".h5py"]
    _DEFAULT_MAX_DEPTH: int = 5
    _DEFAULT_SHOW_HIDDEN: bool = False

    def __init__(self, config: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._config = config
        self._folder_config = config.get("folder", {})

        # 从 config 读取参数
        self._file_filters: list[str] = self._folder_config.get(
            "fileFilters", self._DEFAULT_FILE_FILTERS
        )
        self._max_depth: int = self._folder_config.get(
            "maxRecursionDepth", self._DEFAULT_MAX_DEPTH
        )
        self._show_hidden: bool = self._folder_config.get(
            "showHiddenFiles", self._DEFAULT_SHOW_HIDDEN
        )

        self._root_path: Optional[str] = None
        self._loaded_items: set[str] = set()  # 已加载子项的路径集合

        # 基础属性
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)

        # 信号
        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.itemExpanded.connect(self._on_item_expanded)

        self._apply_style()

    # -- 样式 ------------------------------------------------------------------

    def _apply_style(self) -> None:
        """应用暗色主题样式（与 ExplorerTree 一致）"""
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

    # -- 公开方法 --------------------------------------------------------------

    def open_folder(self, path: str) -> None:
        """打开指定文件夹并加载第一层

        Args:
            path: 文件夹绝对路径
        """
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return

        self.clear()
        self._loaded_items.clear()
        self._root_path = path

        root_item = QTreeWidgetItem(self)
        root_item.setText(0, f"📁 {os.path.basename(path) or path}")
        root_item.setData(0, Qt.ItemDataRole.UserRole, path)
        root_item.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")  # 节点类型
        root_item.setData(0, Qt.ItemDataRole.UserRole + 2, 0)          # 深度

        # 即使根目录也需要懒加载子项
        self._load_children(root_item, path, depth=0)
        root_item.setExpanded(True)

    def refresh(self) -> None:
        """刷新当前文件夹"""
        if self._root_path and os.path.isdir(self._root_path):
            self.open_folder(self._root_path)

    def get_current_folder(self) -> Optional[str]:
        """获取当前打开的文件夹路径

        Returns:
            当前根文件夹路径，未打开时返回 None
        """
        return self._root_path

    def close_folder(self) -> None:
        """关闭当前文件夹，清空树视图"""
        self.clear()
        self._loaded_items.clear()
        self._root_path = None

    # -- 懒加载 ----------------------------------------------------------------

    def _load_children(self, parent_item: QTreeWidgetItem, dir_path: str, depth: int) -> None:
        """扫描目录并添加子节点

        只添加符合条件的文件夹和 HDF5 文件。
        空文件夹（没有匹配文件的子树）不会被添加。

        Args:
            parent_item: 父节点
            dir_path:    要扫描的目录路径
            depth:       当前递归深度
        """
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return
        except OSError:
            return

        for entry_name in entries:
            entry_path = os.path.join(dir_path, entry_name)

            # 隐藏文件过滤
            if not self._show_hidden and entry_name.startswith("."):
                continue

            if os.path.isdir(entry_path):
                # 文件夹：先检查是否包含匹配文件（递归判断，受深度限制）
                if depth < self._max_depth and self._folder_has_matches(entry_path, depth + 1):
                    folder_item = QTreeWidgetItem(parent_item)
                    folder_item.setText(0, f"📁 {entry_name}")
                    folder_item.setData(0, Qt.ItemDataRole.UserRole, entry_path)
                    folder_item.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
                    folder_item.setData(0, Qt.ItemDataRole.UserRole + 2, depth + 1)

                    # 显示展开箭头，但暂不加载子项（懒加载）
                    folder_item.setChildIndicatorPolicy(
                        QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
                    )

            elif os.path.isfile(entry_path):
                # 文件：只显示匹配的格式
                if self._is_matching_file(entry_path):
                    file_item = QTreeWidgetItem(parent_item)
                    size_str = self._format_file_size(os.path.getsize(entry_path))
                    file_item.setText(0, f"📄 {entry_name}  {size_str}")
                    file_item.setData(0, Qt.ItemDataRole.UserRole, entry_path)
                    file_item.setData(0, Qt.ItemDataRole.UserRole + 1, "file")
                    file_item.setData(0, Qt.ItemDataRole.UserRole + 2, depth + 1)

        # 标记该目录已加载
        self._loaded_items.add(dir_path)

    def _folder_has_matches(self, dir_path: str, depth: int) -> bool:
        """检查文件夹是否包含匹配的文件（递归，受深度限制）

        用于决定是否在树中显示该文件夹。
        空文件夹或不含匹配文件的文件夹不显示。

        Args:
            dir_path: 目录路径
            depth:    当前递归深度

        Returns:
            是否包含匹配文件
        """
        try:
            entries = os.listdir(dir_path)
        except (PermissionError, OSError):
            return False

        for entry_name in entries:
            if not self._show_hidden and entry_name.startswith("."):
                continue

            entry_path = os.path.join(dir_path, entry_name)

            if os.path.isfile(entry_path) and self._is_matching_file(entry_path):
                return True

            if os.path.isdir(entry_path) and depth < self._max_depth:
                if self._folder_has_matches(entry_path, depth + 1):
                    return True

        return False

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        """展开节点时懒加载子项

        如果子项尚未加载，先扫描再填充。
        """
        node_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if node_type != "folder":
            return

        dir_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not dir_path or dir_path in self._loaded_items:
            return

        depth = item.data(0, Qt.ItemDataRole.UserRole + 2) or 0
        self._load_children(item, dir_path, depth)

    # -- 文件匹配 --------------------------------------------------------------

    def _is_matching_file(self, file_path: str) -> bool:
        """判断文件是否为支持的 HDF5 格式

        Args:
            file_path: 文件路径

        Returns:
            是否匹配文件过滤列表
        """
        suffix = Path(file_path).suffix.lower()
        return suffix in self._file_filters

    # -- 文件大小格式化 ---------------------------------------------------------

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """格式化文件大小

        Args:
            size_bytes: 文件字节数

        Returns:
            格式化后的字符串，如 "1.2 MB"
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    # -- 事件处理 --------------------------------------------------------------

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """单击节点"""
        node_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if node_type == "file" and path:
            self.file_clicked.emit(path)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """双击节点"""
        node_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if node_type == "file" and path:
            self.file_double_clicked.emit(path)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 — Qt 命名约定
        """右键菜单"""
        item = self.itemAt(event.pos())
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                color: #cccccc;
                border: 1px solid #555555;
            }
            QMenu::item:selected {
                background-color: #094771;
            }
        """)

        if item:
            node_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
            path = item.data(0, Qt.ItemDataRole.UserRole)

            if node_type == "file" and path:
                # Open in New Tab
                open_new_tab = QAction("Open in New Tab", self)
                open_new_tab.triggered.connect(
                    lambda checked, p=path: self.file_double_clicked.emit(p)
                )
                menu.addAction(open_new_tab)

                menu.addSeparator()

                # Copy Path
                copy_path = QAction("Copy Path", self)
                copy_path.triggered.connect(
                    lambda checked, p=path: self._copy_to_clipboard(p)
                )
                menu.addAction(copy_path)

        # 通用操作（无论是否点击了节点）
        menu.addSeparator()

        # Open Folder
        open_folder = QAction("Open Folder...", self)
        open_folder.triggered.connect(self._on_open_folder_dialog)
        menu.addAction(open_folder)

        # Refresh
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh)
        menu.addAction(refresh_action)

        menu.exec(event.globalPos())

    def _on_open_folder_dialog(self) -> None:
        """弹出文件夹选择对话框"""
        folder = QFileDialog.getExistingDirectory(
            self, "Open Folder", self._root_path or ""
        )
        if folder:
            self.open_folder(folder)

    def _copy_to_clipboard(self, text: str) -> None:
        """复制文本到剪贴板

        Args:
            text: 要复制的文本
        """
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)


# ---------------------------------------------------------------------------
# FolderExplorerPanel
# ---------------------------------------------------------------------------

class FolderExplorerPanel(QWidget):
    """文件夹浏览器面板

    包含标题栏、工具栏和 FolderExplorerTree。
    信号转发自内部 Tree，外部只需连接 Panel 的信号即可。

    Signals:
        file_clicked(str):         转发自 FolderExplorerTree
        file_double_clicked(str):  转发自 FolderExplorerTree
    """

    file_clicked = pyqtSignal(str)
    file_double_clicked = pyqtSignal(str)

    def __init__(self, config: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题
        header = QLabel("FOLDER EXPLORER")
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

        # 工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # 文件树
        self.tree = FolderExplorerTree(config, self)
        self.tree.file_clicked.connect(self.file_clicked.emit)
        self.tree.file_double_clicked.connect(self.file_double_clicked.emit)
        layout.addWidget(self.tree)

    def _create_toolbar(self) -> QWidget:
        """创建顶部工具栏

        Returns:
            包含刷新按钮和折叠全部按钮的工具栏 Widget
        """
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #252526; border-bottom: 1px solid #1e1e1e;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)
        toolbar_layout.setSpacing(4)

        # 刷新按钮
        self._refresh_btn = QToolButton()
        self._refresh_btn.setText("🔄")
        self._refresh_btn.setToolTip("Refresh")
        self._refresh_btn.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                padding: 4px;
                font-size: 14px;
            }
            QToolButton:hover {
                background-color: #2a2d2e;
                border-radius: 3px;
            }
        """)
        self._refresh_btn.clicked.connect(self.refresh)
        toolbar_layout.addWidget(self._refresh_btn)

        # 折叠全部按钮
        self._collapse_btn = QToolButton()
        self._collapse_btn.setText("📂")
        self._collapse_btn.setToolTip("Collapse All")
        self._collapse_btn.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                padding: 4px;
                font-size: 14px;
            }
            QToolButton:hover {
                background-color: #2a2d2e;
                border-radius: 3px;
            }
        """)
        self._collapse_btn.clicked.connect(self.collapse_all)
        toolbar_layout.addWidget(self._collapse_btn)

        toolbar_layout.addStretch()
        return toolbar

    # -- 公开方法 --------------------------------------------------------------

    def open_folder(self, path: str) -> None:
        """打开指定文件夹

        Args:
            path: 文件夹绝对路径
        """
        self.tree.open_folder(path)

    def refresh(self) -> None:
        """刷新当前文件夹"""
        self.tree.refresh()

    def collapse_all(self) -> None:
        """折叠所有节点"""
        self.tree.collapseAll()

    def close_folder(self) -> None:
        """关闭当前文件夹，清空树视图"""
        self.tree.close_folder()

    def get_current_folder(self) -> Optional[str]:
        """获取当前打开的文件夹路径

        Returns:
            当前根文件夹路径，未打开时返回 None
        """
        return self.tree.get_current_folder()
