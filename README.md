# HDF5 Viewer

轻量级 HDF5 文件浏览器，仿 VSCode 布局设计，支持大文件懒加载、多标签 Split、插件扩展。

## ✨ 特性

- 🎨 **VSCode 风格界面** — 熟悉的操作体验
- 📑 **多标签 + Split** — 同时查看多个文件/数据集
- 🚀 **大文件友好** — GB 级文件秒开，懒加载
- 🔌 **插件系统** — 可扩展的统计和可视化插件
- 📊 **内置插件** — 统计、折线图、热力图、直方图
- 💾 **CSV 导出** — 数据导出为 CSV 格式
- 🔍 **全局搜索** — 快速查找节点

## 🚀 快速开始

### 从源码运行

```bash
# 克隆项目
git clone <repo-url>
cd hdf5-viewer

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install PyQt6 h5py numpy

# 运行
python main.py [file.h5]
```

### 使用打包版本

#### Linux

```bash
# 下载并解压
cd dist/HDF5Viewer/
./run.sh [file.h5]
```

#### Windows

1. 在 Windows 上运行 `build_windows.bat`
2. 或手动构建: `pyinstaller HDF5Viewer.spec`
3. 运行 `dist\HDF5Viewer\HDF5Viewer.exe`

## 📖 使用指南

### 基本操作

| 操作 | 说明 |
|------|------|
| 打开文件 | `Ctrl+O` 或拖拽文件到窗口 |
| 关闭标签 | `Ctrl+W` |
| 切换面板 | Activity Bar 图标点击 |
| Split 视图 | 右键标签 → Split Right/Down |
| 拖拽成窗口 | 拖拽标签到窗口外 |

### 切片控制

- **手动输入**: 在 Slice 输入框输入 `[0:100, :]`
- **快捷按钮**: First 100 / Last 100 / All
- **维度选择**: 高维数据可选择查看维度

### 插件系统

插件类型：
- **SourcePlugin** — 数据源（HDF5、NetCDF 等）
- **AnalyzePlugin** — 统计分析
- **VisualizePlugin** — 可视化

内置插件：
- Basic Statistics — 基础统计（均值、标准差、分位数等）
- Line Chart — 折线图
- Heatmap — 热力图
- Histogram — 直方图

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
│   └── registry.py            # 插件注册
├── gui/                       # GUI 模块
│   ├── main_window.py         # 主窗口
│   ├── activity_bar.py        # 活动栏
│   ├── sidebar/               # 侧边栏
│   ├── editor/                # 编辑器
│   └── bottom_panel.py        # 底部面板
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
    "maxPreviewRows": 1000,
    "maxPreviewCols": 100,
    "maxPreviewBytes": 104857600
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
# 运行所有测试
python tests/test_core.py
python tests/test_phase1.py
python tests/test_final.py

# 或使用构建脚本
python build.py --test
```

## 📦 打包

### Linux

```bash
python build.py --all
```

### Windows

```batch
build_windows.bat
```

或手动:

```batch
python build.py --windows
pyinstaller HDF5Viewer.spec
```

## 🛠️ 开发

### 添加新插件

1. 在 `plugins/builtin/` 创建新文件
2. 实现 `AnalyzePlugin` 或 `VisualizePlugin` 接口
3. 在 `core/registry.py` 的 `load_builtin_plugins()` 中注册

### 添加新数据源

1. 在 `core/` 创建新文件
2. 实现 `DataSource` 接口
3. 在 `core/registry.py` 中注册

## 📋 TODO

- [ ] Command Palette (Ctrl+Shift+P)
- [ ] 主题配置
- [ ] 更多可视化插件
- [ ] NetCDF/Zarr 支持
- [ ] 数据导出为 NumPy 格式

## 📄 许可证

MIT License

## 🙏 致谢

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- [h5py](https://www.h5py.org/)
- [NumPy](https://numpy.org/)
