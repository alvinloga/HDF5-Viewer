"""SecondaryPanel — 右侧面板容器（Search + Plugins）"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget)
from PyQt6.QtCore import Qt

from services.search import SearchPanel
from gui.sidebar.plugin_panel import PluginPanel

from .theme import get_theme_colors


class SecondaryPanel(QWidget):
    """右侧面板 — Search + Plugins 标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)

        self.search_panel = SearchPanel()
        self.tabs.addTab(self.search_panel, "Search")

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
        colors = get_theme_colors(theme)
        self.setStyleSheet(f"background-color: {colors['bg_secondary']};")
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: {colors['bg_secondary']};
            }}
            QTabBar::tab {{
                background-color: {colors['bg_tab']};
                color: {colors['text_secondary']};
                padding: 6px 12px;
                margin-right: 1px;
                border: none;
            }}
            QTabBar::tab:selected {{
                background-color: {colors['bg_secondary']};
                color: {colors['text_selected']};
            }}
            QTabBar::tab:hover {{
                background-color: {colors['bg_tab_hover']};
            }}
        """)
        self.plugin_panel.apply_theme(theme)
