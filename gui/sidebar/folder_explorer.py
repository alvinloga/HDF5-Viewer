"""FolderExplorer — 文件夹浏览器组件（懒加载、右键菜单）"""

import os
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout,
                              QHBoxLayout, QLabel, QMenu, QToolButton, QFileDialog,
                              QApplication)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction

from ..theme import get_theme_colors


class FolderExplorerTree(QTreeWidget):
    """文件夹浏览树"""

    file_clicked = pyqtSignal(str)
    file_double_clicked = pyqtSignal(str)

    _DEFAULT_FILE_FILTERS: list[str] = [".h5", ".hdf5", ".hdf", ".h5py"]
    _DEFAULT_MAX_DEPTH: int = 5
    _DEFAULT_SHOW_HIDDEN: bool = False

    def __init__(self, config: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._config = config
        self._folder_config = config.get("folder", {})

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
        self._loaded_items: set[str] = set()

        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)

        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.itemExpanded.connect(self._on_item_expanded)

    def open_folder(self, path: str) -> None:
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return

        self.clear()
        self._loaded_items.clear()
        self._root_path = path

        root_item = QTreeWidgetItem(self)
        root_item.setText(0, f"\U0001f4c1 {os.path.basename(path) or path}")
        root_item.setData(0, Qt.ItemDataRole.UserRole, path)
        root_item.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
        root_item.setData(0, Qt.ItemDataRole.UserRole + 2, 0)

        self._load_children(root_item, path, depth=0)
        root_item.setExpanded(True)

    def refresh(self) -> None:
        if self._root_path and os.path.isdir(self._root_path):
            self.open_folder(self._root_path)

    def get_current_folder(self) -> Optional[str]:
        return self._root_path

    def close_folder(self) -> None:
        self.clear()
        self._loaded_items.clear()
        self._root_path = None

    def _load_children(self, parent_item: QTreeWidgetItem, dir_path: str, depth: int) -> None:
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return
        except OSError:
            return

        for entry_name in entries:
            entry_path = os.path.join(dir_path, entry_name)

            if not self._show_hidden and entry_name.startswith("."):
                continue

            if os.path.isdir(entry_path):
                if depth < self._max_depth and self._folder_has_matches(entry_path, depth + 1):
                    folder_item = QTreeWidgetItem(parent_item)
                    folder_item.setText(0, f"\U0001f4c1 {entry_name}")
                    folder_item.setData(0, Qt.ItemDataRole.UserRole, entry_path)
                    folder_item.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
                    folder_item.setData(0, Qt.ItemDataRole.UserRole + 2, depth + 1)

                    folder_item.setChildIndicatorPolicy(
                        QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
                    )

            elif os.path.isfile(entry_path):
                if self._is_matching_file(entry_path):
                    file_item = QTreeWidgetItem(parent_item)
                    size_str = self._format_file_size(os.path.getsize(entry_path))
                    file_item.setText(0, f"\U0001f4c4 {entry_name}  {size_str}")
                    file_item.setData(0, Qt.ItemDataRole.UserRole, entry_path)
                    file_item.setData(0, Qt.ItemDataRole.UserRole + 1, "file")
                    file_item.setData(0, Qt.ItemDataRole.UserRole + 2, depth + 1)

        self._loaded_items.add(dir_path)

    def _folder_has_matches(self, dir_path: str, depth: int) -> bool:
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
        node_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if node_type != "folder":
            return

        dir_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not dir_path or dir_path in self._loaded_items:
            return

        depth = item.data(0, Qt.ItemDataRole.UserRole + 2) or 0
        self._load_children(item, dir_path, depth)

    def _is_matching_file(self, file_path: str) -> bool:
        suffix = Path(file_path).suffix.lower()
        return suffix in self._file_filters

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        node_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if node_type == "file" and path:
            self.file_clicked.emit(path)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        node_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if node_type == "file" and path:
            self.file_double_clicked.emit(path)

    def contextMenuEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        menu = QMenu(self)

        if item:
            node_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
            path = item.data(0, Qt.ItemDataRole.UserRole)

            if node_type == "file" and path:
                open_new_tab = QAction("Open in New Tab", self)
                open_new_tab.triggered.connect(
                    lambda checked, p=path: self.file_double_clicked.emit(p)
                )
                menu.addAction(open_new_tab)

                menu.addSeparator()

                copy_path = QAction("Copy Path", self)
                copy_path.triggered.connect(
                    lambda checked, p=path: self._copy_to_clipboard(p)
                )
                menu.addAction(copy_path)

        menu.addSeparator()

        open_folder = QAction("Open Folder...", self)
        open_folder.triggered.connect(self._on_open_folder_dialog)
        menu.addAction(open_folder)

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh)
        menu.addAction(refresh_action)

        menu.exec(event.globalPos())

    def _on_open_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Open Folder", self._root_path or ""
        )
        if folder:
            self.open_folder(folder)

    def _copy_to_clipboard(self, text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

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


class FolderExplorerPanel(QWidget):
    """文件夹浏览器面板"""

    file_clicked = pyqtSignal(str)
    file_double_clicked = pyqtSignal(str)

    def __init__(self, config: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QLabel("FOLDER EXPLORER")
        layout.addWidget(self._header)

        self._toolbar = self._create_toolbar()
        layout.addWidget(self._toolbar)

        self.tree = FolderExplorerTree(config, self)
        self.tree.file_clicked.connect(self.file_clicked.emit)
        self.tree.file_double_clicked.connect(self.file_double_clicked.emit)
        layout.addWidget(self.tree)

    def _create_toolbar(self) -> QWidget:
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)
        toolbar_layout.setSpacing(4)

        self._refresh_btn = QToolButton()
        self._refresh_btn.setText("\U0001f504")
        self._refresh_btn.setToolTip("Refresh")
        self._refresh_btn.clicked.connect(self.refresh)
        toolbar_layout.addWidget(self._refresh_btn)

        self._collapse_btn = QToolButton()
        self._collapse_btn.setText("\U0001f4c2")
        self._collapse_btn.setToolTip("Collapse All")
        self._collapse_btn.clicked.connect(self.collapse_all)
        toolbar_layout.addWidget(self._collapse_btn)

        toolbar_layout.addStretch()
        return toolbar

    def open_folder(self, path: str) -> None:
        self.tree.open_folder(path)

    def refresh(self) -> None:
        self.tree.refresh()

    def collapse_all(self) -> None:
        self.tree.collapseAll()

    def close_folder(self) -> None:
        self.tree.close_folder()

    def get_current_folder(self) -> Optional[str]:
        return self.tree.get_current_folder()

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
        self._toolbar.setStyleSheet(f"background-color: {colors['bg_secondary']}; border-bottom: 1px solid {colors['border_header']};")
        btn_style = f"""
            QToolButton {{
                background-color: transparent;
                border: none;
                padding: 4px;
                font-size: 14px;
            }}
            QToolButton:hover {{
                background-color: {colors['bg_hover']};
                border-radius: 3px;
            }}
        """
        self._refresh_btn.setStyleSheet(btn_style)
        self._collapse_btn.setStyleSheet(btn_style)
        self.tree.apply_theme(colors)
