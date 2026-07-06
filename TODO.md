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
- [x] plugins/builtin/statistics.py 基础统计
- [x] plugins/builtin/line_chart.py 折线图
- [x] plugins/builtin/heatmap.py 热力图
- [x] plugins/builtin/histogram.py 直方图

### 测试
- [x] test_core.py
- [x] test_phase1.py
- [x] test_final.py
- [x] 文件夹浏览器 e2e 测试

---

## v0.2.0 — 已全部完成 ✅

### 第一优先级：补完已有框架的缺失 UI

- [x] 插件面板 UI
  - Activity Bar 🔌 按钮点击打开插件列表面板
  - 选择插件对当前数据集执行分析/可视化
  - 分析结果展示区域
  - 可视化结果展示区域

- [x] 图形化可视化
  - 集成 Matplotlib，替代 ASCII 文本渲染
  - 折线图 → Matplotlib Line Chart
  - 热力图 → Matplotlib Heatmap (imshow)
  - 直方图 → Matplotlib Histogram

### 第二优先级：交互体验补全

- [x] Command Palette
  - Ctrl+Shift+P 命令面板
  - 14 个命令 + 模糊搜索
  - 主题跟随切换

- [x] 主题配置
  - config.json 的 theme 字段实现切换逻辑
  - Dark/Light 两套主题
  - 配置自动持久化

- [x] 标签拖拽排序
  - 标签页可拖拽改变排列顺序
  - 拖出独立窗口功能暂未启用

### 第三优先级：功能扩展

- [x] NetCDF/Zarr 支持
  - 实现 SourcePlugin 接口
  - 可选依赖，缺失时静默跳过

- [x] NumPy 格式导出
  - exporter.py 的 to_npy 方法
  - UI 中导出菜单添加 .npy 选项

- [x] 数据编辑
  - 支持修改 HDF5 数据
  - 编辑模式切换 + 单元格编辑 + Save 回写

---

## v0.2.1 — 已全部完成 ✅

- [x] 编辑模式按钮内嵌到每个标签页的 Slice 工具栏
  - ✏️ Edit + 💾 Save，每个标签页独立控制
- [x] Plugins 追踪最近激活的数据集
  - 双击/搜索/切换标签页均更新插件面板数据源
- [x] 右侧 Activity Bar 始终可见
  - 关闭面板只隐藏内容区，不隐藏按钮栏
- [x] 标签页拖出独立窗口功能暂时禁用

---

## v0.3.0 开发计划

### 代码清理
- [ ] 清理重复文件（移除废弃的测试和配置文件）
- [ ] 统一代码风格和命名规范
- [ ] 移除过时的注释和废弃代码

### 标签功能
- [ ] 标签拖出独立窗口功能实现
  - 实现 tab_dragged_out 信号处理逻辑
  - 拖出标签 → 创建新 QMainWindow
  - 独立窗口的数据同步

### 功能扩展
- [ ] 数据集合并/对比功能
  - 选择两个数据集进行对比
  - 可视化差异展示
- [ ] 更丰富的插件生态
  - 插件市场概念
  - 从外部文件加载插件
- [ ] 数据筛选和过滤
  - 按条件过滤数据集行
  - 支持基本统计过滤

### 性能优化
- [ ] 超大文件懒加载策略改进
  - 分块读取优化
  - 内存使用优化
- [ ] 启动速度优化
  - 延迟导入非必需模块
  - 缓存编译结果

### 测试增强
- [ ] 新增插件系统测试
- [ ] 增加跨平台测试覆盖
- [ ] 性能基准测试自动化
