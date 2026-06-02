# HDF5 Viewer

轻量级 HDF5 文件浏览器，仿 VSCode 布局设计，支持大文件懒加载、多标签 Split、Matplotlib 可视化、数据编辑。

## ✨ 特性

- 🎨 **VSCode 风格界面** — Activity Bar + 侧边栏 + 编辑区 + 底部面板
- 📑 **多标签 + Split** — 同时查看多个文件/数据集，支持左右/上下分屏
- 🖱️ **标签拖拽** — 标签页拖拽排序（拖出独立窗口功能暂未启用）
- 🚀 **大文件异步加载** — 异步加载 + 分页，UI 不卡
- 📊 **Matplotlib 可视化** — 折线图、直方图、热力图，支持 1D/2D/3D 数据集
- 🔌 **插件面板** — Activity Bar 插件入口，选择可视化插件 + 参数配置
- 🎯 **Command Palette** — `Ctrl+Shift+P` 快速执行命令
- 🌗 **Dark/Light 主题** — 一键切换，配置自动持久化
- 📊 **Attributes 独立标签页** — 底部面板独立显示属性，双击可在新标签页查看属性值
- 🔍 **全局搜索** — 搜索 HDF5 节点路径
- 💾 **多格式导出** — CSV + NumPy (.npy) 导出
- ✏️ **数据编辑模式** — 切换编辑模式，直接修改数据集值并保存回文件
- 🌐 **多数据源** — HDF5 + NetCDF + Zarr（可选依赖，缺失时静默跳过）
- 🌐 **右侧面板栏** — Search + Plugins 独立右侧面板，与 Explorer 同时可见
- 🧪 **121 项测试覆盖** — 主题切换、数据编辑、标签操作、搜索、插件、边界情况全覆盖

## 🚀 快速开始

### 从源码运行

```bash
# 克隆项目
git clone https://github.com/realalvinlog/HDF5-Viewer.git
cd HDF5-Viewer

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py [file.h5]
```

### 可选依赖

NetCDF 和 Zarr 支持为可选功能，安装对应包即可启用：

```bash
pip install netCDF4>=1.6.0   # NetCDF 支持
pip install zarr>=2.14.0     # Zarr 支持
```

未安装时程序正常运行，对应文件格式不会出现在过滤器中。

### 使用打包版本

#### Linux

```bash
python build.py --all
cd dist/HDF5Viewer/
./run.sh [file.h5]
```

#### Windows

```bat
build_windows.bat
dist\HDF5Viewer\HDF5Viewer.exe [file.h5]
```

## 📖 使用指南

### 基本操作

| 操作 | 说明 |
|------|------|
| 打开文件 | `Ctrl+O` 或拖拽文件到窗口 |
| 关闭标签 | `Ctrl+W` |
| Command Palette | `Ctrl+Shift+P` |
| 切换侧边栏 | Activity Bar 图标点击 |
| Split 视图 | 右键标签 → Split Right / Split Down |
| 拖拽标签 | 标签页拖拽排序（拖出独立窗口暂未启用） |
| 右侧面板 | 点击右侧 Activity Bar 🔍/🔌 按钮 |
| 切换底部面板 | `Ctrl+J` |
| 搜索节点 | `Ctrl+Shift+F` |
| 切换主题 | Command Palette → Toggle Theme |
| 数据编辑 | Command Palette → Toggle Edit Mode |

### Command Palette 命令

按 `Ctrl+Shift+P` 打开，支持模糊搜索：

| 命令 | 说明 |
|------|------|
| Open File | 打开文件对话框 |
| Close Tab | 关闭当前标签 |
| Close All Tabs | 关闭所有标签 |
| Toggle Sidebar | 切换侧边栏 |
| Toggle Bottom Panel | 切换底部面板 |
| Toggle Theme | 切换 Dark/Light 主题 |
| Toggle Edit Mode | 切换数据编辑模式 |
| Export CSV | 导出当前数据集为 CSV |
| Export NumPy | 导出当前数据集为 .npy |
| Focus Explorer | 聚焦文件树 |
| Focus Search | 聚焦搜索 |
| Focus Plugin Panel | 聚焦插件面板 |

### 切片控制

- **手动输入**: 在 Slice 输入框输入 `[0:100, :]`
- **快捷按钮**: First 100 / Last 100 / All
- **维度选择**: 高维数据可选择查看维度

### 可视化插件

1. 点击 Activity Bar 的 🔌 图标打开插件面板
2. 选择可视化插件（Line Chart / Histogram / Heatmap）
3. 插件自动过滤匹配当前数据维度的类型
4. 点击 **Run** 执行可视化，结果在编辑区新标签页显示

| 插件 | 支持维度 | 说明 |
|------|----------|------|
| Line Chart | 1D, 2D | 折线图，2D 数据按行绘制多条线 |
| Histogram | 1D | 直方图，自动分箱 |
| Heatmap | 2D, 3D | 热力图，3D 数据取第一个切片 |

### Attributes 查看

- 底部面板切换到 **Attributes** 标签页查看属性列表
- **双击**属性行可在编辑区新标签页打开属性值的表格视图

### 数据编辑

1. 在标签页的 Slice 工具栏点击 **✏️ Edit** 按钮进入编辑模式（每个标签页独立控制）
2. 双击单元格编辑值
3. 编辑完成后点击 **💾 Save** 按钮保存

### 标签页操作

