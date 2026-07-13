# Data Viewer

[中文](README.md) | [English](README_EN.md)

Data Viewer 是面向科研人员、数据工程师和算法开发者的跨平台桌面科研数据工作台。产品目标是可靠完成查看、分析、比较、安全编辑和导出，而不是只提供文件预览。

## 项目状态

仓库目前处于架构重构准备阶段。

- `main.py`、`core/`、`gui/`、`plugins/`、`services/` 是旧版 HDF5 Viewer v0.3.1 之前的实现。
- 旧版只应视为迁移输入，不代表本文档描述的目标能力已经完成。
- Data Viewer 的目标规范、公共接口和执行顺序已经写入 `docs/`、`ARCHITECTURE.md` 和 `tasks/`。
- 后续实现必须按任务清单逐步迁移，不允许通过一次性重写跳过行为测试。

当前已知基线问题：

- GUI 测试在当前开发环境中无法完整收集；
- 旧测试报告中的“121 项全部通过”不能作为当前证据；
- 旧编辑、导出、Split、异步加载和可选数据源存在已确认的正确性问题；
- 当前构建产物和应用内部仍使用 `HDF5Viewer` 名称，名称迁移属于实施任务。

## 产品定位

核心工作流：

```text
打开数据 -> 浏览结构 -> 选择切片 -> 查看 -> 分析/可视化
         -> 比较 -> 安全编辑 -> 导出 -> 保存工作区
```

产品原则：

- 默认只读，编辑必须显式进入并经过保存确认；
- 小数据全量处理，中等数据分块，超大数据默认采样且明确标识；
- 所有统计结果记录数据范围、参数、采样策略和插件版本；
- 不做隐式空间重采样、不执行不可信序列化对象、不加载不可信代码插件；
- Windows 和 Linux 必须同时通过验收才能发布。

## 首版格式范围

| 格式 | 数据域 | 首版读取 | 首版编辑 | 说明 |
|---|---|---:|---:|---|
| HDF5 `.h5/.hdf5/.hdf/.h5py` | 层级数组 | 是 | 是 | 切片 patch 写回 |
| NumPy `.npy` | 数组 | 是 | 是 | 原子替换或另存为 |
| NumPy `.npz` | 多数组 archive | 是 | 是 | 整体重建 archive，禁止 pickle |
| CSV `.csv` | 表格 | 是 | 是 | 打开前确认解析参数 |
| TSV `.tsv` | 表格 | 是 | 是 | 与 CSV 共用适配器 |
| TXT `.txt` | 文本/表格 | 是 | 是 | 无法可靠推断表格时退回文本视图 |
| MATLAB `.mat` | 层级数组 | 是 | 否 | 传统 MAT 与 HDF5 MAT；只读、导出 |
| NIfTI `.nii/.nii.gz` | 医学体数据 | 是 | 否 | 保留 affine、orientation 和 header |
| Excel `.xlsx` | Workbook | 是 | 否 | 不执行宏、外部链接或公式代码 |
| JSON `.json` | 结构化数据 | 是 | 否 | 树/记录集视图 |
| YAML `.yaml/.yml` | 结构化数据 | 是 | 否 | 仅安全解析 |
| 上述格式的 `.gz` 包装 | 压缩包装 | 是 | 否 | Save As；二进制格式先解压到受控缓存 |

NetCDF 和 Zarr 不在首版范围。后续格式路线依次考虑 Parquet、Arrow IPC、DICOM、NRRD/MHA、OME-TIFF、FITS、SQLite 和 EEG/MEG 格式。

完整能力矩阵见 [格式规范](docs/FORMAT_SUPPORT.md)。

## 目标能力

### 数据浏览

- 层级节点按需加载；
- 虚拟化表格和有界缓存；
- 标量、1D、2D、高维、结构化 dtype、字符串和医学体数据使用专门视图；
- 路径面包屑、收藏、历史导航、Recent Files；
- 高级搜索支持路径、类型、dtype、维数和正则表达式。

### 分析与可视化

- Dataset Profile、描述统计、分布、相关矩阵和数据集比较；
- Line、Scatter、Histogram、Box Plot、Image Viewer、Slice Navigator；
- NIfTI 三正交视图、联动十字线、voxel/world coordinate；
- 所有插件通过稳定 Plugin API 增量开发。

### 工作区

- 保存打开文件、标签、Split、切片、收藏、比较关系和插件参数；
- 使用版本化 JSON manifest；
- 默认引用外部数据，不嵌入大型科研文件；
- 路径失效时进入 degraded 状态并支持重新定位。

