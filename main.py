#!/usr/bin/env python3
"""HDF5 Viewer — 主入口"""

import sys
import json
import os
from pathlib import Path

# 添加项目根目录到 path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def load_config() -> dict:
    """加载配置文件

    兼容开发模式和 PyInstaller 打包模式：
    - 开发模式：config.json 在项目根目录
    - 打包模式：config.json 在 sys._MEIPASS 目录
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包模式
        base_path = Path(sys._MEIPASS)
    else:
        # 开发模式
        base_path = project_root

    config_path = base_path / "config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def main():
    """主函数"""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    # 高 DPI 支持
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'

    app = QApplication(sys.argv)
    app.setApplicationName("HDF5 Viewer")
    app.setApplicationVersion("0.1.0")

    # 加载配置
    config = load_config()

    # 加载内置插件
    from core.registry import PluginManager
    PluginManager.load_builtin_plugins()

    # 创建主窗口
    from gui.main_window import MainWindow
    window = MainWindow(config)
    window.show()

    # 命令行参数：直接打开文件
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            window.open_file(file_path)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
