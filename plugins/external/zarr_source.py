"""Zarr Source Plugin — 支持 .zarr 文件"""

import numpy as np
from pathlib import Path
from core.datasource import DataSource, DataMeta, NodeType, TreeNode
from plugins.base import SourcePlugin

try:
    import zarr
    HAS_ZARR = True
except ImportError:
    HAS_ZARR = False


class ZarrSource(SourcePlugin, DataSource):
    """Zarr 数据源插件"""

    @property
    def name(self) -> str:
        return "Zarr"

    @property
    def extensions(self) -> list[str]:
        return ['.zarr']

    def __init__(self):
        self._store = None
        self._root = None
        self._path = ""

    def open(self, path: str) -> None:
        if not HAS_ZARR:
            raise ImportError("zarr package is required for Zarr support. Install with: pip install zarr")
        self._path = path
        self._store = zarr.open(path, mode='r')
        self._root = self._store

    def close(self) -> None:
        self._store = None
        self._root = None

    def is_open(self) -> bool:
        return self._root is not None

    def get_path(self) -> str:
        return self._path

    def get_tree(self) -> TreeNode:
        root = TreeNode(name=Path(self._path).name, path="/", node_type=NodeType.GROUP, children=[])
        if not self._root:
            return root
        self._build_tree(self._root, "/", root)
        return root

    def _build_tree(self, group, path: str, parent: TreeNode):
        for name, item in group.items():
            item_path = f"{path}{name}" if path == "/" else f"{path}/{name}"
            if isinstance(item, zarr.hierarchy.Group):
                child = TreeNode(name=name, path=item_path, node_type=NodeType.GROUP, children=[])
                parent.children.append(child)
                self._build_tree(item, item_path, child)
            else:
                attrs = dict(item.attrs) if item.attrs else {}
                child = TreeNode(
                    name=name, path=item_path, node_type=NodeType.DATASET,
                    shape=item.shape, dtype=str(item.dtype), size=item.size,
                    attrs=attrs, children=[]
                )
                parent.children.append(child)

    def read_slice(self, path: str, slices: tuple) -> np.ndarray:
        if not self._root:
            raise ValueError("File not open")
        parts = path.lstrip('/').split('/')
        item = self._root
        for part in parts:
            item = item[part]
        if slices:
            return item[slices]
        return item[:]

    def get_attrs(self, path: str) -> dict:
        if not self._root:
            return {}
        parts = path.lstrip('/').split('/')
        item = self._root
        for part in parts:
            item = item[part]
        return dict(item.attrs) if hasattr(item, 'attrs') else {}

    def get_metadata(self, path: str) -> DataMeta:
        if not self._root:
            raise ValueError("File not open")
        parts = path.lstrip('/').split('/')
        item = self._root
        for part in parts:
            item = item[part]
        if isinstance(item, zarr.hierarchy.Group):
            return DataMeta(path=path, name=parts[-1], node_type=NodeType.GROUP, shape=(), dtype='', ndim=0, size=0, attrs=dict(item.attrs))
        return DataMeta(
            path=path, name=parts[-1], node_type=NodeType.DATASET,
            shape=item.shape, dtype=str(item.dtype), ndim=item.ndim, size=item.size,
            attrs=dict(item.attrs)
        )

    def search(self, keyword: str) -> list[str]:
        if not self._root:
            return []
        results = []
        self._search_tree(self._root, "/", keyword, results)
        return results

    def _search_tree(self, group, path: str, keyword: str, results: list[str]):
        for name, item in group.items():
            item_path = f"{path}{name}" if path == "/" else f"{path}/{name}"
            if keyword.lower() in name.lower():
                results.append(item_path)
            if isinstance(item, zarr.hierarchy.Group):
                self._search_tree(item, item_path, keyword, results)
