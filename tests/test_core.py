#!/usr/bin/env python3
"""核心模块测试"""

import sys
import os
import tempfile
import numpy as np
import h5py

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.event_bus import EventBus
from core.datasource import DataSource, DataMeta, NodeType, TreeNode
from core.h5_source import H5Source
from core.slicer import SliceParser
from core.cache import LRUCache
from core.registry import DataSourceRegistry


def create_test_hdf5(path: str) -> None:
    """创建测试用的 HDF5 文件"""
    with h5py.File(path, 'w') as f:
        # 创建 group
        grp = f.create_group('data')

        # 创建 datasets
        grp.create_dataset('temperature', data=np.random.randn(100, 50))
        grp.create_dataset('pressure', data=np.random.randn(100, 50))

        # 创建带属性的 dataset
        ds = grp.create_dataset('coordinates', data=np.random.randn(3, 1000))
        ds.attrs['units'] = 'meters'
        ds.attrs['description'] = '3D coordinates'

        # 创建字符串数据
        f.create_dataset('labels', data=[b'label1', b'label2', b'label3'])

        # 创建嵌套 group
        sub = f.create_group('data/nested')
        sub.create_dataset('values', data=np.arange(1000))


def test_event_bus():
    """测试 EventBus"""
    print("Testing EventBus...")

    bus = EventBus.get_instance()
    results = []

    def handler(event):
        results.append(event.data)

    bus.on(EventBus.FILE_OPENED, handler)
    bus.emit(EventBus.FILE_OPENED, "test.h5")
    bus.off(EventBus.FILE_OPENED, handler)

    assert len(results) == 1, f"Expected 1 event, got {len(results)}"
    assert results[0] == "test.h5"
    print("  EventBus: OK")


def test_slicer():
    """测试 SliceParser"""
    print("Testing SliceParser...")

    # 测试解析
    s = SliceParser.parse("[0:100, 10:20]", (1000, 500))
    assert s == (slice(0, 100), slice(10, 20))

    # 测试默认切片
    s = SliceParser.default_slice((5000, 100), max_rows=1000)
    assert s[0].stop == 1000

    # 测试切片转字符串
    s_str = SliceParser.slice_to_str((slice(0, 100), slice(10, 20)))
    assert "0:100" in s_str

    print("  SliceParser: OK")


def test_cache():
    """测试 LRU Cache"""
    print("Testing LRUCache...")

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

    print("  LRUCache: OK")


def test_h5_source():
    """测试 H5Source"""
    print("Testing H5Source...")

    # 创建临时文件
    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        temp_path = f.name

    try:
        create_test_hdf5(temp_path)

        source = H5Source()
        source.open(temp_path)

        # 测试获取树
        tree = source.get_tree()
        assert tree.name == os.path.basename(temp_path)
        assert len(tree.children) > 0

        # 测试获取元数据
        meta = source.get_metadata('/data/temperature')
        assert meta.shape == (100, 50)
        assert meta.dtype == 'float64'

        # 测试读取切片
        data = source.read_slice('/data/temperature', (slice(0, 10), slice(0, 5)))
        assert data.shape == (10, 5)

        # 测试获取属性
        attrs = source.get_attrs('/data/coordinates')
        assert 'units' in attrs

        # 测试搜索
        results = source.search('temperature')
        assert len(results) > 0

        source.close()
        print("  H5Source: OK")

    finally:
        os.unlink(temp_path)


def test_registry():
    """测试 DataSourceRegistry"""
    print("Testing DataSourceRegistry...")

    # 注册
    DataSourceRegistry.register(H5Source)

    # 检查支持的扩展名
    exts = DataSourceRegistry.get_supported_extensions()
    assert '.h5' in exts
    assert '.hdf5' in exts

    # 检查文件支持
    assert DataSourceRegistry.is_supported("test.h5")
    assert DataSourceRegistry.is_supported("test.hdf5")
    assert not DataSourceRegistry.is_supported("test.txt")

    print("  DataSourceRegistry: OK")


def main():
    """运行所有测试"""
    print("=" * 50)
    print("HDF5 Viewer - Core Module Tests")
    print("=" * 50)

    test_event_bus()
    test_slicer()
    test_cache()
    test_h5_source()
    test_registry()

    print("=" * 50)
    print("All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
