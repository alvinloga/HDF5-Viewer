"""TabManager — 标签页管理（VSCode 风格，支持 Split）"""

from PyQt6.QtWidgets import (QTabWidget, QTabBar, QWidget, QVBoxLayout,
                              QHBoxLayout, QApplication, QMainWindow,
                              QMenu, QSplitter, QLabel)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QMouseEvent, QAction

from core.datasource import DataSource, DataMeta
from core.registry import DataSourceRegistry
from core.event_bus import EventBus
from .file_panel import FilePanel
from .attr_panel import AttrPanel

from ..theme import get_theme_colors

import os


class DraggableTabBar(QTabBar):
    """可拖拽的标签栏"""

    tab_dragged_out = pyqtSignal(int)
    split_requested = pyqtSignal(int, object)
    close_requested = pyqtSignal(int)
    close_others_requested = pyqtSignal(int)
    close_all_requested = pyqtSignal()

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
        index = self.tabAt(event.pos())
        if index < 0:
            return

        menu = QMenu(self)

        split_right = QAction("Split Right", self)
        split_right.triggered.connect(lambda: self.split_requested.emit(index, Qt.Orientation.Horizontal))
        menu.addAction(split_right)

        split_down = QAction("Split Down", self)
        split_down.triggered.connect(lambda: self.split_requested.emit(index, Qt.Orientation.Vertical))
        menu.addAction(split_down)

        menu.addSeparator()

        close_action = QAction("Close", self)
        close_action.triggered.connect(lambda: self.close_requested.emit(index))
        menu.addAction(close_action)

        close_others = QAction("Close Others", self)
        close_others.triggered.connect(lambda: self.close_others_requested.emit(index))
        menu.addAction(close_others)

        close_all = QAction("Close All", self)
        close_all.triggered.connect(self.close_all_requested.emit)
        menu.addAction(close_all)

        menu.exec(event.globalPos())


class DetachedWindow(QMainWindow):
    """拖拽出去的独立窗口

    关键：不在此窗口级别设置全局 stylesheet。
    QApplication 级别的全局样式（由 MainWindow._apply_style 设置）
    会自动传播到所有顶级窗口的子组件。
    子组件通过各自的 apply_theme() 设置更具体的样式。
    """

    closed = pyqtSignal(str)

    def __init__(self, widget, panel_key: str, title: str = "", theme: str = "dark"):
        super().__init__()
        self._panel_key = panel_key
        self._theme = theme
        self.setWindowTitle(title or "HDF5 Viewer - Detached")
        self.resize(800, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        colors = get_theme_colors(theme)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(widget)
        self.setCentralWidget(container)

        # 显式刷新所有子组件的主题样式
        if hasattr(widget, 'apply_theme'):
            widget.apply_theme(theme)

        # 确保窗口本身背景色正确
        from PyQt6.QtGui import QPalette, QColor
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(colors['bg_primary']))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(colors['text_primary']))
        pal.setColor(QPalette.ColorRole.Base, QColor(colors['bg_primary']))
        pal.setColor(QPalette.ColorRole.Text, QColor(colors['text_primary']))
        self.setPalette(pal)
        self.setAutoFillBackground(True)

    def closeEvent(self, event):
        self.closed.emit(self._panel_key)
        event.accept()


