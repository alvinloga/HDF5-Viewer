"""AsyncLoader — 异步数据加载器"""

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot
from typing import Any, Callable
import numpy as np


class LoadResult:
    """加载结果"""
    def __init__(self, data: np.ndarray | None = None, error: str | None = None):
        self.data = data
        self.error = error
        self.success = error is None


class LoadSignals(QObject):
    """加载信号"""
    finished = pyqtSignal(object)  # LoadResult
    progress = pyqtSignal(int)     # 进度百分比


class LoadTask(QRunnable):
    """异步加载任务"""

    def __init__(self, loader_fn: Callable, *args, **kwargs):
        super().__init__()
        self._loader_fn = loader_fn
        self._args = args
        self._kwargs = kwargs
        self.signals = LoadResult()
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self):
        try:
            result = self._loader_fn(*self._args, **self._kwargs)
            self.signals = LoadResult(data=result)
        except Exception as e:
            self.signals = LoadResult(error=str(e))


class AsyncLoader(QObject):
    """异步加载管理器"""

    _instance: 'AsyncLoader | None' = None

    def __init__(self, max_workers: int = 4):
        super().__init__()
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(max_workers)

    @classmethod
    def get_instance(cls) -> 'AsyncLoader':
        if cls._instance is None:
            cls._instance = AsyncLoader()
        return cls._instance

    def load(self, loader_fn: Callable, callback: Callable, error_callback: Callable | None = None, *args, **kwargs):
        """异步加载数据"""
        # 简化实现：直接同步调用（后续可改为真正的异步）
        try:
            result = loader_fn(*args, **kwargs)
            callback(LoadResult(data=result))
        except Exception as e:
            if error_callback:
                error_callback(LoadResult(error=str(e)))
