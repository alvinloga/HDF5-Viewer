"""DataSource — 数据源抽象接口"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import numpy as np


class NodeType(Enum):
    """节点类型"""
    GROUP = "group"
    DATASET = "dataset"
    UNKNOWN = "unknown"


@dataclass
class DataMeta:
    """数据集元信息"""
    path: str
    name: str
    shape: tuple = ()
    dtype: str = ""
    ndim: int = 0
    size: int = 0
    node_type: NodeType = NodeType.UNKNOWN
    chunks: tuple | None = None
    compression: str | None = None
    attrs: dict = field(default_factory=dict)


@dataclass
class TreeNode:
    """树节点"""
    name: str
    path: str
    node_type: NodeType
    children: list['TreeNode'] = field(default_factory=list)
    meta: DataMeta | None = None


class DataSource(ABC):
    """统一数据源接口，所有格式实现此接口"""

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
    def is_open(self) -> bool:
        """文件是否已打开"""
        ...

    @abstractmethod
    def get_tree(self) -> TreeNode:
        """获取文件的树形结构"""
        ...

    @abstractmethod
    def get_metadata(self, path: str) -> DataMeta:
        """获取节点的元信息"""
        ...

    @abstractmethod
    def read_slice(self, path: str, slices: tuple) -> np.ndarray:
        """读取数据切片"""
        ...

    @abstractmethod
    def get_attrs(self, path: str) -> dict:
        """获取节点的属性"""
        ...

    @abstractmethod
    def search(self, keyword: str) -> list[str]:
        """搜索节点路径"""
        ...

    @abstractmethod
    def get_path(self) -> str:
        """获取文件路径"""
        ...
