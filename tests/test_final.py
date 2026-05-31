#!/usr/bin/env python3
"""最终完整测试"""

import sys
import os
import tempfile
import numpy as np
import h5py

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
app = QApplication([])

# 测试核心模块
from core.event_bus import EventBus
from core.datasource import DataSource, DataMeta, NodeType
from core.h5_source import H5Source
from core.slicer import SliceParser
from core.cache import LRUCache
from core.registry import DataSourceRegistry, PluginManager
print("[OK] Core modules imported")

# 测试 GUI 模块
from gui.main_window import MainWindow
from gui.activity_bar import ActivityBar
from gui.sidebar.explorer import ExplorerPanel
from gui.editor.tab_manager import TabManager
from gui.editor.file_panel import FilePanel, SliceInput
from gui.editor.data_table import DataTable
from gui.status_bar import StatusBar
from gui.bottom_panel import BottomPanel
print("[OK] GUI modules imported")

# 测试服务模块
from services.search import SearchPanel
from services.exporter import DataExporter
print("[OK] Service modules imported")

# 测试插件模块
from plugins.base import SourcePlugin, AnalyzePlugin, VisualizePlugin
from plugins.builtin.statistics import StatisticsPlugin
from plugins.builtin.histogram import HistogramPlugin
from plugins.builtin.line_chart import LineChartPlugin
from plugins.builtin.heatmap import HeatmapPlugin
print("[OK] Plugin modules imported")


def create_test_hdf5(path: str) -> None:
    """创建测试用的 HDF5 文件"""
    with h5py.File(path, 'w') as f:
        grp = f.create_group('data')
        grp.create_dataset('temperature', data=np.random.randn(100, 50))
        grp.create_dataset('pressure', data=np.random.randn(100, 50))
        ds = grp.create_dataset('coordinates', data=np.random.randn(3, 1000))
        ds.attrs['units'] = 'meters'
        ds.attrs['description'] = '3D coordinates'
        f.create_dataset('labels', data=[b'label1', b'label2', b'label3'])


def test_core_functionality():
    """测试核心功能"""
    print("\n=== Testing Core Functionality ===")

    # EventBus
    bus = EventBus.get_instance()
    results = []
    bus.on(EventBus.FILE_OPENED, lambda e: results.append(e.data))
    bus.emit(EventBus.FILE_OPENED, "test.h5")
    assert len(results) == 1
    print("[OK] EventBus")

    # SliceParser
    s = SliceParser.parse("[0:100, 10:20]", (1000, 500))
    assert s == (slice(0, 100), slice(10, 20))
    print("[OK] SliceParser")

    # LRUCache
    cache = LRUCache(max_size_mb=1)
    data = np.random.randn(1000)
    cache.put("test", data)
    assert np.array_equal(cache.get("test"), data)
    print("[OK] LRUCache")

    # H5Source
    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        temp_path = f.name

    try:
        create_test_hdf5(temp_path)

        source = H5Source()
        source.open(temp_path)

        tree = source.get_tree()
        assert tree.name == os.path.basename(temp_path)

        meta = source.get_metadata('/data/temperature')
        assert meta.shape == (100, 50)

        data = source.read_slice('/data/temperature', (slice(0, 10), slice(0, 5)))
        assert data.shape == (10, 5)

        attrs = source.get_attrs('/data/coordinates')
        assert 'units' in attrs

        results = source.search('temperature')
        assert len(results) > 0

        source.close()
        print("[OK] H5Source")

    finally:
        os.unlink(temp_path)


def test_plugins():
    """测试插件系统"""
    print("\n=== Testing Plugin System ===")

    # 注册插件
    PluginManager.load_builtin_plugins()

    # 检查插件注册
    analyzers = PluginManager.get_analyzers()
    visualizers = PluginManager.get_visualizers()
    assert len(analyzers) >= 1
    assert len(visualizers) >= 3
    print(f"[OK] Plugin registration: {len(analyzers)} analyzers, {len(visualizers)} visualizers")

    # 测试 Statistics 插件
    stats = StatisticsPlugin()
    test_data = np.random.randn(1000)
    meta = DataMeta(path="/test", name="test", shape=(1000,), dtype='float64')
    result = stats.run(test_data, meta)
    assert result['result'] is not None
    assert 'mean' in result['result']
    print("[OK] StatisticsPlugin")

    # 测试可视化插件匹配
    matching = PluginManager.get_matching_visualizers((1000,), 'float64')
    assert len(matching) >= 2  # LineChart + Histogram
    print(f"[OK] Visualizer matching: {[p.name for p in matching]}")


def test_data_export():
    """测试数据导出"""
    print("\n=== Testing Data Export ===")

    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
        csv_path = f.name

    try:
        data = np.random.randn(10, 5)
        success = DataExporter.to_csv(data, csv_path)
        assert success
        assert os.path.exists(csv_path)
        print("[OK] CSV Export")
    finally:
        os.unlink(csv_path)


def main():
    """运行所有测试"""
    print("=" * 60)
    print("HDF5 Viewer - Final Integration Tests")
    print("=" * 60)

    test_core_functionality()
    test_plugins()
    test_data_export()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
