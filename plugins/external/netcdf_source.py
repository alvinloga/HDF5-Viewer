"""NetCDF Source Plugin — 支持 .nc / .nc4 文件"""

import numpy as np
from pathlib import Path
from core.datasource import DataSource, DataMeta, NodeType, TreeNode
from plugins.base import SourcePlugin

try:
    import netCDF4
    HAS_NETCDF4 = True
except ImportError:
    HAS_NETCDF4 = False


class NetCDFSource(SourcePlugin, DataSource):
    """NetCDF 数据源插件"""

    @property
    def name(self) -> str:
        return "NetCDF"

    @property
    def extensions(self) -> list[str]:
        return ['.nc', '.nc4', '.netcdf']

    def __init__(self):
        self._file = None
        self._path = ""

    def open(self, path: str) -> None:
        if not HAS_NETCDF4:
            raise ImportError("netCDF4 package is required for NetCDF support. Install with: pip install netCDF4")
        self._path = path
        self._file = netCDF4.Dataset(path, 'r')

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None

    def is_open(self) -> bool:
        return self._file is not None

    def get_path(self) -> str:
        return self._path

    def get_tree(self) -> TreeNode:
        """构建 NetCDF 文件树"""
        root = TreeNode(name=Path(self._path).name, path="/", node_type=NodeType.GROUP, children=[])
        if not self._file:
            return root

        for var_name, var in self._file.variables.items():
            path = f"/{var_name}"
            attrs = {k: var.getncattr(k) for k in var.ncattrs()}
            child = TreeNode(
                name=var_name,
                path=path,
                node_type=NodeType.DATASET,
                shape=var.shape,
                dtype=str(var.dtype),
                size=var.size,
                attrs=attrs,
                children=[]
            )
            root.children.append(child)

        for dim_name, dim in self._file.dimensions.items():
            path = f"/dimensions/{dim_name}"
            child = TreeNode(
                name=dim_name,
                path=path,
                node_type=NodeType.DATASET if len(dim) > 0 else NodeType.GROUP,
                shape=(len(dim),) if len(dim) > 0 else (),
                dtype="int32",
                size=len(dim) if len(dim) > 0 else 0,
                attrs={},
                children=[]
            )
            root.children.append(child)

        for grp_name in self._file.groups:
            path = f"/{grp_name}"
            child = TreeNode(name=grp_name, path=path, node_type=NodeType.GROUP, children=[])
            root.children.append(child)

        return root

    def read_slice(self, path: str, slices: tuple) -> np.ndarray:
        if not self._file:
            raise ValueError("File not open")
        var_name = path.lstrip('/').split('/')[-1]
        if var_name in self._file.variables:
            var = self._file.variables[var_name]
            if slices:
                return var[slices]
            return var[:]
        raise KeyError(f"Variable not found: {var_name}")

    def get_attrs(self, path: str) -> dict:
        if not self._file:
            return {}
        var_name = path.lstrip('/').split('/')[-1]
        if var_name in self._file.variables:
            var = self._file.variables[var_name]
            return {k: var.getncattr(k) for k in var.ncattrs()}
        return {}

    def get_metadata(self, path: str) -> DataMeta:
        if not self._file:
            raise ValueError("File not open")
        var_name = path.lstrip('/').split('/')[-1]
        if var_name in self._file.variables:
            var = self._file.variables[var_name]
            attrs = {k: var.getncattr(k) for k in var.ncattrs()}
            return DataMeta(
                path=path,
                name=var_name,
                node_type=NodeType.DATASET,
                shape=var.shape,
                dtype=str(var.dtype),
                ndim=var.ndim,
                size=var.size,
                attrs=attrs
            )
        return DataMeta(path=path, name=var_name, node_type=NodeType.GROUP, shape=(), dtype='', ndim=0, size=0, attrs={})

    def write_data(self, path: str, data: np.ndarray) -> bool:
        raise NotImplementedError("NetCDF source is read-only")

    def search(self, keyword: str) -> list[str]:
        if not self._file:
            return []
        results = []
        for name in self._file.variables:
            if keyword.lower() in name.lower():
                results.append(f"/{name}")
        return results