class TabManager(QWidget):
    """标签页管理器，支持 Split"""

    file_opened = pyqtSignal(str)
    file_closed = pyqtSignal(str)
    tab_activated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._event_bus = EventBus.get_instance()
        self._detached_windows: list[DetachedWindow] = []
        self._theme: str = "dark"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self._splitter)

        self._tab_groups: list[QTabWidget] = []
        self._create_tab_group()

        self._panels: dict[str, FilePanel] = {}
        self._file_to_group: dict[str, int] = {}
        self._panel_to_key: dict[int, str] = {}

    def _create_tab_group(self, add_to_splitter: bool = True) -> QTabWidget:
        tab_widget = QTabWidget()
        tab_widget.setTabBar(DraggableTabBar(tab_widget))
        tab_widget.setTabsClosable(True)
        tab_widget.setMovable(True)
        tab_widget.setDocumentMode(True)

        tab_widget.tabCloseRequested.connect(lambda idx, tw=tab_widget: self._on_tab_close(tw, idx))
        tab_widget.currentChanged.connect(lambda idx, tw=tab_widget: self._on_tab_changed(tw, idx))
        tab_widget.tabBar().tab_dragged_out.connect(
            lambda idx, tw=tab_widget: self._on_drag_disabled(tw, idx))

        tab_bar = tab_widget.tabBar()
        tab_bar.split_requested.connect(lambda idx, orient, tw=tab_widget: self._on_split_requested(tw, idx, orient))
        tab_bar.close_requested.connect(lambda idx, tw=tab_widget: self._on_tab_close(tw, idx))
        tab_bar.close_others_requested.connect(lambda idx, tw=tab_widget: self._on_close_others(tw, idx))
        tab_bar.close_all_requested.connect(lambda tw=tab_widget: self._on_close_all(tw))

        self._tab_groups.append(tab_widget)
        if add_to_splitter:
            self._splitter.addWidget(tab_widget)

        return tab_widget

    def open_file(self, file_path: str) -> bool:
        if file_path in self._panels:
            self._focus_panel(file_path)
            return True

        try:
            source = DataSourceRegistry.get(file_path)
            source.open(file_path)

            panel = FilePanel(source, self)

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
        if panel_key not in self._panels:
            return

        if "::" not in panel_key:
            dataset_keys = [k for k in list(self._panels.keys())
                           if k.startswith(f"{panel_key}::")]
            for dk in dataset_keys:
                self.close_file(dk)

        if panel_key not in self._panels:
            return

        panel = self._panels[panel_key]

        for i, tab_widget in enumerate(self._tab_groups):
            idx = tab_widget.indexOf(panel)
            if idx >= 0:
                tab_widget.removeTab(idx)
                break

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

    def _on_split_requested(self, tab_widget: QTabWidget, index: int, orientation: Qt.Orientation) -> None:
        panel = tab_widget.widget(index)
        if not isinstance(panel, (FilePanel, AttrPanel)):
            return
        panel_key = self._panel_to_key.get(id(panel))
        if not panel_key:
            return
        tab_name = tab_widget.tabText(index)
        tab_widget.removeTab(index)

        if orientation == Qt.Orientation.Horizontal:
            new_group = self._create_tab_group()
            new_group.addTab(panel, tab_name)
            self._file_to_group[panel_key] = self._tab_groups.index(new_group)
        elif orientation == Qt.Orientation.Vertical:
            splitter = self._splitter
            splitter_index = splitter.indexOf(tab_widget)

            tab_widget.setParent(None)

            v_splitter = QSplitter(Qt.Orientation.Vertical)
            v_splitter.setChildrenCollapsible(False)
            v_splitter.addWidget(tab_widget)

            new_group = self._create_tab_group(add_to_splitter=False)
            new_group.addTab(panel, tab_name)
            v_splitter.addWidget(new_group)
            v_splitter.setSizes([300, 300])

            splitter.insertWidget(splitter_index, v_splitter)

            self._file_to_group[panel_key] = self._tab_groups.index(new_group)

    def _on_close_others(self, tab_widget: QTabWidget, keep_index: int) -> None:
        for i in range(tab_widget.count() - 1, -1, -1):
            if i != keep_index:
                self._on_tab_close(tab_widget, i)

    def _on_close_all(self, tab_widget: QTabWidget) -> None:
        for i in range(tab_widget.count() - 1, -1, -1):
            self._on_tab_close(tab_widget, i)

    def _on_tab_close(self, tab_widget: QTabWidget, index: int) -> None:
        panel = tab_widget.widget(index)
        panel_key = self._panel_to_key.get(id(panel))
        if panel_key:
            self.close_file(panel_key)

    def _on_tab_changed(self, tab_widget: QTabWidget, index: int) -> None:
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

            current_node = panel.get_current_node()
            if current_node:
                source = panel.get_source()
                if source and source.is_open():
                    try:
                        meta = source.get_metadata(current_node)
                        self._event_bus.emit(EventBus.NODE_SELECTED, {
                            'path': current_node,
                            'meta': meta
                        })
                    except Exception:
                        pass
        elif isinstance(panel, AttrPanel):
            pass

    def _on_drag_disabled(self, tab_widget: QTabWidget, index: int) -> None:
        """标签页拖出已禁用 — 不执行任何操作"""
        pass

    def _on_detached_closed(self, panel_key: str) -> None:
        self._detached_windows = [
            w for w in self._detached_windows
            if w._panel_key != panel_key
        ]
        if panel_key in self._panels:
            self.close_file(panel_key)

    def _get_active_tab_group(self) -> QTabWidget:
        return self._tab_groups[-1]

    def _focus_panel(self, file_path: str) -> None:
        if file_path not in self._panels:
            return

        panel = self._panels[file_path]
        for tab_widget in self._tab_groups:
            idx = tab_widget.indexOf(panel)
            if idx >= 0:
                tab_widget.setCurrentIndex(idx)
                return

    def get_current_panel(self) -> FilePanel | AttrPanel | None:
        for tab_widget in self._tab_groups:
            panel = tab_widget.currentWidget()
            if isinstance(panel, (FilePanel, AttrPanel)):
                return panel
        return None

    def get_all_paths(self) -> list[str]:
        return list(self._panels.keys())

    def open_dataset_tab(self, file_path: str, dataset_path: str,
                         source: DataSource, meta: DataMeta) -> None:
        new_panel = FilePanel(source, self)

        tab_widget = self._get_active_tab_group()
        tab_name = dataset_path.split("/")[-1] or dataset_path
        idx = tab_widget.addTab(new_panel, tab_name)
        tab_widget.setCurrentIndex(idx)

        panel_key = f"{file_path}::{dataset_path}"
        self._panels[panel_key] = new_panel
        self._panel_to_key[id(new_panel)] = panel_key
        self._file_to_group[panel_key] = self._tab_groups.index(tab_widget)

        new_panel.show_dataset(dataset_path, meta)

    def open_attr_tab(self, file_path: str, dataset_path: str,
                       attr_name: str, attr_value) -> None:
        panel_key = f"{file_path}::attr::{dataset_path}::{attr_name}"
        if panel_key in self._panels:
            self._focus_panel(panel_key)
            return

        attr_panel = AttrPanel(attr_name, attr_value, self)

        tab_widget = self._get_active_tab_group()
        tab_name = f"{attr_name} @ {dataset_path.split('/')[-1] or dataset_path}"
        idx = tab_widget.addTab(attr_panel, tab_name)
        tab_widget.setCurrentIndex(idx)

        self._panels[panel_key] = attr_panel
        self._panel_to_key[id(attr_panel)] = panel_key
        self._file_to_group[panel_key] = self._tab_groups.index(tab_widget)

    def apply_theme(self, theme: str):
        self._theme = theme
        colors = get_theme_colors(theme)
        for tab_widget in self._tab_groups:
            tab_widget.setStyleSheet(f"""
                QTabWidget::pane {{
                    border: none;
                    background-color: {colors['bg_primary']};
                }}
                QTabBar::tab {{
                    background-color: {colors['bg_tab']};
                    color: {colors['text_secondary']};
                    padding: 8px 16px;
                    margin-right: 1px;
                    border: none;
                    min-width: 100px;
                }}
                QTabBar::tab:selected {{
                    background-color: {colors['bg_tab_selected']};
                    color: {colors['text_selected']};
                }}
                QTabBar::tab:hover {{
                    background-color: {colors['bg_tab_hover']};
                }}
            """)
        for panel in self._panels.values():
            if hasattr(panel, 'apply_theme'):
                panel.apply_theme(theme)
