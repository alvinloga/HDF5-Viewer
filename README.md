# HDF5 Viewer

轻量级 HDF5 文件浏览器，仿 VSCode 布局设计，支持大文件懒加载、多标签 Split。

## ✨ 特性

- 🎨 **VSCode 风格界面** — Activity Bar + 侧边栏 + 编辑区 + 底部面板
- 📑 **多标签 + Split** — 同时查看多个文件/数据集，支持左右/上下分屏
- 🚀 **大文件异步加载** — 异步加载 + 分页，UI 不卡
- 📊 **Attributes 独立标签页** — 底部面板独立显示属性，双击可在新标签页查看属性值
- 🔍 **全局搜索** — 搜索 HDF5 节点路径
- 💾 **CSV 导出** — 数据集导出为 CSV 格式
- 📂 **文件夹浏览器** — 侧边栏浏览本地文件夹，拖放打开
- 🔌 **插件框架** — 可扩展的分析/可视化插件接口（代码层面可用）

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
| 切换侧边栏 | Activity Bar 图标点击 |
| Split 视图 | 右键标签 → Split Right/Down |
| 切换底部面板 | `Ctrl+J` |
| 搜索节点 | `Ctrl+Shift+F` |

### 切片控制

- **手动输入**: 在 Slice 输入框输入 `[0:100, :]`
- **快捷按钮**: First 100 / Last 100 / All
- **维度选择**: 高维数据可选择查看维度

### Attributes 查看

- 底部面板切换到 **Attributes** 标签页查看属性列表
- **双击**属性行可在编辑区新标签页打开属性值的表格视图

### 插件系统

插件类型：
- **SourcePlugin** — 数据源扩展（HDF5、NetCDF 等）
- **AnalyzePlugin** — 统计分析
- **VisualizePlugin** — 可视化

内置插件（代码层面已实现，暂无 UI 入口）：
- Basic Statistics — 基础统计（均值、标准差、分位数等）
- Line Chart — ASCII 折线图
- Heatmap — ASCII 热力图
- Histogram — ASCII 直方图

## 🏗️ 项目结构

```
hdf5-viewer/
├── main.py                    # 入口
├── config.json                # 配置
├── core/                      # 核心模块
│   ├── datasource.py          # 数据源接口
│   ├── h5_source.py           # HDF5 实现
│   ├── event_bus.py           # 事件总线
│   ├── slicer.py              # 切片解析
│   ├── cache.py               # LRU 缓存
│   ├── async_loader.py        # 异步加载
│   └── registry.py            # 插件注册
├── gui/                       # GUI 模块
│   ├── main_window.py         # 主窗口
│   ├── activity_bar.py        # 活动栏
│   ├── sidebar/               # 侧边栏
│   │   ├── explorer.py        # HDF5 文件树
│   │   └── folder_explorer.py # 本地文件夹浏览器
│   ├── editor/                # 编辑器
│   │   ├── tab_manager.py     # 标签页管理
│   │   ├── file_panel.py      # 数据集面板
│   │   ├── data_table.py      # 数据表格
│   │   └── attr_panel.py      # 属性值面板
│   └── bottom_panel.py        # 底部面板（Properties/Attributes/Output）
├── plugins/                   # 插件系统
│   ├── base.py                # 插件接口
│   └── builtin/               # 内置插件
├── services/                  # 服务
│   ├── search.py              # 搜索
│   └── exporter.py            # 导出
└── tests/                     # 测试
```

## 🔧 配置

编辑 `config.json`:

```json
{
  "viewer": {
    "maxPreviewRows": 200,
    "maxPreviewCols": 100,
    "maxPreviewBytes": 52428800
  },
  "cache": {
    "maxSizeMb": 512
  },
  "ui": {
    "theme": "dark",
    "sidebarWidth": 280
  }
}
```

## 🧪 测试

```bash
python build.py --test
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

## 📋 后续开发计划

### v0.2.0 — 补完框架缺失 UI

- [ ] 插件面板 UI（Activity Bar 🔌 按钮已有但无面板，用户无法在界面中触发插件）
- [ ] 图形化可视化（集成 Matplotlib，替代当前 ASCII 文本渲染）

### v0.2.x — 交互体验补全

- [ ] 标签拖拽成独立窗口（信号已定义，处理逻辑未实现）
- [ ] Command Palette (Ctrl+Shift+P)
- [ ] 主题配置（dark/light 切换）

### v0.3.0 — 功能扩展

- [ ] NetCDF/Zarr 支持
- [ ] NumPy 格式导出
- [ ] 数据编辑（当前只读）

## 📄 许可证

MIT License
