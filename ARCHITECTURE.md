# HDF5 Viewer — 架构文档

## 项目概述

轻量级 HDF5 文件浏览器，仿 VSCode 布局设计，支持大文件懒加载、多标签 Split、插件扩展。

**核心目标**: 像文本编辑器打开 txt 一样打开 HDF5 文件。

## 技术栈

- Python 3.10+
- PyQt6 — GUI 框架
- h5py — HDF5 读写核心
- numpy — 数据处理

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│  MainWindow (VSCode 风格布局)                                    │
│  ┌─────┬────────────┬──────────────────────────────────────────┐│
│  │ Act │ Sidebar    │ Editor Area (多标签 + Split + 拖拽)      ││
│  │ Bar │ Explorer   │ ┌────────────────────┬────────────────┐  ││
│  │     │ Search     │ │ DataTable          │ SidePanel      │  ││
│  │     │ Plugins    │ │                    │ (可视化插件)    │  ││
│  │     │            │ └────────────────────┴────────────────┘  ││
│  │     │            ├──────────────────────────────────────────┤│
│  │     │            │ BottomPanel: Properties / Output / Log   ││
│  └─────┴────────────┴──────────────────────────────────────────┘│
│  Status Bar: file path | node path | shape | dtype | size      │
├─────────────────────────────────────────────────────────────────┤
│                     EventBus (信号总线)                          │
├─────────────────────────────────────────────────────────────────┤
│  PluginManager                                                  │
│  ┌───────────────┬───────────────┬───────────────────────────┐  │
│  │ SourcePlugin  │ AnalyzePlugin │ VisualizePlugin           │  │
│  │ (数据源)      │ (统计分析)    │ (可视化)                  │  │
│  │ H5Source      │ Statistics    │ LineChart / Heatmap       │  │
│  │ NetCDF/Zarr.. │ Histogram     │ Histogram / Image         │  │
│  └───────────────┴───────────────┴───────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  Services: AsyncLoader | DataCache | SearchService | Exporter   │
├─────────────────────────────────────────────────────────────────┤
│  Config (统一配置)                                               │
└─────────────────────────────────────────────────────────────────┘
```

## 核心设计

### 1. DataSource 接口（泛化核心）

```python
class DataSource(ABC):
    def open(self, path: str) -> None: ...
    def get_tree(self) -> TreeNode: ...
    def read_slice(self, path: str, slices: tuple) -> np.ndarray: ...
    def get_attrs(self, path: str) -> dict: ...
    def get_metadata(self, path: str) -> DataMeta: ...
    def search(self, keyword: str) -> list[str]: ...
    def close(self) -> None: ...
```

### 2. EventBus（解耦通信）

```python
class EventBus:
    FILE_OPENED = "file.opened"
    NODE_SELECTED = "node.selected"
    SLICE_CHANGED = "slice.changed"
    SPLIT_REQUESTED = "split.requested"
    PLUGIN_ACTIVATED = "plugin.activated"
```

### 3. 插件系统（三层）

```python
class SourcePlugin(ABC): ...      # 数据源插件
class AnalyzePlugin(ABC): ...     # 统计分析插件
class VisualizePlugin(ABC): ...   # 可视化插件
```

### 4. 异步加载

- 打开文件只读 tree 结构（快）
- 数据切片异步线程读取
- LRU Cache 缓存最近切片

### 5. 大文件策略

- 懒加载：h5py.File 只打开句柄
- 分页：默认只显示前 N 行
- 切片限制：超大数据集自动截断
- 内存控制：单次读取不超过 maxPreviewBytes

## VSCode 风格布局

| VSCode 概念 | 映射 |
|------------|------|
| Activity Bar | 左侧图标栏（Explorer/Search/Plugins） |
| Explorer | 文件树视图 |
| Editor Area | 数据表格区（多标签、Split、拖拽） |
| Side Panel | 可视化插件面板 |
| Bottom Panel | 属性/日志面板 |
| Status Bar | 状态栏 |
| Tab Bar | 标签页栏 |

## 增量开发路线

| Phase | 目标 |
|-------|------|
| Phase 0 | 骨架：打开 HDF5，树形浏览，基础表格 |
| Phase 1 | 核心体验：多标签、Split、拖拽、切片控制 |
| Phase 2 | 大文件优化：异步加载、LRU 缓存、分页 |
| Phase 3 | 扩展能力：属性面板、搜索、导出 |
| Phase 4 | 插件框架：PluginManager + 三类接口 |
| Phase 5 | 内置插件：Statistics、LineChart、Heatmap |
| Phase 6 | 体验打磨：快捷键、主题、右键菜单 |

## 文件结构

```
hdf5-viewer/
├── main.py
├── config.json
├── core/
│   ├── datasource.py
│   ├── h5_source.py
│   ├── registry.py
│   ├── event_bus.py
│   ├── async_loader.py
│   ├── cache.py
│   └── slicer.py
├── gui/
│   ├── main_window.py
│   ├── activity_bar.py
│   ├── sidebar/
│   │   ├── explorer.py
│   │   ├── search_panel.py
│   │   └── plugin_panel.py
│   ├── editor/
│   │   ├── tab_manager.py
│   │   ├── file_panel.py
│   │   ├── data_table.py
│   │   └── slice_input.py
│   ├── side_panel.py
│   ├── bottom_panel.py
│   ├── status_bar.py
│   ├── menu_bar.py
│   └── toolbar.py
├── plugins/
│   ├── base.py
│   ├── builtin/
│   └── external/
├── services/
│   ├── search.py
│   └── exporter.py
├── utils/
│   ├── format.py
│   └── icons.py
└── tests/
```
