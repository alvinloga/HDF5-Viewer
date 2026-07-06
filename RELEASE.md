# HDF5 Viewer v0.2.1 — Release Notes

**发布日期**: 2026-07-06  
**测试状态**: ✅ 全部 121 项测试通过  

---

## 🎉 发布说明

HDF5 Viewer v0.2.1 是一个轻量级的 HDF5 文件查看器，采用 VSCode 风格界面设计。此版本在 v0.2.0 的基础上进一步打磨交互体验。

### v0.2.1 更新内容

- ✅ 编辑模式按钮内嵌到每个标签页的 Slice 工具栏（✏️ Edit + 💾 Save，每个标签页独立控制）
- ✅ Plugins 追踪最近激活的数据集（双击/搜索/切换标签页均更新插件面板数据源）
- ✅ 右侧 Activity Bar 始终可见（关闭面板只隐藏内容区，不隐藏按钮栏）
- ✅ 标签页拖出独立窗口功能暂时禁用

### v0.2.0 功能更新

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

### 已测试功能

| 功能 | 测试状态 |
|------|----------|
| 文件打开/关闭 | ✅ |
| 文件树浏览 | ✅ |
| 数据表格显示 | ✅ |
| 切片功能 | ✅ |
| 异步加载 | ✅ |
| 数据导出 (CSV + NumPy) | ✅ |
| 标签页管理 | ✅ |
| Split 功能 | ✅ |
| 搜索功能 | ✅ |
| 拖拽打开 | ✅ |
| Attributes 显示 | ✅ |
| 主题切换 | ✅ |
| 数据编辑 | ✅ |
| 可视化插件 | ✅ |
| Command Palette | ✅ |

---

## 📦 打包信息

### 打包方式

```bash
# Linux — OneDir 方式
python build.py --all
cd dist/HDF5Viewer/
./run.sh [file.h5]

# Windows
build_windows.bat
dist\HDF5Viewer\HDF5Viewer.exe [file.h5]
```

**打包方式**: OneDir（目录模式），便于调试和排查依赖问题。

---

## 🧪 测试报告

详细测试报告请查看 [TEST_REPORT.md](TEST_REPORT.md)

**测试概览**: 121 项测试全部通过，覆盖主题切换、数据编辑、标签操作、搜索、插件、边界情况等。

---

## 📋 后续开发计划

### v0.3.0

- [ ] 清理重复文件（移除废弃的测试和配置文件）
- [ ] 标签拖出独立窗口功能
- [ ] 更丰富的插件生态
- [ ] 数据集合并/对比功能
- [ ] 性能优化（更大文件的懒加载策略改进）

---

**发布者**: Alvin  
**日期**: 2026-07-06
