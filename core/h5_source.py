"""H5Source — HDF5 数据源实现"""

import h5py
import numpy as np
from pathlib import Path
from .datasource import DataSource, DataMeta, TreeNode, NodeType


class H5Source(DataSource):
    """HDF5 数据源"""

    def __init__(self):
        self._file: h5py.File | None = None
        self._path: str = ""

    @property
    def name(self) -> str:
        return "HDF5"

    @property
    def extensions(self) -> list[str]:
        return [".h5", ".hdf5", ".hdf", ".h5py"]

    def open(self, path: str) -> None:
        """打开 HDF5 文件"""
        if self._file:
            self.close()
        self._path = path
        self._file = h5py.File(path, 'r+')

    def close(self) -> None:
        """关闭文件"""
        if self._file:
            self._file.close()
            self._file = None
            self._path = ""

    def is_open(self) -> bool:
        return self._file is not None and self._file.id.valid

    def get_path(self) -> str:
        return self._path

    def get_tree(self) -> TreeNode:
        """递归获取 HDF5 的树形结构"""
        if not self._file:
            raise RuntimeError("File not opened")

        root = TreeNode(
            name=Path(self._path).name,
            path="/",
            node_type=NodeType.GROUP
        )
        self._build_tree("/", self._file, root)
        return root

    def _build_tree(self, path: str, group: h5py.Group, parent: TreeNode) -> None:
        """递归构建树"""
        for name, item in group.items():
            item_path = f"{path}{name}" if path == "/" else f"{path}/{name}"

            if isinstance(item, h5py.Group):
                node = TreeNode(
                    name=name,
                    path=item_path,
                    node_type=NodeType.GROUP
                )
                parent.children.append(node)
                self._build_tree(item_path, item, node)
            elif isinstance(item, h5py.Dataset):
                meta = self._get_dataset_meta(item, item_path, name)
                node = TreeNode(
                    name=name,
                    path=item_path,
                    node_type=NodeType.DATASET,
                    meta=meta
                )
                parent.children.append(node)

    def _get_dataset_meta(self, ds: h5py.Dataset, path: str, name: str) -> DataMeta:
        """获取 dataset 的元信息"""
        return DataMeta(
            path=path,
            name=name,
            shape=tuple(ds.shape),
            dtype=str(ds.dtype),
            ndim=ds.ndim,
            size=ds.size,
            node_type=NodeType.DATASET,
            chunks=ds.chunks,
            compression=ds.compression,
            attrs=dict(ds.attrs)
        )

    def get_metadata(self, path: str) -> DataMeta:
        """获取节点元信息"""
        if not self._file:
            raise RuntimeError("File not opened")

        item = self._file[path]
        name = path.split("/")[-1] or "/"

        if isinstance(item, h5py.Dataset):
            return self._get_dataset_meta(item, path, name)
        elif isinstance(item, h5py.Group):
            return DataMeta(
                path=path,
                name=name,
                node_type=NodeType.GROUP,
                attrs=dict(item.attrs)
            )
        else:
            return DataMeta(path=path, name=name, node_type=NodeType.UNKNOWN)

    def read_slice(self, path: str, slices: tuple) -> np.ndarray:
        """读取数据切片"""
        if not self._file:
            raise RuntimeError("File not opened")

        ds = self._file[path]
        if not isinstance(ds, h5py.Dataset):
            raise ValueError(f"{path} is not a dataset")

        if slices:
            return ds[slices]
        return ds[:]

    def get_attrs(self, path: str) -> dict:
        """获取节点属性"""
        if not self._file:
            raise RuntimeError("File not opened")
        return dict(self._file[path].attrs)

    def write_data(self, path: str, data: np.ndarray) -> bool:
        """将数据写回 HDF5 文件"""
        if not self._file:
            return False
        try:
            dataset = self._file[path]
            dataset[...] = data
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to write data to {path}: {e}")

    def search(self, keyword: str) -> list[str]:
        """搜索节点路径"""
        if not self._file:
            raise RuntimeError("File not opened")

        results = []
        keyword_lower = keyword.lower()

        def visitor(name, obj):
            if keyword_lower in name.lower():
                results.append(f"/{name}")

        self._file.visititems(visitor)
        return results
