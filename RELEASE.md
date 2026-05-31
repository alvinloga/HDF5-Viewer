# HDF5 Viewer v0.1.0 — Release Notes

**发布日期**: 2026-05-27  
**测试状态**: ✅ 全部 66 项测试通过  

---

## 🎉 发布说明

HDF5 Viewer v0.1.0 是一个轻量级的 HDF5 文件查看器，采用 VSCode 风格界面设计。

### 已完成功能

- **多标签页 + Split** — 支持多文件同时查看，支持左右/上下分屏
- **大数据异步加载** — 异步加载 + 分页，UI 不卡
- **智能切片** — 默认限制 200x100，避免大数据卡顿
- **Attributes 独立标签页** — 底部面板独立显示，双击可查看属性值详情
- **数据导出** — 支持导出为 CSV 格式
- **全局搜索** — 搜索 HDF5 节点路径
- **文件夹浏览器** — 侧边栏浏览本地文件夹
- **拖拽打开文件** — 拖拽文件/文件夹到窗口直接打开

### 已测试功能

| 功能 | 测试状态 |
|------|----------|
| 文件打开/关闭 | ✅ |
| 文件树浏览 | ✅ |
| 数据表格显示 | ✅ |
| 切片功能 | ✅ |
| 异步加载 | ✅ |
| 数据导出 | ✅ |
| 标签页管理 | ✅ |
| Split 功能 | ✅ |
| 搜索功能 | ✅ |
| 拖拽打开 | ✅ |
| Attributes 显示 | ✅ |

### 已修复问题

- 右键 "Open in New Tab" 空白问题
- leadfield 大数据集加载卡死问题
- CSV 导出失效问题
- 1D 数据显示列数错误问题

---

## 📦 打包信息

### Linux 版本

```bash
python build.py --all
cd dist/HDF5Viewer/
./run.sh [file.h5]
```

### Windows 版本

```bat
build_windows.bat
dist\HDF5Viewer\HDF5Viewer.exe [file.h5]
```

---

## 🧪 测试报告

详细测试报告请查看 [TEST_REPORT.md](TEST_REPORT.md)

---

## 📋 后续开发计划

- [ ] 图形化可视化（Matplotlib 集成，替代当前 ASCII 渲染）
- [ ] 插件面板 UI（用户可在界面中触发插件）
- [ ] 标签拖拽成独立窗口
- [ ] Command Palette (Ctrl+Shift+P)
- [ ] 主题配置
- [ ] NetCDF/Zarr 支持

---

**发布者**: Alvin  
**日期**: 2026-05-27
