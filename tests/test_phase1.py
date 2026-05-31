#!/usr/bin/env python3
"""Phase 1 完整测试"""

import sys
import os
import tempfile
import numpy as np
import h5py

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
app = QApplication([])

from core.event_bus import EventBus
from core.h5_source import H5Source
from core.registry import DataSourceRegistry
from gui.editor.tab_manager import TabManager
from gui.editor.file_panel import FilePanel, SliceInput
from gui.editor.data_table import DataTable, DataTablePanel
from gui.sidebar.explorer import ExplorerPanel, ExplorerTree
from gui.status_bar import StatusBar


def create_test_hdf5(path: str) -> None:
    """创建测试用的 HDF5 文件"""
    with h5py.File(path, 'w') as f:
        grp = f.create_group('data')
        grp.create_dataset('temperature', data=np.random.randn(100, 50))
        grp.create_dataset('pressure', data=np.random.randn(100, 50))
        ds = grp.create_dataset('coordinates', data=np.random.randn(3, 1000))
        ds.attrs['units'] = 'meters'
        f.create_dataset('labels', data=[b'label1', b'label2', b'label3'])


def test_tab_manager():
    """测试 TabManager"""
    print("Testing TabManager...")

    DataSourceRegistry.register(H5Source)

    tab_mgr = TabManager()

    # 创建临时文件
    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        temp_path = f.name

    try:
        create_test_hdf5(temp_path)

        # 测试打开文件
        success = tab_mgr.open_file(temp_path)
        assert success, "Failed to open file"

        # 测试获取当前面板
        panel = tab_mgr.get_current_panel()
        assert panel is not None, "No current panel"

        # 测试获取所有路径
        paths = tab_mgr.get_all_paths()
        assert len(paths) == 1
        assert paths[0] == temp_path

        # 测试关闭文件
        tab_mgr.close_file(temp_path)
        assert len(tab_mgr.get_all_paths()) == 0

        print("  TabManager: OK")

    finally:
        os.unlink(temp_path)


def test_explorer():
    """测试 Explorer"""
    print("Testing ExplorerPanel...")

    explorer = ExplorerPanel()

    # 创建临时文件并加载
    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        temp_path = f.name

    try:
        create_test_hdf5(temp_path)

        source = H5Source()
        source.open(temp_path)
        tree = source.get_tree()

        explorer.load_tree(tree, temp_path)
        print("  ExplorerPanel: OK")

        source.close()
    finally:
        os.unlink(temp_path)


def test_slice_input():
    """测试 SliceInput"""
    print("Testing SliceInput...")

    slice_input = SliceInput()
    slice_input.set_shape_hint((1000, 500))
    print("  SliceInput: OK")


def test_data_table():
    """测试 DataTable"""
    print("Testing DataTable...")

    table = DataTable()

    # 测试 1D 数据
    data_1d = np.random.randn(100)
    table.load_data(data_1d)
    # 使用模型获取行数
    assert table.model().rowCount() == 100

    # 测试 2D 数据
    data_2d = np.random.randn(50, 30)
    table.load_data(data_2d)
    assert table.model().rowCount() == 50
    assert table.model().columnCount() == 30

    print("  DataTable: OK")


def test_status_bar():
    """测试 StatusBar"""
    print("Testing StatusBar...")

    status_bar = StatusBar()
    status_bar.set_message("Test message")
    print("  StatusBar: OK")


def main():
    """运行所有测试"""
    print("=" * 50)
    print("HDF5 Viewer - Phase 1 Tests")
    print("=" * 50)

    test_tab_manager()
    test_explorer()
    test_slice_input()
    test_data_table()
    test_status_bar()

    print("=" * 50)
    print("All Phase 1 tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
