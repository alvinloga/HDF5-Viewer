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
┌─────────────────────────────────────────────────────────────────────┐
│  MainWindow (VSCode 风格布局)                                        │
│  ┌─────┬────────────┬──────────────────────────────────────────────┐│
│  │ Act │ Sidebar    │ Editor Area (多标签 + Split + 拖拽排序)      ││
│  │ Bar │ Explorer   │ ┌───────────────────────┬──────────────────┐ ││
│  │     │ Search     │ │ DataTable (编辑模式)   │ SidePanel       │ ││
│  │     │ Plugins    │ │                       │ (可视化结果)     │ ││
│  │     │            │ └───────────────────────┴──────────────────┘ ││
│  │     │            ├──────────────────────────────────────────────┤│
│  │     │            │ BottomPanel: Properties / Attributes / Output││
│  ├─────┼────────────┼──────────────────────────────────────────────┤│
│  │ Sec │ Right Panel│ Search / Plugins (与 Explorer 同时可见)      ││
│  │ Bar │            │                                               ││
│  └─────┴────────────┴──────────────────────────────────────────────┘│
│  Status Bar: file path | node path | shape | dtype | size           │
├─────────────────────────────────────────────────────────────────────┤
│       EventBus | CommandPalette | ThemeManager                      │
├─────────────────────────────────────────────────────────────────────┤
│  PluginManager                                                      │
│  ┌───────────────┬───────────────┬───────────────────────────────┐  │
│  │ SourcePlugin  │ AnalyzePlugin │ VisualizePlugin               │  │
│  │ (数据源)      │ (统计分析)    │ (Matplotlib 可视化)           │  │
│  │ H5Source      │ Statistics    │ LineChart / Heatmap           │  │
│  │ NetCDF/Zarr   │ Histogram     │ Histogram                     │  │
│  └───────────────┴───────────────┴───────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│  Services: AsyncLoader | DataCache | SearchService | Exporter       │
├─────────────────────────────────────────────────────────────────────┤
│  Config (统一配置, 主题持久化, 面板状态持久化)                       │
└─────────────────────────────────────────────────────────────────────┘
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
| Secondary Bar | 右侧图标栏（Search/Plugins） |
| Explorer | 文件树视图 + 文件夹浏览器 |
| Editor Area | 数据表格区（多标签、Split、拖拽排序） |
| Side Panel | 可视化插件结果展示 |
| Bottom Panel | Properties/Attributes/Output |
| Status Bar | 状态栏（路径、形状、类型、大小） |
| Tab Bar | 标签页栏（含编辑模式工具栏） |
| Command Palette | Ctrl+Shift+P 命令面板 |

## 开发路线

| 版本 | 目标 |
|-------|------|
| v0.1.0 | 骨架：打开 HDF5，树形浏览，多标签 Split，异步加载，插件框架 |
| v0.2.0 | 插件面板 UI + Matplotlib 可视化 + Command Palette + 主题切换 + 数据编辑 + NetCDF/Zarr |
| v0.2.1 | 编辑模式工具栏改进 + 插件追踪活跃数据集 + 右侧 Activity Bar 行为优化 |
| v0.3.0 | 代码清理 + 标签拖出独立窗口 + 数据集对比 + 性能优化 |

## 文件结构

```
hdf5-viewer/
├── main.py                    # 入口
├── config.json                # 统一配置
├── build.py                   # 构建脚本
├── build_windows.py           # Windows 构建脚本
├── build_windows.bat          # Windows 构建入口
├── HDF5Viewer.spec            # PyInstaller 打包配置
├── requirements.txt           # 依赖列表
├── LICENSE                    # MIT 许可证
├── README.md                  # 中文说明
├── README_EN.md               # English README
├── RELEASE.md                 # 发布说明
├── TEST_REPORT.md             # 测试报告
├── TODO.md                    # 开发任务
├── ARCHITECTURE.md            # 架构文档
├── core/                      # 核心模块
│   ├── __init__.py
│   ├── datasource.py          # 数据源接口 + DataMeta/NodeType（支持写入）
│   ├── h5_source.py           # HDF5 实现（H5Source + H5DataWriter）
│   ├── registry.py            # 插件注册 + 条件注册
│   ├── event_bus.py           # 事件总线
│   ├── async_loader.py        # 异步加载器
│   ├── cache.py               # LRU 缓存
│   └── slicer.py              # 切片解析
├── gui/                       # GUI 模块
│   ├── __init__.py
│   ├── main_window.py         # VSCode 风格主窗口（含右侧面板管理）
│   ├── activity_bar.py        # 左侧 Activity Bar
│   ├── command_palette.py     # Command Palette（Ctrl+Shift+P）
│   ├── secondary_bar.py       # 右侧 Activity Bar
│   ├── secondary_panel.py     # 右侧面板（Search + Plugins）
│   ├── theme.py               # 主题管理（Dark/Light 切换 + 持久化）
│   ├── sidebar/
│   │   ├── __init__.py
│   │   ├── explorer.py        # HDF5 文件树
│   │   ├── folder_explorer.py # 本地文件夹浏览器
│   │   └── plugin_panel.py    # 可视化插件面板
│   ├── editor/
│   │   ├── __init__.py
│   │   ├── tab_manager.py     # 标签页管理（Split/拖拽/右键菜单）
│   │   ├── file_panel.py      # 数据集面板
│   │   ├── data_table.py      # 数据表格（支持编辑模式）
│   │   ├── data_editor.py     # 编辑模式工具栏
│   │   └── attr_panel.py      # 属性值面板
│   ├── status_bar.py          # 状态栏
│   └── bottom_panel.py        # 底部面板（Properties/Attributes/Output）
├── plugins/                   # 插件系统
│   ├── __init__.py
│   ├── base.py                # 插件接口（Source/Analyze/Visualize）
│   ├── builtin/               # 内置插件
│   │   ├── __init__.py
│   │   ├── statistics.py      # 基础统计
│   │   ├── line_chart.py      # Matplotlib 折线图
│   │   ├── histogram.py       # Matplotlib 直方图
│   │   └── heatmap.py         # Matplotlib 热力图
│   └── external/              # 外部数据源插件
│       ├── __init__.py
│       ├── netcdf_source.py   # NetCDF 数据源
│       └── zarr_source.py     # Zarr 数据源
├── services/                  # 服务
│   ├── __init__.py
│   ├── search.py              # 搜索服务
│   └── exporter.py            # 导出服务（CSV + NumPy）
├── utils/                     # 工具
│   └── __init__.py
└── tests/                     # 测试
    ├── __init__.py
    ├── test_core.py           # 核心模块测试（5 项）
    ├── test_phase1.py         # 第一阶段测试（5 项）
    ├── test_all_features.py   # 全面功能测试（7 项）
    ├── test_edge_cases.py     # 边界情况测试（11 项）
    ├── test_stress.py         # 压力测试（8 项）
    ├── test_packaged.py       # 打包测试（7 项）
    ├── test_integration.py    # 集成测试（6 项）
    ├── test_final.py          # 最终集成测试（3 项）
    ├── test_gui_interaction.py# GUI 交互测试（9 项）
    └── test_comprehensive.py  # 综合测试（60 项：主题/编辑/标签/Command Palette/搜索/插件）
```
