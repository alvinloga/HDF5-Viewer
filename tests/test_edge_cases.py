"""边界情况和压力测试"""

import sys
import os
import numpy as np
import h5py
import pytest

# 添加项目根目录到 path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_h5(tmp_path):
    """创建临时 HDF5 文件路径，测试结束后自动清理"""
    return str(tmp_path / "test.h5")


@pytest.fixture
def tmp_csv(tmp_path):
    """创建临时 CSV 文件路径，测试结束后自动清理"""
    return str(tmp_path / "test.csv")


# ── 测试 ──────────────────────────────────────────────────────────────────

def test_empty_file(tmp_h5):
    """测试空 HDF5 文件"""
    # 创建空文件
    with h5py.File(tmp_h5, 'w'):
        pass  # 空文件

    from core.h5_source import H5Source
    source = H5Source()
    source.open(tmp_h5)

    # 测试获取树
    tree = source.get_tree()
    assert tree is not None
    assert len(tree.children) == 0

    # 测试搜索
    results = source.search("test")
    assert len(results) == 0

    source.close()


def test_single_dataset(tmp_h5):
    """测试只有一个数据集的文件"""
    # 创建只有一个数据集的文件
    with h5py.File(tmp_h5, 'w') as f:
        f.create_dataset('data', data=np.random.randn(100))

    from core.h5_source import H5Source
    source = H5Source()
    source.open(tmp_h5)

    # 测试获取树
    tree = source.get_tree()
    assert len(tree.children) == 1
    assert tree.children[0].name == 'data'

    # 测试读取
    data = source.read_slice('/data', (slice(0, 10),))
    assert data.shape == (10,)

    source.close()


def test_deep_nested_groups(tmp_h5):
    """测试深层嵌套的组"""
    # 创建深层嵌套的文件
    with h5py.File(tmp_h5, 'w') as f:
        g1 = f.create_group('level1')
        g2 = g1.create_group('level2')
        g3 = g2.create_group('level3')
        g4 = g3.create_group('level4')
        g4.create_dataset('data', data=np.random.randn(10))

    from core.h5_source import H5Source
    source = H5Source()
    source.open(tmp_h5)

    # 测试获取树
    tree = source.get_tree()
    assert len(tree.children) == 1

    # 测试读取深层数据
    data = source.read_slice('/level1/level2/level3/level4/data', (slice(0, 5),))
    assert data.shape == (5,)

    source.close()


def test_string_datasets(tmp_h5):
    """测试字符串数据集"""
    # 创建字符串数据集
    with h5py.File(tmp_h5, 'w') as f:
        f.create_dataset('strings', data=['hello', 'world', 'test'])
        f.create_dataset('bytes', data=[b'byte1', b'byte2', b'byte3'])

    from core.h5_source import H5Source
    source = H5Source()
    source.open(tmp_h5)

    # 测试读取字符串
    data = source.read_slice('/strings', (slice(0, 2),))
    assert data.shape == (2,)

    # 测试读取字节
    data = source.read_slice('/bytes', (slice(0, 2),))
    assert data.shape == (2,)

    source.close()


def test_nan_inf_data(tmp_h5):
    """测试包含 NaN 和 Inf 的数据"""
    # 创建包含 NaN 和 Inf 的数据
    data = np.array([1.0, 2.0, np.nan, np.inf, -np.inf, 5.0])
    with h5py.File(tmp_h5, 'w') as f:
        f.create_dataset('special', data=data)

    from core.h5_source import H5Source
    source = H5Source()
    source.open(tmp_h5)

    # 测试读取
    result = source.read_slice('/special', (slice(0, 6),))
    assert result.shape == (6,)

    # 测试统计插件
    from plugins.builtin.statistics import StatisticsPlugin
    plugin = StatisticsPlugin()
    from core.datasource import DataMeta
    meta = DataMeta(path='/special', name='special', shape=(6,), dtype='float64')
    stats = plugin.run(result, meta)
    assert 'nan_count' in stats['result']
    assert stats['result']['nan_count'] == 1

    source.close()


def test_large_dataset_performance(tmp_h5):
    """测试大数据集性能"""
    # 创建大数据集
    with h5py.File(tmp_h5, 'w') as f:
        f.create_dataset('big', data=np.random.randn(100000, 100))

    from core.h5_source import H5Source
    source = H5Source()
    source.open(tmp_h5)

    # 测试元数据获取
    meta = source.get_metadata('/big')
    assert meta.shape == (100000, 100)

    # 测试小切片
    data = source.read_slice('/big', (slice(0, 100), slice(0, 10)))
    assert data.shape == (100, 10)

    # 测试默认切片
    from core.slicer import SliceParser
    slices = SliceParser.default_slice(meta.shape)
    data = source.read_slice('/big', slices)
    assert data is not None

    source.close()