### 安全编辑

- 修改记录为 patch，不直接修改展示数组；
- 支持撤销、重做、放弃和保存摘要；
- 保存前检查源文件是否被外部修改；
- 支持原子替换和 Save As；
- gzip 包装、MAT、NIfTI、XLSX、JSON、YAML 首版只读。

## 设计方向

Data Viewer 使用专业、安静、高信息密度的桌面工具语言：

- Fluent 2 和现代 IDE 启发的原生 Qt 设计；
- `DESIGN_VARIANCE 4 / MOTION_INTENSITY 2 / VISUAL_DENSITY 8`；
- 单一语义 token 系统覆盖深浅主题；
- 一套单色图标，不使用 emoji 按钮；
- 动效只表达加载、焦点和状态变化；
- 完整支持 loading、empty、error、dirty、read-only、disabled 和 keyboard focus 状态。

完整规范见 [UI/UX 规范](docs/UI_UX_SPEC.md)。

## 文档入口

| 文档 | 用途 |
|---|---|
| [AGENTS.md](AGENTS.md) | 后续 agent 必读规则和工作顺序 |
| [产品规范](docs/PRODUCT_SPEC.md) | 需求、边界、成功标准 |
| [目标架构](ARCHITECTURE.md) | 模块边界、数据流、状态机 |
| [格式规范](docs/FORMAT_SUPPORT.md) | 每种格式的读取、编辑和 gzip 语义 |
| [DataSource API](docs/DATASOURCE_API.md) | 数据源公共接口 |
| [Plugin API](docs/PLUGIN_API.md) | 插件 v1 契约和示例 |
| [工作区格式](docs/WORKSPACE_FORMAT.md) | `.dvw` manifest schema |
| [安全编辑](docs/SAFE_EDITING.md) | patch、冲突检测、原子保存 |
| [UI/UX 规范](docs/UI_UX_SPEC.md) | 信息架构、设计系统、状态和无障碍 |
| [测试规范](docs/TESTING.md) | 测试层级、CI、性能预算 |
| [依赖策略](docs/DEPENDENCIES.md) | 运行时/开发依赖和安全规则 |
| [迁移策略](docs/MIGRATION.md) | 从旧版 HDF5 Viewer 增量迁移及删除条件 |
| [ADR 索引](docs/decisions/README.md) | 已接受架构决策 |
| [文档总索引](docs/INDEX.md) | 权威顺序和按任务必读文档 |
| [实施计划](tasks/plan.md) | 依赖图、阶段和 checkpoint |
| [任务清单](tasks/todo.md) | 可逐项执行的任务、验收和验证 |

## 当前遗留版本快速启动

这些命令只用于审计和迁移旧实现，不代表目标版本已经完成。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
QT_QPA_PLATFORM=xcb python main.py
```

目标开发环境和命令将在 Phase 0 建立，随后以 `docs/PRODUCT_SPEC.md` 中的命令为唯一准则。

## 当前验证基线

初始只读审查已经被当前锁定的 Windows/Linux 基线取代：

- `uv sync --locked --all-extras` 在独立 CPython 3.12 环境与 Windows/Ubuntu CI 均通过；
- 首版直接依赖（包括 PyQt6）在两端导入通过；
- 全量 `pytest --collect-only -q` 收集 177 项；全量执行为 176 passed、1 skipped；
- 当前 CI 已验证锁定安装、lint/type、编译、collection、offscreen GUI 回归、JUnit/manifest 证据上传及源码包/wheel 构建；
- release gate 已验证质量测试失败会阻断后续发版 job；
- 发布仍受未实现的 v1 功能、artifact smoke、SBOM/许可证决策等门禁约束；
- 静态计数与历史“121 tests / 100%”宣传仍不可作为当前证据。

当前证据见 [测试状态](TEST_REPORT.md)。任何后续 agent 都不得把旧报告复制为新结论。

## 贡献流程

1. 阅读 `AGENTS.md`、产品规范和相关 ADR；
2. 从 `tasks/todo.md` 选择一个未完成任务；
3. 先写失败测试，再实现最小垂直切片；
4. 每个任务控制在约 3-5 个文件；
5. 运行任务指定验证和全量回归；
6. 更新任务状态、文档和变更日志；
7. Windows/Linux 相关行为必须同时验证。

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

仓库源代码当前使用 MIT License。PyQt6 自身采用 GPLv3 或商业许可，正式分发 Data Viewer 前必须完成依赖许可审查并确认发布方式与所选 PyQt6 许可兼容。
