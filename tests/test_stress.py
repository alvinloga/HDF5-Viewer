"""压力测试 - 并发访问和内存泄漏检测"""

import sys
import os
import tempfile
import numpy as np
import h5py
import gc
import time

# 添加项目根目录到 path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def test_memory_leak():
    """测试内存泄漏"""
    print("\n=== Testing Memory Leak ===")

    from core.h5_source import H5Source
    from core.cache import LRUCache

    try:
        # 创建测试文件
        with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
            temp_path = f.name

        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('data', data=np.random.randn(1000, 100))

        # 测试重复打开关闭
        for i in range(100):
            source = H5Source()
            source.open(temp_path)
            data = source.read_slice('/data', (slice(0, 100), slice(0, 10)))
            source.close()
            del source

        gc.collect()
        print(f"  [OK] 100 open/close cycles completed")

        # 测试缓存
        cache = LRUCache(max_size_mb=10)
        for i in range(1000):
            data = np.random.randn(100, 100)
            cache.put(f'key{i}', data)
            if i % 100 == 0:
                gc.collect()

        print(f"  [OK] Cache stress test: {cache.count} items, {cache.size_mb:.2f} MB")

        os.unlink(temp_path)
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_concurrent_access():
    """测试并发访问"""
    print("\n=== Testing Concurrent Access ===")

    from core.h5_source import H5Source
    from core.event_bus import EventBus

    try:
        # 创建测试文件
        with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
            temp_path = f.name

        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('data', data=np.random.randn(1000, 100))

        # 测试多个数据源同时打开
        sources = []
        for i in range(10):
            source = H5Source()
            source.open(temp_path)
            sources.append(source)

        # 测试同时读取
        for i in range(10):
            data = sources[i].read_slice('/data', (slice(0, 100), slice(0, 10)))
            assert data.shape == (100, 10)

        print(f"  [OK] 10 concurrent sources")

        # 关闭所有
        for source in sources:
            source.close()

        # 测试事件总线并发
        bus = EventBus()
        bus.clear()

        events_received = []
        def handler(e):
            events_received.append(e.data)

        bus.on('test', handler)

        # 快速触发多个事件
        for i in range(100):
            bus.emit('test', i)

        assert len(events_received) == 100
        print(f"  [OK] 100 events processed")

        bus.clear()
        os.unlink(temp_path)
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_rapid_open_close():
    """测试快速打开关闭"""
    print("\n=== Testing Rapid Open/Close ===")

    from core.h5_source import H5Source

    try:
        # 创建测试文件
        with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
            temp_path = f.name

        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('data', data=np.random.randn(100, 100))

        # 快速打开关闭
        start = time.time()
        for i in range(50):
            source = H5Source()
            source.open(temp_path)
            source.close()
        elapsed = time.time() - start

        print(f"  [OK] 50 open/close in {elapsed:.3f}s ({elapsed/50*1000:.1f}ms each)")

        # 快速读取
        source = H5Source()
        source.open(temp_path)

        start = time.time()
        for i in range(100):
            data = source.read_slice('/data', (slice(0, 10), slice(0, 10)))
        elapsed = time.time() - start

        print(f"  [OK] 100 reads in {elapsed:.3f}s ({elapsed/100*1000:.1f}ms each)")

        source.close()
        os.unlink(temp_path)
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_large_file_operations():
    """测试大文件操作"""
    print("\n=== Testing Large File Operations ===")

    from core.h5_source import H5Source
    from core.slicer import SliceParser

    try:
        # 创建大文件
        with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
            temp_path = f.name

        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('big', data=np.random.randn(10000, 1000))
            f.create_dataset('small', data=np.random.randn(10, 10))

        source = H5Source()
        source.open(temp_path)

        # 测试大文件元数据
        meta = source.get_metadata('/big')
        assert meta.shape == (10000, 1000)
        print(f"  [OK] Big dataset metadata: {meta.shape}")

        # 测试各种切片
        slices_to_test = [
            (slice(0, 100), slice(0, 100)),
            (slice(0, 1000), slice(0, 100)),
            (slice(0, 100), slice(0, 1000)),
            (slice(5000, 5100), slice(0, 100)),
        ]

        for slices in slices_to_test:
            data = source.read_slice('/big', slices)
            expected_shape = (slices[0].stop - slices[0].start, slices[1].stop - slices[1].start)
            assert data.shape == expected_shape
            print(f"  [OK] Slice {slices}: {data.shape}")

        # 测试默认切片
        default_slices = SliceParser.default_slice(meta.shape)
        data = source.read_slice('/big', default_slices)
        print(f"  [OK] Default slice: {data.shape}")

        source.close()
        os.unlink(temp_path)
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_error_recovery():
    """测试错误恢复"""
    print("\n=== Testing Error Recovery ===")

    from core.h5_source import H5Source

    try:
        # 测试打开不存在的文件
        try:
            source = H5Source()
            source.open('/nonexistent/file.h5')
            print(f"  [FAIL] Should have raised error")
            return False
        except FileNotFoundError:
            print(f"  [OK] FileNotFoundError caught")

        # 测试读取不存在的数据集
        with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
            temp_path = f.name

        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('data', data=np.random.randn(10, 10))

        source = H5Source()
        source.open(temp_path)

        try:
            data = source.read_slice('/nonexistent', (slice(0, 5),))
            print(f"  [FAIL] Should have raised error")
            return False
        except KeyError:
            print(f"  [OK] KeyError caught for missing dataset")

        # 测试读取组（不是数据集）
        source.close()  # 先关闭再重新打开
        with h5py.File(temp_path, 'a') as f:
            f.create_group('group')
        source.open(temp_path)

        try:
            data = source.read_slice('/group', (slice(0, 5),))
            print(f"  [FAIL] Should have raised error")
            return False
        except ValueError:
            print(f"  [OK] ValueError caught for group read")

        # 测试错误后继续使用
        data = source.read_slice('/data', (slice(0, 5), slice(0, 5)))
        assert data.shape == (5, 5)
        print(f"  [OK] Recovery after error")

        source.close()
        os.unlink(temp_path)
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_special_characters_in_path():
    """测试路径中的特殊字符"""
    print("\n=== Testing Special Characters in Path ===")

    from core.h5_source import H5Source

    try:
        with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
            temp_path = f.name

        # 创建包含特殊字符的路径
        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('normal', data=np.random.randn(10))
            g1 = f.create_group('with space')
            g1.create_dataset('data', data=np.random.randn(10))
            g2 = f.create_group('with-special')
            g2.create_dataset('data', data=np.random.randn(10))
            g3 = f.create_group('with.dots')
            g3.create_dataset('data', data=np.random.randn(10))

        source = H5Source()
        source.open(temp_path)

        # 测试正常路径
        data = source.read_slice('/normal', (slice(0, 5),))
        assert data.shape == (5,)
        print(f"  [OK] Normal path")

        # 测试带空格的路径
        data = source.read_slice('/with space/data', (slice(0, 5),))
        assert data.shape == (5,)
        print(f"  [OK] Path with space")

        # 测试带连字符的路径
        data = source.read_slice('/with-special/data', (slice(0, 5),))
        assert data.shape == (5,)
        print(f"  [OK] Path with hyphen")

        # 测试带点的路径
        data = source.read_slice('/with.dots/data', (slice(0, 5),))
        assert data.shape == (5,)
        print(f"  [OK] Path with dots")

        # 测试搜索
        results = source.search('data')
        assert len(results) == 3
        print(f"  [OK] Search found {len(results)} results")

        source.close()
        os.unlink(temp_path)
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_compressed_datasets():
    """测试压缩数据集"""
    print("\n=== Testing Compressed Datasets ===")

    from core.h5_source import H5Source

    try:
        with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
            temp_path = f.name

        # 创建压缩数据集
        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('gzip', data=np.random.randn(100, 100), compression='gzip')
            f.create_dataset('lzf', data=np.random.randn(100, 100), compression='lzf')
            f.create_dataset('none', data=np.random.randn(100, 100))

        source = H5Source()
        source.open(temp_path)

        # 测试读取压缩数据
        data = source.read_slice('/gzip', (slice(0, 10), slice(0, 10)))
        assert data.shape == (10, 10)
        print(f"  [OK] GZIP compressed")

        data = source.read_slice('/lzf', (slice(0, 10), slice(0, 10)))
        assert data.shape == (10, 10)
        print(f"  [OK] LZF compressed")

        data = source.read_slice('/none', (slice(0, 10), slice(0, 10)))
        assert data.shape == (10, 10)
        print(f"  [OK] No compression")

        # 测试元数据
        meta = source.get_metadata('/gzip')
        assert meta.compression == 'gzip'
        print(f"  [OK] Compression metadata")

        source.close()
        os.unlink(temp_path)
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_chunked_datasets():
    """测试分块数据集"""
    print("\n=== Testing Chunked Datasets ===")

    from core.h5_source import H5Source

    try:
        with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
            temp_path = f.name

        # 创建分块数据集
        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('chunked', data=np.random.randn(1000, 1000), chunks=(100, 100))
            f.create_dataset('auto', data=np.random.randn(1000, 1000), chunks=True)

        source = H5Source()
        source.open(temp_path)

        # 测试读取分块数据
        data = source.read_slice('/chunked', (slice(0, 100), slice(0, 100)))
        assert data.shape == (100, 100)
        print(f"  [OK] Chunked dataset")

        data = source.read_slice('/auto', (slice(0, 100), slice(0, 100)))
        assert data.shape == (100, 100)
        print(f"  [OK] Auto-chunked dataset")

        # 测试元数据
        meta = source.get_metadata('/chunked')
        assert meta.chunks == (100, 100)
        print(f"  [OK] Chunk metadata")

        source.close()
        os.unlink(temp_path)
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("HDF5 Viewer - Stress Tests")
    print("=" * 60)

    tests = [
        test_memory_leak,
        test_concurrent_access,
        test_rapid_open_close,
        test_large_file_operations,
        test_error_recovery,
        test_special_characters_in_path,
        test_compressed_datasets,
        test_chunked_datasets,
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
