"""Registry — 数据源/插件注册中心"""

import os
from pathlib import Path
from typing import Type
from .datasource import DataSource


class DataSourceRegistry:
    """数据源注册中心"""

    _sources: dict[str, Type[DataSource]] = {}
    _instances: dict[str, DataSource] = {}  # cache: path -> instance

    @classmethod
    def register(cls, source_class: Type[DataSource]) -> None:
        """注册数据源"""
        instance = source_class()
        for ext in instance.extensions:
            cls._sources[ext.lower()] = source_class

    @classmethod
    def get(cls, path: str, reuse: bool = True) -> DataSource:
        """根据文件路径获取对应的数据源

        Args:
            path: 文件路径
            reuse: 是否复用已有实例（默认 True）
        """
        ext = Path(path).suffix.lower()
        # 对于目录格式，使用目录名后缀
        if not ext and os.path.isdir(path):
            for filter_ext in cls._sources:
                if path.endswith(filter_ext):
                    ext = filter_ext
                    break
        if ext not in cls._sources:
            raise ValueError(f"Unsupported file format: {ext}")
        if reuse and path in cls._instances:
            return cls._instances[path]
        instance = cls._sources[ext]()
        if reuse:
            cls._instances[path] = instance
        return instance

    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """获取所有支持的扩展名"""
        return list(cls._sources.keys())

    @classmethod
    def is_supported(cls, path: str) -> bool:
        """检查文件是否支持"""
        ext = Path(path).suffix.lower()
        return ext in cls._sources

    @classmethod
    def try_register(cls, source_class: Type) -> None:
        """尝试注册数据源（如果依赖可用）"""
        try:
            instance = source_class()
            for ext in instance.extensions:
                cls._sources[ext.lower()] = source_class
        except (ImportError, TypeError):
            pass  # 依赖不可用或类不完整，跳过注册

    @classmethod
    def remove_instance(cls, path: str) -> None:
        """从缓存中移除实例（关闭文件后调用）"""
        instance = cls._instances.pop(path, None)
        if instance and instance.is_open():
            instance.close()

    @classmethod
    def close_all(cls) -> None:
        """关闭并清除所有缓存的数据源实例"""
        for path, instance in list(cls._instances.items()):
            if instance.is_open():
                instance.close()
        cls._instances.clear()


class PluginManager:
    """插件管理器"""

    _analyzers: dict[str, object] = {}
    _visualizers: dict[str, object] = {}

    @classmethod
    def register_analyzer(cls, plugin) -> None:
        """注册统计分析插件"""
        cls._analyzers[plugin.name] = plugin

    @classmethod
    def register_visualizer(cls, plugin) -> None:
        """注册可视化插件"""
        cls._visualizers[plugin.name] = plugin

    @classmethod
    def get_analyzers(cls) -> dict[str, object]:
        """获取所有分析插件"""
        return cls._analyzers.copy()

    @classmethod
    def get_visualizers(cls) -> dict[str, object]:
        """获取所有可视化插件"""
        return cls._visualizers.copy()

    @classmethod
    def get_matching_visualizers(cls, data_shape: tuple, dtype: str) -> list:
        """获取匹配的可视化插件"""
        matching = []
        for plugin in cls._visualizers.values():
            if plugin.can_accept(data_shape, dtype):
                matching.append(plugin)
        return matching

    @classmethod
    def get_matching_analyzers(cls, data_shape: tuple, dtype: str) -> list:
        """获取匹配的分析插件"""
        matching = []
        for plugin in cls._analyzers.values():
            if plugin.can_accept(data_shape, dtype) if hasattr(plugin, 'can_accept') else True:
                matching.append(plugin)
        return matching

    @classmethod
    def load_builtin_plugins(cls) -> None:
        """加载内置插件"""
        from plugins.builtin.statistics import StatisticsPlugin
        from plugins.builtin.histogram import HistogramPlugin
        from plugins.builtin.line_chart import LineChartPlugin
        from plugins.builtin.heatmap import HeatmapPlugin

        cls.register_analyzer(StatisticsPlugin())
        cls.register_visualizer(HistogramPlugin())
        cls.register_visualizer(LineChartPlugin())
        cls.register_visualizer(HeatmapPlugin())
