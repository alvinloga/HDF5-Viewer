"""SecondaryPanel — 右侧面板容器（Search + Plugins）"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget)
from PyQt6.QtCore import Qt

from services.search import SearchPanel
from gui.sidebar.plugin_panel import PluginPanel


class SecondaryPanel(QWidget):
    """右侧面板 — Search + Plugins 标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Width is set by MainWindow from config
        self.setStyleSheet("background-color: #252526;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #252526;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #969696;
                padding: 6px 12px;
                margin-right: 1px;
                border: none;
            }
            QTabBar::tab:selected {
                background-color: #252526;
                color: #ffffff;
            }
            QTabBar::tab:hover {
                background-color: #383838;
            }
        """)

        # Search 面板
        self.search_panel = SearchPanel()
        self.tabs.addTab(self.search_panel, "Search")

        # Plugins 面板
        self.plugin_panel = PluginPanel()
        self.tabs.addTab(self.plugin_panel, "Plugins")

        layout.addWidget(self.tabs)

    def show_search(self):
        self.show()
        self.tabs.setCurrentIndex(0)

    def show_plugins(self):
        self.show()
        self.tabs.setCurrentIndex(1)

    def get_search_panel(self) -> SearchPanel:
        return self.search_panel

    def get_plugin_panel(self) -> PluginPanel:
        return self.plugin_panel

    def apply_theme(self, theme: str):
        """根据主题切换样式"""
        if theme == "light":
            self.setStyleSheet("background-color: #f3f3f3;")
            self.tabs.setStyleSheet("""
                QTabWidget::pane {
                    border: none;
                    background-color: #f3f3f3;
                }
                QTabBar::tab {
                    background-color: #e8e8e8;
                    color: #666666;
                    padding: 6px 12px;
                    margin-right: 1px;
                    border: none;
                }
                QTabBar::tab:selected {
                    background-color: #f3f3f3;
                    color: #333333;
                }
                QTabBar::tab:hover {
                    background-color: #d8d8d8;
                }
            """)
        else:  # dark
            self.setStyleSheet("background-color: #252526;")
            self.tabs.setStyleSheet("""
                QTabWidget::pane {
                    border: none;
                    background-color: #252526;
                }
                QTabBar::tab {
                    background-color: #2d2d2d;
                    color: #969696;
                    padding: 6px 12px;
                    margin-right: 1px;
                    border: none;
                }
                QTabBar::tab:selected {
                    background-color: #252526;
                    color: #ffffff;
                }
                QTabBar::tab:hover {
                    background-color: #383838;
                }
            """)
