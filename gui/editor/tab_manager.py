"""TabManager — 标签页管理（VSCode 风格，支持 Split）"""

from PyQt6.QtWidgets import (QTabWidget, QTabBar, QWidget, QVBoxLayout,
                              QHBoxLayout, QApplication, QMainWindow,
                              QMenu, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QMouseEvent, QAction

from core.datasource import DataSource, DataMeta
from core.registry import DataSourceRegistry
from core.event_bus import EventBus
from .file_panel import FilePanel
from .attr_panel import AttrPanel

import os


class DraggableTabBar(QTabBar):
    """可拖拽的标签栏"""

    tab_dragged_out = pyqtSignal(int)  # 标签被拖出的索引

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos = None
        self._drag_tab_index = -1

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            self._drag_tab_index = self.tabAt(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start_pos and self._drag_tab_index >= 0:
            distance = (event.pos() - self._drag_start_pos).manhattanLength()
            if distance > 20:
                tab_rect = self.tabRect(self._drag_tab_index)
                if not tab_rect.contains(event.pos()):
                    self.tab_dragged_out.emit(self._drag_tab_index)
                    self._drag_start_pos = None
                    self._drag_tab_index = -1
                    return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_start_pos = None
        self._drag_tab_index = -1
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        """右键菜单"""
        index = self.tabAt(event.pos())
        if index < 0:
            return

        menu = QMenu(self)

        # Split Right
        split_right = QAction("Split Right", self)
        split_right.triggered.connect(lambda: self._split_tab(index, Qt.Orientation.Horizontal))
        menu.addAction(split_right)

        # Split Down
        split_down = QAction("Split Down", self)
        split_down.triggered.connect(lambda: self._split_tab(index, Qt.Orientation.Vertical))
        menu.addAction(split_down)

        menu.addSeparator()

        # Close
        close_action = QAction("Close", self)
        close_action.triggered.connect(lambda: self._close_tab(index))
        menu.addAction(close_action)

        # Close Others
        close_others = QAction("Close Others", self)
        close_others.triggered.connect(lambda: self._close_other_tabs(index))
        menu.addAction(close_others)

        # Close All
        close_all = QAction("Close All", self)
        close_all.triggered.connect(self._close_all_tabs)
        menu.addAction(close_all)

        menu.exec(event.globalPos())

    def _split_tab(self, index: int, orientation: Qt.Orientation) -> None:
        """分割标签页"""
        parent = self.parent()
        if isinstance(parent, TabManager):
            parent.split_tab(index, orientation)

    def _close_tab(self, index: int) -> None:
        """关闭标签页"""
        parent = self.parent()
        if isinstance(parent, TabManager):
            parent.tabCloseRequested.emit(index)

    def _close_other_tabs(self, keep_index: int) -> None:
        """关闭其他标签页"""
        parent = self.parent()
        if isinstance(parent, TabManager):
            for i in range(parent.count() - 1, -1, -1):
                if i != keep_index:
                    parent.tabCloseRequested.emit(i)

    def _close_all_tabs(self) -> None:
        """关闭所有标签页"""
        parent = self.parent()
        if isinstance(parent, TabManager):
            for i in range(parent.count() - 1, -1, -1):
                parent.tabCloseRequested.emit(i)


class TabManager(QWidget):
    """标签页管理器，支持 Split"""

    file_opened = pyqtSignal(str)
    file_closed = pyqtSignal(str)
    tab_activated = pyqtSignal(str)  # file_path — 标签页激活时发出文件路径

    def __init__(self, parent=None):
        super().__init__(parent)
        self._event_bus = EventBus.get_instance()

        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 使用 QSplitter 支持 Split
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self._splitter)

        # 创建第一个标签页组
        self._tab_groups: list[QTabWidget] = []
        self._create_tab_group()

        # 文件路径到标签页的映射
        self._panels: dict[str, FilePanel] = {}
        self._file_to_group: dict[str, int] = {}
        # 反向映射：panel 对象 -> key，用于通过 panel 快速查找 key
        self._panel_to_key: dict[int, str] = {}  # id(panel) -> key

    def _create_tab_group(self) -> QTabWidget:
        """创建新的标签页组"""
        tab_widget = QTabWidget()
        tab_widget.setTabBar(DraggableTabBar(tab_widget))
        tab_widget.setTabsClosable(True)
        tab_widget.setMovable(True)
        tab_widget.setDocumentMode(True)

        # 样式
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #969696;
                padding: 8px 16px;
                margin-right: 1px;
                border: none;
                min-width: 100px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QTabBar::tab:hover {
                background-color: #383838;
            }
        """)

        # 信号连接
        tab_widget.tabCloseRequested.connect(lambda idx, tw=tab_widget: self._on_tab_close(tw, idx))
        tab_widget.currentChanged.connect(lambda idx, tw=tab_widget: self._on_tab_changed(tw, idx))

        self._tab_groups.append(tab_widget)
        self._splitter.addWidget(tab_widget)

        return tab_widget

    def open_file(self, file_path: str) -> bool:
        """打开文件"""
        if file_path in self._panels:
            # 已经打开，切换到该标签
            self._focus_panel(file_path)
            return True

        try:
            source = DataSourceRegistry.get(file_path)
            source.open(file_path)

            panel = FilePanel(source, self)

            # 添加到当前活动的标签页组
            tab_widget = self._get_active_tab_group()
            tab_name = os.path.basename(file_path)
            idx = tab_widget.addTab(panel, tab_name)
            tab_widget.setCurrentIndex(idx)

            self._panels[file_path] = panel
            self._panel_to_key[id(panel)] = file_path
            self._file_to_group[file_path] = self._tab_groups.index(tab_widget)

            self.file_opened.emit(file_path)
            self._event_bus.emit(EventBus.FILE_OPENED, {
                'path': file_path,
                'source': source,
                'panel': panel
            })

            return True

        except Exception as e:
            self._event_bus.emit(EventBus.ERROR_OCCURRED, f"Failed to open {file_path}: {e}")
            return False

    def close_file(self, panel_key: str) -> None:
        """关闭文件（或数据集标签页）

        关闭主文件标签页时，会同时关闭该文件的所有数据集标签页。
        关闭数据集标签页时，不关闭共享的数据源。

        Args:
            panel_key: 主文件标签页用 file_path，数据集标签页用 file_path::dataset_path
        """
        if panel_key not in self._panels:
            return

        # 如果关闭的是主文件标签页，先关闭该文件的所有数据集标签页
        if "::" not in panel_key:
            # 收集属于该文件的所有数据集标签页 key
            dataset_keys = [k for k in list(self._panels.keys())
                           if k.startswith(f"{panel_key}::")]
            for dk in dataset_keys:
                # 递归关闭数据集标签页（不会关闭 source）
                self.close_file(dk)

        if panel_key not in self._panels:
            return

        panel = self._panels[panel_key]

        # 找到并从标签页组中移除
        for i, tab_widget in enumerate(self._tab_groups):
            idx = tab_widget.indexOf(panel)
            if idx >= 0:
                tab_widget.removeTab(idx)
                break

        # 只有主文件标签页关闭时才关闭数据源
        # 数据集标签页（复合 key 含 ::）和属性标签页（含 ::attr::）共享数据源，不关闭
        if "::" not in panel_key:
            if hasattr(panel, 'get_source'):
                panel.get_source().close()

        del self._panels[panel_key]
        if id(panel) in self._panel_to_key:
            del self._panel_to_key[id(panel)]
        if panel_key in self._file_to_group:
            del self._file_to_group[panel_key]

        self.file_closed.emit(panel_key)
        self._event_bus.emit(EventBus.FILE_CLOSED, panel_key)

    def split_tab(self, index: int, orientation: Qt.Orientation) -> None:
        """分割标签页"""
        # 找到源标签页组
        source_group = None
        for tab_widget in self._tab_groups:
            if index < tab_widget.count():
                source_group = tab_widget
                break
            index -= tab_widget.count()

        if source_group is None:
            return

        # 获取要分割的面板
        panel = source_group.widget(index)
        if not isinstance(panel, (FilePanel, AttrPanel)):
            return

        # 找到该 panel 的 key
        panel_key = self._panel_to_key.get(id(panel))
        if not panel_key:
            return

        # 从源组移除
        source_group.removeTab(index)

        # 创建新的标签页组
        new_group = self._create_tab_group()

        # 设置分割方向
        if orientation == Qt.Orientation.Horizontal:
            self._splitter.setOrientation(Qt.Orientation.Horizontal)
        else:
            self._splitter.setOrientation(Qt.Orientation.Vertical)

        # 添加到新组
        tab_name = source_group.tabText(index)
        new_group.addTab(panel, tab_name)

        # 更新映射
        self._file_to_group[panel_key] = self._tab_groups.index(new_group)
    def _on_tab_close(self, tab_widget: QTabWidget, index: int) -> None:
        """标签关闭请求"""
        panel = tab_widget.widget(index)
        # 通过反向映射找到 key（支持 FilePanel 和 AttrPanel）
        panel_key = self._panel_to_key.get(id(panel))
        if panel_key:
            self.close_file(panel_key)

    def _on_tab_changed(self, tab_widget: QTabWidget, index: int) -> None:
        """标签切换"""
        if index < 0:
            return
        panel = tab_widget.widget(index)
        if isinstance(panel, FilePanel):
            self._event_bus.emit(EventBus.FILE_OPENED, {
                'path': panel.get_path(),
                'source': panel.get_source(),
                'panel': panel
            })
            self.tab_activated.emit(panel.get_path())
        elif isinstance(panel, AttrPanel):
            # 属性标签页激活，不需要特殊处理
            pass

    def _get_active_tab_group(self) -> QTabWidget:
        """获取当前活动的标签页组"""
        # 返回最后一个标签页组
        return self._tab_groups[-1]

    def _focus_panel(self, file_path: str) -> None:
        """聚焦到指定文件的面板"""
        if file_path not in self._panels:
            return

        panel = self._panels[file_path]
        for tab_widget in self._tab_groups:
            idx = tab_widget.indexOf(panel)
            if idx >= 0:
                tab_widget.setCurrentIndex(idx)
                return

    def get_current_panel(self) -> FilePanel | AttrPanel | None:
        """获取当前文件面板"""
        for tab_widget in self._tab_groups:
            panel = tab_widget.currentWidget()
            if isinstance(panel, (FilePanel, AttrPanel)):
                return panel
        return None

    def get_all_paths(self) -> list[str]:
        """获取所有打开的文件路径"""
        return list(self._panels.keys())

    def open_dataset_tab(self, file_path: str, dataset_path: str,
                         source: DataSource, meta: DataMeta) -> None:
        """为同一文件的数据集打开新的标签页

        创建一个新的 FilePanel 并注册到 TabManager 的所有内部映射中，
        确保关闭、切换、分割等操作都能正确识别该标签页。

        Args:
            file_path: HDF5 文件路径（主文件标签页的 key）
            dataset_path: 数据集在 HDF5 文件中的路径（如 /group/dataset）
            source: 数据源（与主文件标签页共享）
            meta: 数据集元信息
        """
        # 创建新的 FilePanel（共享同一个数据源）
        new_panel = FilePanel(source, self)

        # 添加到当前活动的标签页组
        tab_widget = self._get_active_tab_group()
        tab_name = dataset_path.split("/")[-1] or dataset_path
        idx = tab_widget.addTab(new_panel, tab_name)
        tab_widget.setCurrentIndex(idx)

        # 使用复合 key 注册到 _panels
        panel_key = f"{file_path}::{dataset_path}"
        self._panels[panel_key] = new_panel
        self._panel_to_key[id(new_panel)] = panel_key
        self._file_to_group[panel_key] = self._tab_groups.index(tab_widget)

        # 显示数据
        new_panel.show_dataset(dataset_path, meta)

    def open_attr_tab(self, file_path: str, dataset_path: str,
                       attr_name: str, attr_value) -> None:
        """为 HDF5 属性打开新的标签页

        创建一个 AttrPanel 以只读表格形式显示属性值。
        使用复合 key: file_path::attr::dataset_path::attr_name

        Args:
            file_path: HDF5 文件路径
            dataset_path: 数据集路径
            attr_name: 属性名
            attr_value: 属性原始值（任意类型）
        """
        # 如果已经打开，切换过去
        panel_key = f"{file_path}::attr::{dataset_path}::{attr_name}"
        if panel_key in self._panels:
            self._focus_panel(panel_key)
            return

        # 创建 AttrPanel
        attr_panel = AttrPanel(attr_name, attr_value, self)

        # 添加到当前活动的标签页组
        tab_widget = self._get_active_tab_group()
        tab_name = f"{attr_name} @ {dataset_path.split('/')[-1] or dataset_path}"
        idx = tab_widget.addTab(attr_panel, tab_name)
        tab_widget.setCurrentIndex(idx)

        # 注册到 _panels（AttrPanel 也存入，但关闭时不关 source）
        self._panels[panel_key] = attr_panel
        self._panel_to_key[id(attr_panel)] = panel_key
        self._file_to_group[panel_key] = self._tab_groups.index(tab_widget)
