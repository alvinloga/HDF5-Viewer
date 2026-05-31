#!/usr/bin/env python3
"""集成测试 — 验证完整功能"""

import sys
import os
import tempfile
import numpy as np
import h5py
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_complex_hdf5(path: str) -> None:
    """创建复杂的测试 HDF5 文件"""
    with h5py.File(path, 'w') as f:
        # 模拟科学数据
        grp = f.create_group('experiment')

        # 温度数据
        temp_data = np.random.randn(1000, 100) * 10 + 25  # 25°C ± 10
        ds = grp.create_dataset('temperature', data=temp_data)
        ds.attrs['units'] = 'celsius'
        ds.attrs['description'] = 'Temperature measurements'
        ds.attrs['sampling_rate'] = 100  # Hz

        # 压力数据
        pressure_data = np.random.randn(1000, 100) * 0.1 + 101.3  # 101.3 kPa ± 0.1
        ds = grp.create_dataset('pressure', data=pressure_data)
        ds.attrs['units'] = 'kPa'
        ds.attrs['description'] = 'Pressure measurements'

        # 时间序列
        time_data = np.linspace(0, 10, 1000)
        ds = grp.create_dataset('time', data=time_data)
        ds.attrs['units'] = 'seconds'

        # 多维数据
        multi_data = np.random.randn(10, 20, 30)
        ds = grp.create_dataset('3d_data', data=multi_data)
        ds.attrs['description'] = '3D volumetric data'

        # 字符串数据
        labels = [f'channel_{i:03d}'.encode() for i in range(100)]
        grp.create_dataset('channel_labels', data=labels)

        # 元数据
        f.attrs['experiment_name'] = 'Test Experiment'
        f.attrs['date'] = '2026-05-26'
        f.attrs['operator'] = 'Alvin'


def test_file_operations():
    """测试文件操作"""
    print("Testing file operations...")

    from core.h5_source import H5Source

    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        temp_path = f.name

    try:
        create_complex_hdf5(temp_path)

        # 测试打开
        source = H5Source()
        source.open(temp_path)
        assert source.is_open()

        # 测试树结构
        tree = source.get_tree()
        assert tree.name == os.path.basename(temp_path)
        assert len(tree.children) > 0

        # 测试元数据
        meta = source.get_metadata('/experiment/temperature')
        assert meta.shape == (1000, 100)
        assert meta.dtype == 'float64'
        assert meta.attrs.get('units') == 'celsius'

        # 测试数据读取
        data = source.read_slice('/experiment/temperature', (slice(0, 10), slice(0, 5)))
        assert data.shape == (10, 5)
        assert not np.any(np.isnan(data))

        # 测试属性
        attrs = source.get_attrs('/experiment/temperature')
        assert 'units' in attrs
        assert attrs['units'] == 'celsius'

        # 测试搜索
        results = source.search('temperature')
        assert len(results) > 0
        assert any('temperature' in r for r in results)

        # 测试多维数据
        meta_3d = source.get_metadata('/experiment/3d_data')
        assert meta_3d.shape == (10, 20, 30)
        assert meta_3d.ndim == 3

        # 测试字符串数据
        labels = source.read_slice('/experiment/channel_labels', (slice(0, 5),))
        assert len(labels) == 5

        source.close()
        assert not source.is_open()

        print("  [OK] File operations")
        return True

    finally:
        os.unlink(temp_path)


def test_slicer_integration():
    """测试切片解析集成"""
    print("Testing slicer integration...")

    from core.slicer import SliceParser

    # 测试各种切片格式
    test_cases = [
        ("[0:100, :]", (1000, 500), (slice(0, 100), slice(None, None))),
        ("[:, 0:50]", (1000, 500), (slice(None, None), slice(0, 50))),
        ("[0:100, 10:20]", (1000, 500), (slice(0, 100), slice(10, 20))),
        ("[0:100]", (1000,), (slice(0, 100),)),
        ("[0:10, 0:20, 0:30]", (100, 200, 300), (slice(0, 10), slice(0, 20), slice(0, 30))),
    ]

    for slice_str, shape, expected in test_cases:
        result = SliceParser.parse(slice_str, shape)
        assert result == expected, f"Failed for {slice_str}: {result} != {expected}"

    # 测试默认切片
    default = SliceParser.default_slice((5000, 100, 50), max_rows=1000)
    assert default[0].stop == 1000

    # 测试字符串转换
    s_str = SliceParser.slice_to_str((slice(0, 100), slice(10, 20)))
    assert "0:100" in s_str
    assert "10:20" in s_str

    print("  [OK] Slicer integration")
    return True


