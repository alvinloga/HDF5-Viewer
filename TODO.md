# TODO — HDF5 Viewer 开发任务

## Phase 0: 骨架（最小可用） ✅ 完成

- [x] 1. config.json 统一配置
- [x] 2. core/event_bus.py 事件总线
- [x] 3. core/datasource.py 数据源抽象接口
- [x] 4. core/h5_source.py HDF5 实现
- [x] 5. core/slicer.py 切片解析
- [x] 6. core/cache.py LRU 缓存
- [x] 7. core/registry.py 插件注册中心
- [x] 8. core/async_loader.py 异步加载器
- [x] 9. gui/main_window.py VSCode 风格主窗口框架
- [x] 10. gui/activity_bar.py 左侧 Activity Bar
- [x] 11. gui/sidebar/explorer.py 文件树 Explorer
- [x] 12. gui/editor/tab_manager.py 标签页管理（基础）
- [x] 13. gui/editor/file_panel.py 单文件面板
- [x] 14. gui/editor/data_table.py 数据表格视图
- [x] 15. gui/status_bar.py 状态栏
- [x] 16. main.py 入口整合
- [x] 17. tests/test_core.py 核心模块测试

## Phase 1: 核心体验 ✅ 完成

- [x] 18. Split 功能（左右/上下）
- [x] 19. 标签拖拽成独立窗口
- [x] 20. 切片输入控件增强（快捷切片按钮）
- [x] 21. 右键菜单（Explorer + Tab）

## Phase 2: 大文件优化 ✅ 完成

- [x] 22. core/async_loader.py 异步加载
- [x] 23. 分页滚动加载（DataTable 内置）
- [x] 24. LRU Cache 集成

## Phase 3: 扩展能力 ✅ 完成

- [x] 25. gui/bottom_panel.py 属性面板
- [x] 26. services/search.py 搜索服务
- [x] 27. services/exporter.py 导出 CSV

## Phase 4: 插件框架 ✅ 完成

- [x] 28. plugins/base.py 三类插件接口
- [x] 29. PluginManager 插件管理器

## Phase 5: 内置插件 ✅ 完成

- [x] 30. plugins/builtin/statistics.py 基础统计
- [x] 31. plugins/builtin/line_chart.py 折线图
- [x] 32. plugins/builtin/heatmap.py 热力图
- [x] 33. plugins/builtin/histogram.py 直方图

## Phase 6: 体验打磨

- [ ] 34. 快捷键系统（部分完成）
- [ ] 35. 主题配置
- [x] 36. 拖拽打开文件（已实现）
- [ ] 37. Command Palette (Ctrl+Shift+P)

## Phase 7: 文件夹浏览器 ✅ 完成

- [x] 38. gui/sidebar/folder_explorer.py 文件夹浏览器组件（懒加载、文件过滤）
- [x] 39. config.json 新增 folder 配置段
- [x] 40. EventBus 新增 FOLDER_OPENED/FOLDER_CLOSED/FILE_TAB_ACTIVATED
- [x] 41. MainWindow 集成 Open Folder / Close Folder 菜单
- [x] 42. 侧边栏双层结构（FolderExplorer + Explorer + Search）
- [x] 43. TabManager.tab_activated 信号，标签切换联动 Explorer 树
- [x] 44. 拖放文件夹支持
- [x] 45. _update_explorer_for_file 统一更新逻辑

## 测试结果

- [x] test_core.py ✅
- [x] test_phase1.py ✅
- [x] test_final.py ✅
- [x] 文件夹浏览器 e2e 测试 ✅（10/10 通过）
