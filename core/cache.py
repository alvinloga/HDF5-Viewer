"""Cache — LRU 数据缓存"""

from collections import OrderedDict
from typing import Any
import numpy as np
import sys


class LRUCache:
    """LRU 缓存，用于缓存最近使用的数据切片"""

    def __init__(self, max_size_mb: int = 512):
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._current_size = 0
        self._cache: OrderedDict[str, tuple[np.ndarray, int]] = OrderedDict()

    def get(self, key: str) -> np.ndarray | None:
        """获取缓存"""
        if key in self._cache:
            # 移到末尾（最近使用）
            self._cache.move_to_end(key)
            return self._cache[key][0]
        return None

    def put(self, key: str, data: np.ndarray) -> None:
        """存入缓存"""
        data_size = data.nbytes

        # 如果单个数据超过缓存上限，不缓存
        if data_size > self._max_size_bytes:
            return

        # 如果已存在，先移除旧的
        if key in self._cache:
            self._current_size -= self._cache[key][1]
            del self._cache[key]

        # 淘汰旧数据直到有足够空间
        while self._current_size + data_size > self._max_size_bytes and self._cache:
            _, (_, old_size) = self._cache.popitem(last=False)
            self._current_size -= old_size

        # 存入新数据
        self._cache[key] = (data, data_size)
        self._current_size += data_size

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._current_size = 0

    @property
    def size_mb(self) -> float:
        """当前缓存大小 (MB)"""
        return self._current_size / (1024 * 1024)

    @property
    def count(self) -> int:
        """缓存条目数"""
        return len(self._cache)
