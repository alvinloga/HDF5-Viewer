"""Plugin Base — 插件基类定义"""

from abc import ABC, abstractmethod
from typing import Any
from PyQt6.QtWidgets import QWidget
import numpy as np
from core.datasource import DataMeta


class SourcePlugin(ABC):
    """数据源插件接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        ...

    @property
    @abstractmethod
    def extensions(self) -> list[str]:
        """支持的文件扩展名"""
        ...

    @abstractmethod
    def open(self, path: str) -> None:
        """打开文件"""
        ...

    @abstractmethod
    def close(self) -> None:
        """关闭文件"""
        ...

    @abstractmethod
    def get_tree(self) -> Any:
        """获取树结构"""
        ...

    @abstractmethod
    def read_slice(self, path: str, slices: tuple) -> np.ndarray:
        """读取切片"""
        ...

    @abstractmethod
    def get_attrs(self, path: str) -> dict:
        """获取属性"""
        ...


class AnalyzePlugin(ABC):
    """统计分析插件接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        ...

    @property
    @abstractmethod
    def accepts(self) -> list[str]:
        """接受的数据类型，如 ['numeric', 'array', 'any']"""
        ...

    @abstractmethod
    def run(self, data: np.ndarray, meta: DataMeta) -> dict:
        """
        执行分析
        返回: {'name': str, 'result': Any, 'summary': str}
        """
        ...


class VisualizePlugin(ABC):
    """可视化插件接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        ...

    @property
    @abstractmethod
    def accepts(self) -> list[str]:
        """适合的数据形状，如 ['1d', '2d', '3d', 'image']"""
        ...

    @abstractmethod
    def create_widget(self, data: np.ndarray, meta: DataMeta) -> QWidget:
        """返回一个可嵌入的 Qt 控件"""
        ...

    def can_accept(self, data_shape: tuple, dtype: str) -> bool:
        """检查是否能接受该数据"""
        import numpy as np

        if 'any' in self.accepts:
            return True

        ndim = len(data_shape)
        if ndim == 1 and '1d' in self.accepts:
            return True
        if ndim == 2:
            if '2d' in self.accepts:
                return True
            if 'image' in self.accepts and min(data_shape) > 1:
                return True
        if ndim >= 3 and '3d' in self.accepts:
            return True

        if 'numeric' in self.accepts:
            try:
                np.dtype(dtype)
                return True
            except:
                pass

        return False
