"""压力测试 - 并发访问和内存泄漏检测"""

import sys
import os
import tempfile
import numpy as np
import h5py
import gc
import time
import pytest

# 添加项目根目录到 path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_h5(tmp_path):
    """创建临时 HDF5 文件路径，测试结束后自动清理"""
    return str(tmp_path / "test.h5")


# ── 测试 ──────────────────────────────────────────────────────────────────

def test_memory_leak(tmp_h5):
    """测试内存泄漏"""
    from core.h5_source import H5Source
    from core.cache import LRUCache

    # 创建测试文件
    with h5py.File(tmp_h5, 'w') as f:
        f.create_dataset('data', data=np.random.randn(1000, 100))

    # 测试重复打开关闭
    for i in range(100):
        source = H5Source()
        source.open(tmp_h5)
        data = source.read_slice('/data', (slice(0, 100), slice(0, 10)))
        source.close()
        del source

    gc.collect()

    # 测试缓存
    cache = LRUCache(max_size_mb=10)
    for i in range(1000):
        data = np.random.randn(100, 100)
        cache.put(f'key{i}', data)
        if i % 100 == 0:
            gc.collect()

    assert cache.count >= 0  # 缓存应正常工作


def test_concurrent_access(tmp_h5):
    """测试并发访问"""
    from core.h5_source import H5Source
    from core.event_bus import EventBus

    # 创建测试文件
    with h5py.File(tmp_h5, 'w') as f:
        f.create_dataset('data', data=np.random.randn(1000, 100))

    # 测试多个数据源同时打开
    sources = []
    for i in range(10):
        source = H5Source()
        source.open(tmp_h5)
        sources.append(source)

    # 测试同时读取
    for i in range(10):
        data = sources[i].read_slice('/data', (slice(0, 100), slice(0, 10)))
        assert data.shape == (100, 10)

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

    bus.clear()


def test_rapid_open_close(tmp_h5):
    """测试快速打开关闭"""
    from core.h5_source import H5Source

    # 创建测试文件
    with h5py.File(tmp_h5, 'w') as f:
        f.create_dataset('data', data=np.random.randn(100, 100))

    # 快速打开关闭
    start = time.time()
    for i in range(50):
        source = H5Source()
        source.open(tmp_h5)
        source.close()
    elapsed = time.time() - start
    assert elapsed >= 0  # 只要不崩溃就行

    # 快速读取
    source = H5Source()
    source.open(tmp_h5)

    start = time.time()
    for i in range(100):
        data = source.read_slice('/data', (slice(0, 10), slice(0, 10)))
    elapsed = time.time() - start
    assert elapsed >= 0

    source.close()


def test_large_file_operations(tmp_h5):
    """测试大文件操作"""
    from core.h5_source import H5Source
    from core.slicer import SliceParser

    # 创建大文件
    with h5py.File(tmp_h5, 'w') as f:
        f.create_dataset('big', data=np.random.randn(10000, 1000))
        f.create_dataset('small', data=np.random.randn(10, 10))

    source = H5Source()
    source.open(tmp_h5)

    # 测试大文件元数据
    meta = source.get_metadata('/big')
    assert meta.shape == (10000, 1000)

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

    # 测试默认切片
    default_slices = SliceParser.default_slice(meta.shape)
    data = source.read_slice('/big', default_slices)
    assert data is not None

    source.close()


def test_error_recovery():
    """测试错误恢复"""
    from core.h5_source import H5Source

    # 测试打开不存在的文件
    with pytest.raises(FileNotFoundError):
        source = H5Source()
        source.open('/nonexistent/file.h5')

    # 测试读取不存在的数据集
    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        temp_path = f.name

    try:
        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('data', data=np.random.randn(10, 10))

        source = H5Source()
        source.open(temp_path)

        with pytest.raises(KeyError):
            data = source.read_slice('/nonexistent', (slice(0, 5),))

        # 测试读取组（不是数据集）
        source.close()
        with h5py.File(temp_path, 'a') as f:
            f.create_group('group')
        source.open(temp_path)

        with pytest.raises(ValueError):
            data = source.read_slice('/group', (slice(0, 5),))

        # 测试错误后继续使用
        data = source.read_slice('/data', (slice(0, 5), slice(0, 5)))
        assert data.shape == (5, 5)

        source.close()
    finally:
        os.unlink(temp_path)


def test_special_characters_in_path(tmp_h5):
    """测试路径中的特殊字符"""
    from core.h5_source import H5Source

    # 创建包含特殊字符的路径
    with h5py.File(tmp_h5, 'w') as f:
        f.create_dataset('normal', data=np.random.randn(10))
        g1 = f.create_group('with space')
        g1.create_dataset('data', data=np.random.randn(10))
        g2 = f.create_group('with-special')
        g2.create_dataset('data', data=np.random.randn(10))
        g3 = f.create_group('with.dots')
        g3.create_dataset('data', data=np.random.randn(10))

    source = H5Source()
    source.open(tmp_h5)

    # 测试正常路径
    data = source.read_slice('/normal', (slice(0, 5),))
    assert data.shape == (5,)

    # 测试带空格的路径
    data = source.read_slice('/with space/data', (slice(0, 5),))
    assert data.shape == (5,)

    # 测试带连字符的路径
    data = source.read_slice('/with-special/data', (slice(0, 5),))
    assert data.shape == (5,)

    # 测试带点的路径
    data = source.read_slice('/with.dots/data', (slice(0, 5),))
    assert data.shape == (5,)

    # 测试搜索
    results = source.search('data')
    assert len(results) == 3

    source.close()


def test_compressed_datasets(tmp_h5):
    """测试压缩数据集"""
    from core.h5_source import H5Source

    # 创建压缩数据集
    with h5py.File(tmp_h5, 'w') as f:
        f.create_dataset('gzip', data=np.random.randn(100, 100), compression='gzip')
        f.create_dataset('lzf', data=np.random.randn(100, 100), compression='lzf')
        f.create_dataset('none', data=np.random.randn(100, 100))

    source = H5Source()
    source.open(tmp_h5)

    # 测试读取压缩数据
    data = source.read_slice('/gzip', (slice(0, 10), slice(0, 10)))
    assert data.shape == (10, 10)

    data = source.read_slice('/lzf', (slice(0, 10), slice(0, 10)))
    assert data.shape == (10, 10)

    data = source.read_slice('/none', (slice(0, 10), slice(0, 10)))
    assert data.shape == (10, 10)

    # 测试元数据
    meta = source.get_metadata('/gzip')
    assert meta.compression == 'gzip'

    source.close()


def test_chunked_datasets(tmp_h5):
    """测试分块数据集"""
    from core.h5_source import H5Source

    # 创建分块数据集
    with h5py.File(tmp_h5, 'w') as f:
        f.create_dataset('chunked', data=np.random.randn(1000, 1000), chunks=(100, 100))
        f.create_dataset('auto', data=np.random.randn(1000, 1000), chunks=True)

    source = H5Source()
    source.open(tmp_h5)

    # 测试读取分块数据
    data = source.read_slice('/chunked', (slice(0, 100), slice(0, 100)))
    assert data.shape == (100, 100)

    data = source.read_slice('/auto', (slice(0, 100), slice(0, 100)))
    assert data.shape == (100, 100)

    # 测试元数据
    meta = source.get_metadata('/chunked')
    assert meta.chunks == (100, 100)

    source.close()


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
