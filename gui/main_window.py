"""MainWindow — VSCode 风格主窗口（完整版）"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                              QSplitter, QFileDialog, QMessageBox, QMenuBar,
                              QMenu, QApplication, QTabWidget)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QKeySequence, QDragEnterEvent, QDropEvent
import os

from core.event_bus import EventBus
from core.registry import DataSourceRegistry
from core.h5_source import H5Source
from .activity_bar import ActivityBar
from .sidebar.explorer import ExplorerPanel
from .sidebar.folder_explorer import FolderExplorerPanel
from .editor.tab_manager import TabManager
from .status_bar import StatusBar
from .bottom_panel import BottomPanel
from services.search import SearchPanel


class MainWindow(QMainWindow):
    """VSCode 风格主窗口"""

    def __init__(self, config: dict):
        super().__init__()
        self._config = config
        self._event_bus = EventBus.get_instance()

        # 注册数据源
        DataSourceRegistry.register(H5Source)

        # 窗口配置
        self.setWindowTitle("HDF5 Viewer")
        self.setMinimumSize(1024, 768)
        self.resize(1400, 900)

        self.setAcceptDrops(True)

        self._setup_ui()
        self._setup_menu()
        self._setup_connections()
        self._apply_style()

    def _setup_ui(self):
        """设置 UI 布局"""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Activity Bar
        self.activity_bar = ActivityBar(self)
        main_layout.addWidget(self.activity_bar)

        # 主内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 垂直分割器（主编辑区 + 底部面板）
        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.vertical_splitter.setChildrenCollapsible(False)

        # 水平分割器（侧边栏 + 编辑区）
        self.horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.horizontal_splitter.setChildrenCollapsible(False)

        # Sidebar
        self.sidebar = QWidget()
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # 侧边栏垂直分割器：FolderExplorer（上）+ 内部标签页（下）
        self.sidebar_splitter = QSplitter(Qt.Orientation.Vertical)
        self.sidebar_splitter.setChildrenCollapsible(False)

        # FolderExplorer 面板
        self.folder_explorer = FolderExplorerPanel(self._config)
        self.sidebar_splitter.addWidget(self.folder_explorer)

        # 侧边栏标签页
        self.sidebar_tabs = QTabWidget()
        self.sidebar_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.sidebar_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #252526;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #969696;
                padding: 6px 12px;
            }
            QTabBar::tab:selected {
                background-color: #252526;
                color: #ffffff;
            }
        """)

        # Explorer 面板
        self.explorer = ExplorerPanel()
        self.sidebar_tabs.addTab(self.explorer, "Explorer")

        # Search 面板
        self.search_panel = SearchPanel()
        self.sidebar_tabs.addTab(self.search_panel, "Search")

        self.sidebar_splitter.addWidget(self.sidebar_tabs)
        self.sidebar_splitter.setSizes([150, 450])

        sidebar_layout.addWidget(self.sidebar_splitter)

        self.sidebar.setFixedWidth(self._config.get('ui', {}).get('sidebarWidth', 280))
        self.horizontal_splitter.addWidget(self.sidebar)

        # 编辑器区域
        self.tab_manager = TabManager(self)
        self.horizontal_splitter.addWidget(self.tab_manager)

        self.horizontal_splitter.setSizes([280, 1120])

        # 底部面板
        self.bottom_panel = BottomPanel(self)

        # 组装垂直分割器
        self.vertical_splitter.addWidget(self.horizontal_splitter)
        self.vertical_splitter.addWidget(self.bottom_panel)
        self.vertical_splitter.setSizes([700, 200])

        content_layout.addWidget(self.vertical_splitter)
        main_layout.addWidget(content_widget)

        # 状态栏
        self.status_bar = StatusBar(self)

    def _setup_menu(self):
        """设置菜单栏"""
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: #333333;
                color: #cccccc;
                border-bottom: 1px solid #1e1e1e;
            }
            QMenuBar::item:selected {
                background-color: #505050;
            }
            QMenu {
                background-color: #2d2d2d;
                color: #cccccc;
                border: 1px solid #555555;
            }
            QMenu::item:selected {
                background-color: #094771;
            }
        """)

        # File 菜单
        file_menu = menu_bar.addMenu("File")

        open_action = QAction("Open File...", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)

        open_folder = QAction("Open Folder...", self)
        open_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        open_folder.triggered.connect(self._on_open_folder)
        file_menu.addAction(open_folder)

        close_folder = QAction("Close Folder", self)
        close_folder.triggered.connect(self._on_close_folder)
        file_menu.addAction(close_folder)

        file_menu.addSeparator()

        export_csv = QAction("Export as CSV...", self)
        export_csv.setShortcut(QKeySequence("Ctrl+Shift+E"))
        export_csv.triggered.connect(self._on_export_csv)
        file_menu.addAction(export_csv)

        file_menu.addSeparator()

        close_action = QAction("Close", self)
        close_action.setShortcut(QKeySequence("Ctrl+W"))
        close_action.triggered.connect(self._on_close_tab)
        file_menu.addAction(close_action)

        close_all_action = QAction("Close All", self)
        close_all_action.triggered.connect(self._on_close_all)
        file_menu.addAction(close_all_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View 菜单
        view_menu = menu_bar.addMenu("View")

        explorer_action = QAction("Explorer", self)
        explorer_action.setShortcut(QKeySequence("Ctrl+Shift+X"))
        explorer_action.triggered.connect(lambda: self._show_sidebar(0))
        view_menu.addAction(explorer_action)

        search_action = QAction("Search", self)
        search_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        search_action.triggered.connect(lambda: self._show_sidebar(1))
        view_menu.addAction(search_action)

        view_menu.addSeparator()

        toggle_bottom = QAction("Toggle Bottom Panel", self)
        toggle_bottom.setShortcut(QKeySequence("Ctrl+J"))
        toggle_bottom.triggered.connect(self._toggle_bottom_panel)
        view_menu.addAction(toggle_bottom)

        # Help 菜单
        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _setup_connections(self):
        """设置信号连接"""
        self.activity_bar.panel_changed.connect(self._on_panel_changed)
        self.explorer.node_double_clicked.connect(self._on_node_double_clicked)
        self.explorer.open_in_new_tab.connect(self._on_open_in_new_tab)
        self.search_panel.node_selected.connect(self._on_search_result_clicked)
        self.tab_manager.file_opened.connect(self._on_file_opened)
        self.tab_manager.file_closed.connect(self._on_file_closed)
        self.tab_manager.tab_activated.connect(self._on_tab_activated)
        self.folder_explorer.file_clicked.connect(self.browse_file)
        self.folder_explorer.file_double_clicked.connect(self.browse_file)
        self.bottom_panel.attributes.attr_double_clicked.connect(self._on_attr_double_clicked)
        self._event_bus.on(EventBus.ERROR_OCCURRED, self._on_error)

    def _apply_style(self):
        """应用全局样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #cccccc;
            }
        """)

    def _on_open_file(self):
        """打开文件"""
        extensions = DataSourceRegistry.get_supported_extensions()
        filter_str = "HDF5 Files (" + " ".join(f"*{ext}" for ext in extensions) + ")"
        filter_str += ";;All Files (*)"

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open HDF5 File", "", filter_str
        )

        if file_path:
            self.open_file(file_path)

    def open_file(self, file_path: str) -> bool:
        """打开文件（创建标签页 + 更新 Explorer）"""
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Error", f"File not found: {file_path}")
            return False

        if not DataSourceRegistry.is_supported(file_path):
            QMessageBox.warning(self, "Error", f"Unsupported file format: {file_path}")
            return False

        success = self.tab_manager.open_file(file_path)
        if success:
            self._update_explorer_for_file(file_path)

        return success

    def browse_file(self, file_path: str) -> None:
        """浏览文件（只更新 Explorer，不创建标签页）

        从 FolderExplorer 单击/双击 HDF5 文件时调用。
        只打开数据源、更新侧边栏展示内部结构，
        不在右侧创建空标签页。
        """
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Error", f"File not found: {file_path}")
            return

        if not DataSourceRegistry.is_supported(file_path):
            QMessageBox.warning(self, "Error", f"Unsupported file format: {file_path}")
            return

        # 打开数据源（如果尚未打开）
        source = DataSourceRegistry.get(file_path)
        try:
            source.open(file_path)
        except Exception as e:
            self._event_bus.emit(EventBus.ERROR_OCCURRED, f"Failed to open {file_path}: {e}")
            return

        # 更新 Explorer
        self._update_explorer_for_file(file_path)
        self.status_bar.set_message(f"Browsing: {file_path}")

    def _update_explorer_for_file(self, file_path: str) -> None:
        """更新 Explorer 树和 Search 面板以显示指定文件的内部结构

        如果 Explorer 已经加载了该文件的树，不重建（保留展开状态），
        只确保 Search 面板的 source 正确。

        Args:
            file_path: 已打开的 HDF5 文件路径
        """
        # 优先从已有的 panel 中查找 source（共享数据源）
        source = None
        for key, panel in self.tab_manager._panels.items():
            if key == file_path or key.startswith(f"{file_path}::"):
                s = panel.get_source()
                if s and s.is_open():
                    source = s
                    break

        # 如果没有 panel，尝试从 DataSourceRegistry 获取（browse 模式）
        if source is None:
            try:
                source = DataSourceRegistry.get(file_path)
                if not source.is_open():
                    source.open(file_path)
            except Exception:
                return

        if source and source.is_open():
            if self.explorer.tree._loaded_file_path != file_path:
                tree = source.get_tree()
                self.explorer.load_tree(tree, file_path, source)
            self.search_panel.set_source(source)

    def _on_close_tab(self):
        """关闭当前标签页"""
        panel = self.tab_manager.get_current_panel()
        if panel:
            # 通过反向映射找到正确的 key（可能是复合 key）
            panel_key = self.tab_manager._panel_to_key.get(id(panel))
            if panel_key:
                self.tab_manager.close_file(panel_key)

    def _on_close_all(self):
        """关闭所有标签页"""
        # 只关闭主文件标签页（不含 ::），数据集标签页会被级联关闭
        main_keys = [k for k in self.tab_manager.get_all_paths() if "::" not in k]
        for key in main_keys:
            self.tab_manager.close_file(key)

    def _on_panel_changed(self, panel_name: str):
        """切换面板"""
        if panel_name == "explorer":
            self._show_sidebar(0)
        elif panel_name == "search":
            self._show_sidebar(1)
        else:
            self.sidebar.hide()

    def _show_sidebar(self, tab_index: int):
        """显示侧边栏并切换标签"""
        self.sidebar.show()
        self.sidebar_tabs.setCurrentIndex(tab_index)

    def _toggle_bottom_panel(self):
        """切换底部面板显示"""
        if self.bottom_panel.isVisible():
            self.bottom_panel.hide()
        else:
            self.bottom_panel.show()

    def _on_node_double_clicked(self, path: str):
        """节点双击 — 在当前面板显示数据集"""
        # 优先从当前 panel 获取 source，否则从 explorer 获取（browse 模式）
        source = None
        panel = self.tab_manager.get_current_panel()
        if panel:
            source = panel.get_source()

        if source is None:
            source = self.explorer.get_source()

        if not source:
            return

        try:
            meta = source.get_metadata(path)
            if meta.node_type.value == "dataset":
                if panel:
                    panel.show_dataset(path, meta)
                else:
                    # browse 模式：双击数据集直接在新标签页打开
                    file_path = self.explorer.tree._loaded_file_path
                    if file_path:
                        self.tab_manager.open_dataset_tab(file_path, path, source, meta)

                self._event_bus.emit(EventBus.NODE_SELECTED, {
                    'path': path,
                    'meta': meta
                })
        except Exception as e:
            self._event_bus.emit(EventBus.ERROR_OCCURRED, f"Error loading {path}: {e}")

    def _on_open_in_new_tab(self, path: str):
        """在新标签页中打开数据集"""
        # 优先从当前 panel 获取 source，否则从 explorer 获取（browse 模式）
        source = None
        file_path = None

        current_panel = self.tab_manager.get_current_panel()
        if current_panel:
            source = current_panel.get_source()
            file_path = current_panel.get_path()

        if source is None:
            source = self.explorer.get_source()
            file_path = self.explorer.tree._loaded_file_path

        if not source or not file_path:
            return

        try:
            meta = source.get_metadata(path)
            if meta.node_type.value != "dataset":
                return

            self.tab_manager.open_dataset_tab(file_path, path, source, meta)

            self._event_bus.emit(EventBus.NODE_SELECTED, {
                'path': path,
                'meta': meta
            })

        except Exception as e:
            self._event_bus.emit(EventBus.ERROR_OCCURRED, f"Error opening {path}: {e}")

    def _on_search_result_clicked(self, path: str):
        """搜索结果点击"""
        panel = self.tab_manager.get_current_panel()
        if not panel:
            return

        source = panel.get_source()
        try:
            meta = source.get_metadata(path)
            if meta.node_type.value == "dataset":
                panel.show_dataset(path, meta)
                self._event_bus.emit(EventBus.NODE_SELECTED, {
                    'path': path,
                    'meta': meta
                })
        except Exception as e:
            self._event_bus.emit(EventBus.ERROR_OCCURRED, f"Error loading {path}: {e}")

    def _on_export_csv(self):
        """导出 CSV"""
        panel = self.tab_manager.get_current_panel()
        if not panel:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export as CSV", "", "CSV Files (*.csv)"
        )

        if file_path:
            from services.exporter import DataExporter
            import numpy as np

            # 获取当前显示的数据（从 FilePanel 获取）
            try:
                # 获取当前切片的数据
                source = panel.get_source()
                current_path = panel.get_current_node()
                if not current_path:
                    self.status_bar.set_message("No dataset selected")
                    return

                meta = source.get_metadata(current_path)
                from core.slicer import SliceParser
                slices = SliceParser.default_slice(meta.shape)
                data = source.read_slice(current_path, slices)

                if DataExporter.to_csv(data, file_path):
                    self.status_bar.set_message(f"Exported to {file_path}")
                else:
                    self.status_bar.set_message("Export failed")
            except Exception as e:
                self.status_bar.set_message(f"Export error: {e}")

    def _on_file_opened(self, file_path: str):
        """文件打开后"""
        self.status_bar.set_message(f"Opened: {file_path}")

    def _on_file_closed(self, panel_key: str):
        """文件/数据集标签页关闭后

        如果关闭的是主文件标签页，且该文件正是 Explorer 当前显示的，
        清除 Explorer 的已加载文件记录。
        """
        if "::" not in panel_key:
            # 主文件标签页关闭
            if self.explorer.tree._loaded_file_path == panel_key:
                self.explorer.clear_loaded_file()

    def _on_open_folder(self):
        """打开文件夹"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Open Folder", ""
        )
        if folder_path:
            self._open_folder(folder_path)

    def _open_folder(self, folder_path: str):
        """打开文件夹并显示在侧边栏"""
        self.folder_explorer.open_folder(folder_path)
        self.status_bar.set_message(f"Opened folder: {folder_path}")
        self._event_bus.emit(EventBus.FOLDER_OPENED, {'path': folder_path})

    def _on_close_folder(self):
        """关闭文件夹"""
        self.folder_explorer.close_folder()
        self._event_bus.emit(EventBus.FOLDER_CLOSED, None)

    def _on_tab_activated(self, file_path: str):
        """标签页激活时更新侧边栏"""
        self._update_explorer_for_file(file_path)
        self._event_bus.emit(EventBus.FILE_TAB_ACTIVATED, {'path': file_path})



    def _on_error(self, event):
        """错误处理"""
        error_msg = event.data if isinstance(event.data, str) else str(event.data)
        self.status_bar.set_message(f"Error: {error_msg}")

    def _on_attr_double_clicked(self, attr_name: str, attr_value) -> None:
        """属性行双击 — 在新标签页中打开属性值

        从 Explorer 或当前面板获取文件路径和数据集路径。
        """
        # 获取文件路径和数据集路径
        file_path = self.explorer.tree._loaded_file_path
        if not file_path:
            return

        # 尝试获取当前数据集路径
        dataset_path = "/"
        panel = self.tab_manager.get_current_panel()
        if panel and hasattr(panel, 'get_current_node'):
            current_node = panel.get_current_node()
            if current_node:
                dataset_path = current_node

        self.tab_manager.open_attr_tab(file_path, dataset_path, attr_name, attr_value)

    def _on_about(self):
        """关于"""
        QMessageBox.about(
            self, "About HDF5 Viewer",
            "HDF5 Viewer v0.1.0\n\n"
            "A lightweight HDF5 file viewer\n"
            "with VSCode-style interface.\n\n"
            "Features:\n"
            "- Multi-tab with Split\n"
            "- Large file lazy loading\n"
            "- Data export to CSV\n"
            "- Plugin system (extensible)"
        )

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path:
                if os.path.isdir(file_path):
                    self._open_folder(file_path)
                else:
                    self.open_file(file_path)

    def closeEvent(self, event):
        main_keys = [k for k in self.tab_manager.get_all_paths() if "::" not in k]
        for key in main_keys:
            self.tab_manager.close_file(key)
        event.accept()
