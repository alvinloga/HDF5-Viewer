# TODO — HDF5 Viewer 开发任务

## v0.1.0 已完成

### 核心框架
- [x] config.json 统一配置
- [x] core/event_bus.py 事件总线
- [x] core/datasource.py 数据源抽象接口
- [x] core/h5_source.py HDF5 实现
- [x] core/slicer.py 切片解析
- [x] core/cache.py LRU 缓存
- [x] core/registry.py 插件注册中心
- [x] core/async_loader.py 异步加载器

### GUI 基础
- [x] gui/main_window.py VSCode 风格主窗口
- [x] gui/activity_bar.py 左侧 Activity Bar
- [x] gui/sidebar/explorer.py 文件树 Explorer
- [x] gui/sidebar/folder_explorer.py 文件夹浏览器
- [x] gui/editor/tab_manager.py 标签页管理
- [x] gui/editor/file_panel.py 数据集面板
- [x] gui/editor/data_table.py 数据表格视图
- [x] gui/editor/attr_panel.py 属性值面板
- [x] gui/bottom_panel.py 底部面板（Properties/Attributes/Output）
- [x] gui/status_bar.py 状态栏
- [x] main.py 入口整合

### 核心功能
- [x] 多标签页 + Split（左右/上下分屏）
- [x] 切片输入控件（手动输入 + 快捷按钮 + 维度选择）
- [x] 右键菜单（Explorer + Tab）
- [x] 大文件异步加载 + 分页
- [x] LRU Cache 集成
- [x] Attributes 独立标签页显示，双击查看属性值详情
- [x] 全局搜索节点
- [x] CSV 导出
- [x] 拖拽打开文件/文件夹
- [x] 文件夹浏览器（懒加载、文件过滤）

### 插件框架
- [x] plugins/base.py 三类插件接口（Source/Analyze/Visualize）
- [x] PluginManager 插件管理器
- [x] plugins/builtin/statistics.py 基础统计（代码层面可用）
- [x] plugins/builtin/line_chart.py ASCII 折线图（代码层面可用）
- [x] plugins/builtin/heatmap.py ASCII 热力图（代码层面可用）
- [x] plugins/builtin/histogram.py ASCII 直方图（代码层面可用）

### 测试
- [x] test_core.py ✅
- [x] test_phase1.py ✅
- [x] test_final.py ✅
- [x] 文件夹浏览器 e2e 测试 ✅

---

## v0.2.0 开发计划

### 第一优先级：补完已有框架的缺失 UI

- [ ] 插件面板 UI
  - Activity Bar 🔌 按钮已有，但点击无面板
  - 需要做插件列表面板，用户可选择插件对当前数据集执行分析/可视化
  - 分析结果展示区域
  - 可视化结果展示区域

- [ ] 图形化可视化
  - 集成 Matplotlib，替代当前 ASCII 文本渲染
  - 折线图 → Matplotlib Line Chart
  - 热力图 → Matplotlib Heatmap (imshow)
  - 直方图 → Matplotlib Histogram
  - 需要添加 matplotlib 依赖

### 第二优先级：交互体验补全

- [ ] 标签拖拽成独立窗口
  - tab_dragged_out 信号已定义，但未连接处理逻辑
  - 需要实现拖出标签 → 创建新 QMainWindow

- [ ] Command Palette
  - Ctrl+Shift+P 命令面板
  - 快速搜索和执行操作

- [ ] 主题配置
  - config.json 已有 theme 字段，但未实现切换逻辑
  - 支持至少 dark/light 两套主题

### 第三优先级：功能扩展

- [ ] NetCDF/Zarr 支持
  - 实现 SourcePlugin 接口
  - 添加 netcdf4 / zarr 依赖

- [ ] NumPy 格式导出
  - exporter.py 已有 to_npy 方法，但 UI 未接入
  - 在导出菜单中添加 .npy 选项

- [ ] 数据编辑
  - 当前只读
  - 支持修改 HDF5 数据（需谨慎设计，涉及文件写入安全）
