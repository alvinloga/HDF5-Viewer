"""边界情况和压力测试"""

import sys
import os
import tempfile
import numpy as np
import h5py

# 添加项目根目录到 path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def test_empty_file():
    """测试空 HDF5 文件"""
    print("\n=== Testing Empty HDF5 File ===")

    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        temp_path = f.name

    try:
        # 创建空文件
        with h5py.File(temp_path, 'w') as f:
            pass  # 空文件

        from core.h5_source import H5Source
        source = H5Source()
        source.open(temp_path)

        # 测试获取树
        tree = source.get_tree()
        assert tree is not None
        assert len(tree.children) == 0
        print(f"  [OK] Empty file tree: {len(tree.children)} children")

        # 测试搜索
        results = source.search("test")
        assert len(results) == 0
        print(f"  [OK] Empty file search: {len(results)} results")

        source.close()
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False
    finally:
        os.unlink(temp_path)


def test_single_dataset():
    """测试只有一个数据集的文件"""
    print("\n=== Testing Single Dataset File ===")

    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        temp_path = f.name

    try:
        # 创建只有一个数据集的文件
        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('data', data=np.random.randn(100))

        from core.h5_source import H5Source
        source = H5Source()
        source.open(temp_path)

        # 测试获取树
        tree = source.get_tree()
        assert len(tree.children) == 1
        assert tree.children[0].name == 'data'
        print(f"  [OK] Single dataset: {tree.children[0].name}")

        # 测试读取
        data = source.read_slice('/data', (slice(0, 10),))
        assert data.shape == (10,)
        print(f"  [OK] Read slice: {data.shape}")

        source.close()
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False
    finally:
        os.unlink(temp_path)


def test_deep_nested_groups():
    """测试深层嵌套的组"""
    print("\n=== Testing Deep Nested Groups ===")

    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        temp_path = f.name

    try:
        # 创建深层嵌套的文件
        with h5py.File(temp_path, 'w') as f:
            g1 = f.create_group('level1')
            g2 = g1.create_group('level2')
            g3 = g2.create_group('level3')
            g4 = g3.create_group('level4')
            g4.create_dataset('data', data=np.random.randn(10))

        from core.h5_source import H5Source
        source = H5Source()
        source.open(temp_path)

        # 测试获取树
        tree = source.get_tree()
        assert len(tree.children) == 1
        print(f"  [OK] Nested groups: depth=4")

        # 测试读取深层数据
        data = source.read_slice('/level1/level2/level3/level4/data', (slice(0, 5),))
        assert data.shape == (5,)
        print(f"  [OK] Deep read: {data.shape}")

        source.close()
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False
    finally:
        os.unlink(temp_path)


def test_string_datasets():
    """测试字符串数据集"""
    print("\n=== Testing String Datasets ===")

    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        temp_path = f.name

    try:
        # 创建字符串数据集
        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('strings', data=['hello', 'world', 'test'])
            f.create_dataset('bytes', data=[b'byte1', b'byte2', b'byte3'])

        from core.h5_source import H5Source
        source = H5Source()
        source.open(temp_path)

        # 测试读取字符串
        data = source.read_slice('/strings', (slice(0, 2),))
        assert data.shape == (2,)
        print(f"  [OK] String data: {data}")

        # 测试读取字节
        data = source.read_slice('/bytes', (slice(0, 2),))
        assert data.shape == (2,)
        print(f"  [OK] Bytes data: {data}")

        source.close()
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False
    finally:
        os.unlink(temp_path)


def test_nan_inf_data():
    """测试包含 NaN 和 Inf 的数据"""
    print("\n=== Testing NaN/Inf Data ===")

    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        temp_path = f.name

    try:
        # 创建包含 NaN 和 Inf 的数据
        data = np.array([1.0, 2.0, np.nan, np.inf, -np.inf, 5.0])
        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('special', data=data)

        from core.h5_source import H5Source
        source = H5Source()
        source.open(temp_path)

        # 测试读取
        result = source.read_slice('/special', (slice(0, 6),))
        assert result.shape == (6,)
        print(f"  [OK] NaN/Inf data: {result}")

        # 测试统计插件
        from plugins.builtin.statistics import StatisticsPlugin
        plugin = StatisticsPlugin()
        from core.datasource import DataMeta
        meta = DataMeta(path='/special', name='special', shape=(6,), dtype='float64')
        stats = plugin.run(result, meta)
        assert 'nan_count' in stats['result']
        assert stats['result']['nan_count'] == 1
        print(f"  [OK] Statistics: nan_count={stats['result']['nan_count']}")

        source.close()
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False
    finally:
        os.unlink(temp_path)