| 操作 | 说明 |
|------|------|
| 右键 → Split Right | 将标签页移到右侧新分组 |
| 右键 → Split Down | 将标签页移到下方新分组 |
| 右键 → Close | 关闭当前标签 |
| 右键 → Close Others | 关闭其他标签 |
| 右键 → Close All | 关闭所有标签 |
| 拖拽标签到标签栏外 | 成为独立窗口 |

## 🏗️ 项目结构

```
hdf5-viewer/
├── main.py                    # 入口
├── config.json                # 配置
├── core/                      # 核心模块
│   ├── datasource.py          # 数据源接口 + DataMeta/NodeType
│   ├── h5_source.py           # HDF5 实现
│   ├── event_bus.py           # 事件总线
│   ├── slicer.py              # 切片解析
│   ├── cache.py               # LRU 缓存
│   ├── async_loader.py        # 异步加载
│   └── registry.py            # 插件注册 + 条件注册
├── gui/                       # GUI 模块
│   ├── main_window.py         # 主窗口
│   ├── activity_bar.py        # 活动栏
│   ├── command_palette.py     # Command Palette
│   ├── secondary_bar.py       # 右侧 Activity Bar
│   ├── secondary_panel.py     # 右侧面板（Search + Plugins）
│   ├── sidebar/               # 侧边栏
│   │   ├── explorer.py        # HDF5 文件树
│   │   ├── folder_explorer.py # 本地文件夹浏览器
│   │   └── plugin_panel.py    # 可视化插件面板
│   ├── editor/                # 编辑器
│   │   ├── tab_manager.py     # 标签页管理（Split/拖拽/右键菜单）
│   │   ├── file_panel.py      # 数据集面板
│   │   ├── data_table.py      # 数据表格（支持编辑模式）
│   │   ├── data_editor.py     # 编辑模式工具栏
│   │   └── attr_panel.py      # 属性值面板
│   ├── status_bar.py          # 状态栏
│   └── bottom_panel.py        # 底部面板（Properties/Attributes/Output）
├── plugins/                   # 插件系统
│   ├── base.py                # 插件接口
│   ├── builtin/               # 内置插件
│   │   ├── statistics.py      # 基础统计
│   │   ├── line_chart.py      # Matplotlib 折线图
│   │   ├── histogram.py       # Matplotlib 直方图
│   │   └── heatmap.py         # Matplotlib 热力图
│   └── external/              # 外部数据源插件
│       ├── netcdf_source.py   # NetCDF 数据源
│       └── zarr_source.py     # Zarr 数据源
├── services/                  # 服务
│   ├── search.py              # 搜索
│   └── exporter.py            # 导出（CSV + NumPy）
└── tests/                     # 测试
```

## 🔧 配置

编辑 `config.json`:

```json
{
  "ui": {
    "theme": "dark",
    "sidebarWidth": 280
  },
  "folder": {
    "fileFilters": [".h5", ".hdf5", ".hdf", ".h5py", ".nc", ".nc4", ".netcdf", ".zarr"]
  }
}
```

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `ui.theme` | 主题：`dark` / `light` | `dark` |
| `ui.sidebarWidth` | 左侧边栏宽度（px） | `280` |
| `ui.secondaryPanelWidth` | 右侧面板宽度（px） | `280` |
| `ui.secondaryPanelVisible` | 右侧面板是否显示 | `false` |
| `folder.fileFilters` | 文件过滤器支持的扩展名 | 见上 |

主题切换后自动持久化到 `config.json`。

右侧面板（Search + Plugins）显示/隐藏状态也会持久化。

## 🧪 测试

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

## 📦 打包

### Linux

```bash
python build.py --all
```

### Windows

```bat
build_windows.bat
```

打包产物位于 `dist/HDF5Viewer/`，Linux 下需确保安装 `libxcb-cursor0`：
```bash
sudo apt install libxcb-cursor0
```

## 📋 版本历史

### v0.2.1

- ✅ 编辑模式按钮内嵌到每个标签页的 Slice 工具栏（✏️ Edit + 💾 Save，每个标签页独立控制）
- ✅ Plugins 追踪最近激活的数据集（双击/搜索/切换标签页均更新插件面板数据源）
- ✅ 右侧 Activity Bar 始终可见（关闭面板只隐藏内容区，不隐藏按钮栏）
- ✅ 标签页拖出独立窗口功能暂时禁用

### v0.2.0

- ✅ 插件面板 UI（Activity Bar 🔌 入口 + 可视化插件选择 + 参数配置）
- ✅ Matplotlib 可视化（折线图/直方图/热力图，替代 ASCII 渲染）
- ✅ Command Palette（Ctrl+Shift+P，14 个命令）+ 主题跟随切换
- ✅ 标签拖拽排序（拖出独立窗口功能暂未启用）
- ✅ Dark/Light 主题切换 + 配置持久化（CommandPalette/SecondaryBar/SecondaryPanel 全部跟随）
- ✅ NetCDF/Zarr 条件注册（可选依赖，缺失时静默跳过）
- ✅ NumPy (.npy) 导出
- ✅ 数据编辑模式（Toggle Edit Mode + 单元格编辑 + Save 回写文件）
- ✅ 右侧面板栏（Search + Plugins 独立面板，与 Explorer 同时可见）
- ✅ 右键菜单修复（Split Right/Down 垂直嵌套、Close/Others/All 全部可用）
- ✅ Split Down 真正的垂直嵌套分割（QSplitter 嵌套）
- ✅ 121 项测试全面覆盖

### v0.1.0

- 初始版本
- VSCode 风格界面
- HDF5 文件浏览 + 异步加载
- 多标签 + Split
- CSV 导出
- 全局搜索
- Attributes 查看

## 📄 许可证

MIT License