def test_slicer_edge_cases():
    """测试切片解析边界情况"""
    from core.slicer import SliceParser

    # 测试空字符串
    result = SliceParser.parse("", (100, 200))
    assert result == tuple()

    # 测试只有冒号
    result = SliceParser.parse("[:]", (100,))
    assert result == (slice(None, None, None),)

    # 测试单个索引
    result = SliceParser.parse("[5]", (100,))
    assert result == (5,)

    # 测试步长
    result = SliceParser.parse("[0:100:2]", (100,))
    assert result == (slice(0, 100, 2),)

    # 测试负索引
    result = SliceParser.parse("[-10:]", (100,))
    assert result == (slice(-10, None, None),)

    # 测试超出范围
    result = SliceParser.parse("[0:200]", (100,))
    assert result == (slice(0, 200, None),)


def test_export_edge_cases(tmp_csv):
    """测试导出边界情况"""
    from services.exporter import DataExporter

    # 测试空数据
    empty_data = np.array([])
    result = DataExporter.to_csv(empty_data, tmp_csv)
    assert result

    # 测试 1D 数据
    data_1d = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    result = DataExporter.to_csv(data_1d, tmp_csv)
    assert result

    # 测试 2D 数据
    data_2d = np.random.randn(10, 5)
    result = DataExporter.to_csv(data_2d, tmp_csv)
    assert result

    # 测试 3D 数据
    data_3d = np.random.randn(3, 4, 5)
    result = DataExporter.to_csv(data_3d, tmp_csv)
    assert result

    # 测试包含 NaN 的数据
    data_nan = np.array([1.0, np.nan, 3.0, np.inf, -np.inf])
    result = DataExporter.to_csv(data_nan, tmp_csv)
    assert result


def test_cache_edge_cases():
    """测试缓存边界情况"""
    from core.cache import LRUCache

    # 测试空缓存
    cache = LRUCache(max_size_mb=1)  # 1MB 缓存
    assert cache.get('key1') is None

    # 测试缓存存储
    data = np.random.randn(100, 100)
    cache.put('key1', data)
    result = cache.get('key1')
    assert result is not None
    assert result.shape == (100, 100)

    # 测试更新
    data2 = np.random.randn(50, 50)
    cache.put('key1', data2)
    result = cache.get('key1')
    assert result.shape == (50, 50)

    # 测试清空
    cache.clear()
    assert cache.count == 0


def test_event_bus_edge_cases():
    """测试事件总线边界情况"""
    from core.event_bus import EventBus

    bus = EventBus()
    bus.clear()

    # 测试无处理器的事件
    bus.emit('nonexistent.event', 'data')

    # 测试多个处理器
    events = []
    def handler1(e):
        events.append(('h1', e.data))

    def handler2(e):
        events.append(('h2', e.data))

    bus.on('test.event', handler1)
    bus.on('test.event', handler2)
    bus.emit('test.event', 'test_data')
    assert len(events) == 2

    # 测试移除处理器
    bus.off('test.event', handler1)
    events.clear()
    bus.emit('test.event', 'test_data2')
    assert len(events) == 1

    # 测试处理器异常
    def bad_handler(e):
        raise Exception("Handler error")

    bus.on('bad.event', bad_handler)
    bus.emit('bad.event', 'data')  # 不应该崩溃

    bus.clear()


def test_datatable_model_edge_cases():
    """测试 DataTableModel 边界情况"""
    from gui.editor.data_table import DataTableModel
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QModelIndex

    QApplication.instance() or QApplication(sys.argv)

    model = DataTableModel()

    # 测试空模型
    assert model.rowCount() == 0
    assert model.columnCount() == 0
    assert model.data(QModelIndex()) is None

    # 测试加载 None
    model.load_data(None)
    assert model.rowCount() == 0

    # 测试加载空数组
    model.load_data(np.array([]))
    assert model.rowCount() == 0

    # 测试 1D 数据
    model.load_data(np.array([1, 2, 3, 4, 5]))
    assert model.rowCount() == 5
    assert model.columnCount() == 2  # Index + Value

    # 测试 2D 数据
    model.load_data(np.random.randn(10, 5))
    assert model.rowCount() == 10
    assert model.columnCount() == 5

    # 测试大数据限制
    model.load_data(np.random.randn(100000, 10))
    assert model.rowCount() == 5000  # MAX_ROWS

    # 测试清空
    model.clear_data()
    assert model.rowCount() == 0

    # 测试格式化
    assert model._format_value(np.nan) == "NaN"
    assert model._format_value(np.inf) == "Inf"
    assert model._format_value(-np.inf) == "-Inf"
    assert model._format_value(3.14159) == "3.14159"
    assert model._format_value(42) == "42"