def test_large_dataset_performance():
    """测试大数据集性能"""
    print("\n=== Testing Large Dataset Performance ===")

    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        temp_path = f.name

    try:
        # 创建大数据集
        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('big', data=np.random.randn(100000, 100))

        from core.h5_source import H5Source
        source = H5Source()
        source.open(temp_path)

        import time

        # 测试元数据获取
        start = time.time()
        meta = source.get_metadata('/big')
        elapsed = time.time() - start
        assert meta.shape == (100000, 100)
        print(f"  [OK] Metadata: {elapsed:.3f}s")

        # 测试小切片
        start = time.time()
        data = source.read_slice('/big', (slice(0, 100), slice(0, 10)))
        elapsed = time.time() - start
        assert data.shape == (100, 10)
        print(f"  [OK] Small slice: {elapsed:.3f}s")

        # 测试默认切片
        from core.slicer import SliceParser
        slices = SliceParser.default_slice(meta.shape)
        start = time.time()
        data = source.read_slice('/big', slices)
        elapsed = time.time() - start
        print(f"  [OK] Default slice: {data.shape} in {elapsed:.3f}s")

        source.close()
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False
    finally:
        os.unlink(temp_path)


def test_slicer_edge_cases():
    """测试切片解析边界情况"""
    print("\n=== Testing Slicer Edge Cases ===")

    from core.slicer import SliceParser

    try:
        # 测试空字符串
        result = SliceParser.parse("", (100, 200))
        assert result == tuple()
        print(f"  [OK] Empty string")

        # 测试只有冒号
        result = SliceParser.parse("[:]", (100,))
        assert result == (slice(None, None, None),)
        print(f"  [OK] Only colon")

        # 测试单个索引
        result = SliceParser.parse("[5]", (100,))
        assert result == (5,)
        print(f"  [OK] Single index")

        # 测试步长
        result = SliceParser.parse("[0:100:2]", (100,))
        assert result == (slice(0, 100, 2),)
        print(f"  [OK] Step")

        # 测试负索引
        result = SliceParser.parse("[-10:]", (100,))
        assert result == (slice(-10, None, None),)
        print(f"  [OK] Negative index")

        # 测试超出范围
        result = SliceParser.parse("[0:200]", (100,))
        assert result == (slice(0, 200, None),)
        print(f"  [OK] Out of range")

        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_export_edge_cases():
    """测试导出边界情况"""
    print("\n=== Testing Export Edge Cases ===")

    from services.exporter import DataExporter

    try:
        # 测试空数据
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            temp_path = f.name

        empty_data = np.array([])
        result = DataExporter.to_csv(empty_data, temp_path)
        assert result == True
        print(f"  [OK] Empty data export")

        # 测试 1D 数据
        data_1d = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = DataExporter.to_csv(data_1d, temp_path)
        assert result == True
        print(f"  [OK] 1D data export")

        # 测试 2D 数据
        data_2d = np.random.randn(10, 5)
        result = DataExporter.to_csv(data_2d, temp_path)
        assert result == True
        print(f"  [OK] 2D data export")

        # 测试 3D 数据
        data_3d = np.random.randn(3, 4, 5)
        result = DataExporter.to_csv(data_3d, temp_path)
        assert result == True
        print(f"  [OK] 3D data export")

        # 测试包含 NaN 的数据
        data_nan = np.array([1.0, np.nan, 3.0, np.inf, -np.inf])
        result = DataExporter.to_csv(data_nan, temp_path)
        assert result == True
        print(f"  [OK] NaN/Inf data export")

        os.unlink(temp_path)
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_cache_edge_cases():
    """测试缓存边界情况"""
    print("\n=== Testing Cache Edge Cases ===")

    from core.cache import LRUCache

    try:
        # 测试空缓存
        cache = LRUCache(max_size_mb=1)  # 1MB 缓存
        assert cache.get('key1') is None
        print(f"  [OK] Empty cache")

        # 测试缓存存储
        data = np.random.randn(100, 100)
        cache.put('key1', data)
        result = cache.get('key1')
        assert result is not None
        assert result.shape == (100, 100)
        print(f"  [OK] Cache store/retrieve")

        # 测试更新
        data2 = np.random.randn(50, 50)
        cache.put('key1', data2)
        result = cache.get('key1')
        assert result.shape == (50, 50)
        print(f"  [OK] Cache update")

        # 测试清空
        cache.clear()
        assert cache.count == 0
        print(f"  [OK] Cache clear")

        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_event_bus_edge_cases():
    """测试事件总线边界情况"""
    print("\n=== Testing Event Bus Edge Cases ===")

    from core.event_bus import EventBus

    try:
        bus = EventBus()
        bus.clear()

        # 测试无处理器的事件
        bus.emit('nonexistent.event', 'data')
        print(f"  [OK] No handlers")

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
        print(f"  [OK] Multiple handlers")

        # 测试移除处理器
        bus.off('test.event', handler1)
        events.clear()
        bus.emit('test.event', 'test_data2')
        assert len(events) == 1
        print(f"  [OK] Remove handler")

        # 测试处理器异常
        def bad_handler(e):
            raise Exception("Handler error")

        bus.on('bad.event', bad_handler)
        bus.emit('bad.event', 'data')  # 不应该崩溃
        print(f"  [OK] Handler exception")

        bus.clear()
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_datatable_model_edge_cases():
    """测试 DataTableModel 边界情况"""
    print("\n=== Testing DataTableModel Edge Cases ===")

    from gui.editor.data_table import DataTableModel
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QModelIndex

    app = QApplication.instance() or QApplication(sys.argv)

    try:
        model = DataTableModel()

        # 测试空模型
        assert model.rowCount() == 0
        assert model.columnCount() == 0
        assert model.data(QModelIndex()) is None
        print(f"  [OK] Empty model")

        # 测试加载 None
        model.load_data(None)
        assert model.rowCount() == 0
        print(f"  [OK] Load None")

        # 测试加载空数组
        model.load_data(np.array([]))
        assert model.rowCount() == 0
        print(f"  [OK] Load empty array")

        # 测试 1D 数据
        model.load_data(np.array([1, 2, 3, 4, 5]))
        assert model.rowCount() == 5
        assert model.columnCount() == 2  # Index + Value
        print(f"  [OK] 1D data")

        # 测试 2D 数据
        model.load_data(np.random.randn(10, 5))
        assert model.rowCount() == 10
        assert model.columnCount() == 5
        print(f"  [OK] 2D data")

        # 测试大数据限制
        model.load_data(np.random.randn(100000, 10))
        assert model.rowCount() == 5000  # MAX_ROWS
        print(f"  [OK] Big data limit")

        # 测试清空
        model.clear_data()
        assert model.rowCount() == 0
        print(f"  [OK] Clear data")

        # 测试格式化
        assert model._format_value(np.nan) == "NaN"
        assert model._format_value(np.inf) == "Inf"
        assert model._format_value(-np.inf) == "-Inf"
        assert model._format_value(3.14159) == "3.14159"
        assert model._format_value(42) == "42"
        print(f"  [OK] Format values")

        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("HDF5 Viewer - Edge Case Tests")
    print("=" * 60)

    tests = [
        test_empty_file,
        test_single_dataset,
        test_deep_nested_groups,
        test_string_datasets,
        test_nan_inf_data,
        test_large_dataset_performance,
        test_slicer_edge_cases,
        test_export_edge_cases,
        test_cache_edge_cases,
        test_event_bus_edge_cases,
        test_datatable_model_edge_cases,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
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