def test_cache_integration():
    """测试缓存集成"""
    print("Testing cache integration...")

    from core.cache import LRUCache

    cache = LRUCache(max_size_mb=1)

    # 测试多次存取
    for i in range(10):
        data = np.random.randn(1000)
        cache.put(f"key_{i}", data)

    # 验证最近的数据
    for i in range(5, 10):
        result = cache.get(f"key_{i}")
        assert result is not None

    # 测试缓存统计
    assert cache.count > 0
    assert cache.size_mb > 0

    # 测试清空
    cache.clear()
    assert cache.count == 0

    print("  [OK] Cache integration")
    return True


def test_plugin_integration():
    """测试插件集成"""
    print("Testing plugin integration...")

    from core.registry import PluginManager
    from plugins.builtin.statistics import StatisticsPlugin
    from plugins.builtin.histogram import HistogramPlugin
    from plugins.builtin.line_chart import LineChartPlugin
    from plugins.builtin.heatmap import HeatmapPlugin
    from core.datasource import DataMeta

    # 加载插件
    PluginManager.load_builtin_plugins()

    # 测试统计插件
    stats = StatisticsPlugin()
    test_data = np.random.randn(1000) * 10 + 25  # 25 ± 10
    meta = DataMeta(path="/test", name="test", shape=(1000,), dtype='float64')
    result = stats.run(test_data, meta)

    assert result['result'] is not None
    assert 'mean' in result['result']
    assert 'std' in result['result']
    assert 'min' in result['result']
    assert 'max' in result['result']
    assert 'median' in result['result']

    # 验证统计结果合理性
    mean = result['result']['mean']
    assert 20 < mean < 30, f"Mean {mean} not in expected range"

    # 测试可视化插件匹配
    matching = PluginManager.get_matching_visualizers((1000,), 'float64')
    assert len(matching) >= 2  # LineChart + Histogram

    plugin_names = [p.name for p in matching]
    assert 'Histogram' in plugin_names
    assert 'Line Chart' in plugin_names

    print("  [OK] Plugin integration")
    return True


def test_export_integration():
    """测试导出集成"""
    print("Testing export integration...")

    from services.exporter import DataExporter

    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
        csv_path = f.name

    try:
        # 测试 2D 数据导出
        data_2d = np.random.randn(10, 5)
        success = DataExporter.to_csv(data_2d, csv_path)
        assert success

        # 验证 CSV 内容
        with open(csv_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 11  # header + 10 rows
            header = lines[0].strip()
            assert 'Col_0' in header

        # 测试 1D 数据导出
        os.unlink(csv_path)
        data_1d = np.random.randn(100)
        success = DataExporter.to_csv(data_1d, csv_path)
        assert success

        with open(csv_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 101  # header + 100 rows

        print("  [OK] Export integration")
        return True

    finally:
        if os.path.exists(csv_path):
            os.unlink(csv_path)


def test_event_bus_integration():
    """测试事件总线集成"""
    print("Testing event bus integration...")

    from core.event_bus import EventBus

    bus = EventBus.get_instance()

    # 测试多个事件类型
    events_received = []

    def handler1(event):
        events_received.append(('file', event.data))

    def handler2(event):
        events_received.append(('node', event.data))

    bus.on(EventBus.FILE_OPENED, handler1)
    bus.on(EventBus.NODE_SELECTED, handler2)

    # 触发事件
    bus.emit(EventBus.FILE_OPENED, "test.h5")
    bus.emit(EventBus.NODE_SELECTED, "/data/temperature")
    bus.emit(EventBus.FILE_OPENED, "test2.h5")

    assert len(events_received) == 3
    assert events_received[0] == ('file', 'test.h5')
    assert events_received[1] == ('node', '/data/temperature')
    assert events_received[2] == ('file', 'test2.h5')

    # 清理
    bus.off(EventBus.FILE_OPENED, handler1)
    bus.off(EventBus.NODE_SELECTED, handler2)

    print("  [OK] Event bus integration")
    return True


def main():
    """运行所有测试"""
    print("=" * 60)
    print("HDF5 Viewer - Integration Tests")
    print("=" * 60)

    tests = [
        test_file_operations,
        test_slicer_integration,
        test_cache_integration,
        test_plugin_integration,
        test_export_integration,
        test_event_bus_integration,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"  [FAIL] {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
