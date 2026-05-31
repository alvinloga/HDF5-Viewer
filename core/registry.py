"""Registry — 数据源/插件注册中心"""

from pathlib import Path
from typing import Type
from .datasource import DataSource


class DataSourceRegistry:
    """数据源注册中心"""

    _sources: dict[str, Type[DataSource]] = {}

    @classmethod
    def register(cls, source_class: Type[DataSource]) -> None:
        """注册数据源"""
        instance = source_class()
        for ext in instance.extensions:
            cls._sources[ext.lower()] = source_class

    @classmethod
    def get(cls, path: str) -> DataSource:
        """根据文件路径获取对应的数据源"""
        ext = Path(path).suffix.lower()
        if ext not in cls._sources:
            raise ValueError(f"Unsupported file format: {ext}")
        return cls._sources[ext]()

    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """获取所有支持的扩展名"""
        return list(cls._sources.keys())

    @classmethod
    def is_supported(cls, path: str) -> bool:
        """检查文件是否支持"""
        ext = Path(path).suffix.lower()
        return ext in cls._sources


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
