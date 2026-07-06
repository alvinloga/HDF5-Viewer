#!/usr/bin/env python3
"""打包后功能测试"""

import sys
import os
import tempfile
import numpy as np
import h5py
import pytest
from pathlib import Path

# 设置项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_h5(tmp_path):
    """创建临时 HDF5 文件路径，测试结束后自动清理"""
    return str(tmp_path / "test.h5")


@pytest.fixture
def tmp_csv(tmp_path):
    """创建临时 CSV 文件路径，测试结束后自动清理"""
    return str(tmp_path / "test.csv")


# ── Helper ────────────────────────────────────────────────────────────────

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


# ── 测试 ──────────────────────────────────────────────────────────────────

def test_core_imports():
    """测试核心模块导入"""
    from core.event_bus import EventBus
    from core.datasource import DataSource, DataMeta, NodeType
    from core.h5_source import H5Source
    from core.slicer import SliceParser
    from core.cache import LRUCache
    from core.registry import DataSourceRegistry, PluginManager


def test_h5_operations(tmp_h5):
    """测试 HDF5 操作"""
    from core.h5_source import H5Source

    create_test_hdf5(tmp_h5)

    source = H5Source()
    source.open(tmp_h5)

    # 测试树结构
    tree = source.get_tree()
    assert tree.name == os.path.basename(tmp_h5)
    assert len(tree.children) > 0

    # 测试元数据
    meta = source.get_metadata('/data/temperature')
    assert meta.shape == (100, 50)
    assert meta.dtype == 'float64'

    # 测试数据读取
    data = source.read_slice('/data/temperature', (slice(0, 10), slice(0, 5)))
    assert data.shape == (10, 5)

    # 测试属性
    attrs = source.get_attrs('/data/coordinates')
    assert 'units' in attrs
    assert attrs['units'] == 'meters'

    # 测试搜索
    results = source.search('temperature')
    assert len(results) > 0

    source.close()


def test_slicer():
    """测试切片解析"""
    from core.slicer import SliceParser

    # 测试解析
    s = SliceParser.parse("[0:100, 10:20]", (1000, 500))
    assert s == (slice(0, 100), slice(10, 20))

    # 测试默认切片
    s = SliceParser.default_slice((5000, 100), max_rows=1000)
    assert s[0].stop == 1000

    # 测试字符串转换
    s_str = SliceParser.slice_to_str((slice(0, 100), slice(10, 20)))
    assert "0:100" in s_str


def test_cache():
    """测试缓存"""
    from core.cache import LRUCache

    cache = LRUCache(max_size_mb=1)

    # 存入数据
    data = np.random.randn(1000)
    cache.put("test_key", data)

    # 读取
    result = cache.get("test_key")
    assert result is not None
    assert np.array_equal(result, data)

    # 不存在的键
    assert cache.get("nonexistent") is None


def test_plugins():
    """测试插件系统"""
    from core.registry import PluginManager
    from plugins.base import AnalyzePlugin, VisualizePlugin
    from plugins.builtin.statistics import StatisticsPlugin
    from plugins.builtin.histogram import HistogramPlugin
    from plugins.builtin.line_chart import LineChartPlugin
    from plugins.builtin.heatmap import HeatmapPlugin
    from core.datasource import DataMeta

    # 加载内置插件
    PluginManager.load_builtin_plugins()

    # 检查插件注册
    analyzers = PluginManager.get_analyzers()
    visualizers = PluginManager.get_visualizers()
    assert len(analyzers) >= 1
    assert len(visualizers) >= 3

    # 测试 Statistics 插件
    stats = StatisticsPlugin()
    test_data = np.random.randn(1000)
    meta = DataMeta(path="/test", name="test", shape=(1000,), dtype='float64')
    result = stats.run(test_data, meta)
    assert result['result'] is not None
    assert 'mean' in result['result']

    # 测试可视化插件匹配
    matching = PluginManager.get_matching_visualizers((1000,), 'float64')
    assert len(matching) >= 2


def test_export(tmp_csv):
    """测试导出"""
    from services.exporter import DataExporter

    data = np.random.randn(10, 5)
    success = DataExporter.to_csv(data, tmp_csv)
    assert success
    assert os.path.exists(tmp_csv)

    # 验证 CSV 内容
    with open(tmp_csv, 'r') as f:
        lines = f.readlines()
        assert len(lines) == 11  # header + 10 rows


def test_event_bus():
    """测试事件总线"""
    from core.event_bus import EventBus

    bus = EventBus.get_instance()
    results = []

    def handler(event):
        results.append(event.data)

    bus.on(EventBus.FILE_OPENED, handler)
    bus.emit(EventBus.FILE_OPENED, "test.h5")
    bus.off(EventBus.FILE_OPENED, handler)

    assert len(results) == 1
    assert results[0] == "test.h5"


def main():
    """运行所有测试"""
    print("=" * 60)
    print("HDF5 Viewer - Packaged Build Tests")
    print("=" * 60)

    tests = [
        test_core_imports,
        test_h5_operations,
        test_slicer,
        test_cache,
        test_plugins,
        test_export,
        test_event_bus,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
