"""Small centralized UI string catalog for Data Viewer native Qt surfaces."""

from __future__ import annotations

from enum import StrEnum


class Locale(StrEnum):
    """Locales supported by the v1 UI baseline."""

    EN_US = "en-US"
    ZH_CN = "zh-CN"


class UiStringKey(StrEnum):
    """Stable keys for user-visible shell/dialog/state text."""

    APP_TITLE = "app.title"
    PATH_INPUT_PLACEHOLDER = "path.input.placeholder"
    SOURCE_PATH_LABEL = "path.source.label"
    COMMAND_OPEN = "command.open"
    COMMAND_CANCEL_OPEN = "command.cancel_open"
    COMMAND_REVIEW_CHANGES = "command.review_changes"
    COMMAND_SAVE = "command.save"
    COMMAND_SAVE_AS = "command.save_as"
    COMMAND_EXPORT = "command.export"
    COMMAND_LOAD_SLICE = "command.load_slice"
    COMMAND_CANCEL = "command.cancel"
    COMMAND_RETRY = "command.retry"
    COMMAND_DETAILS = "command.details"
    COMMAND_OPEN_SOURCE = "command.open_source"
    COMMAND_CLEAR_FILTER = "command.clear_filter"
    COMMAND_REFINE = "command.refine"
    COMMAND_UNAVAILABLE = "command.unavailable"
    COMMAND_RELOAD_SOURCE = "command.reload_source"
    COMMAND_RECOMPUTE = "command.recompute"
    EDIT_CLEAN = "edit.clean"
    HINT_NO_SOURCE = "hint.no_source"
    NAVIGATION_HEADER = "navigation.header"
    ACCESSIBLE_PATH_INPUT = "accessible.path_input"
    ACCESSIBLE_NAVIGATION = "accessible.navigation"
    ACCESSIBLE_INSPECTOR_OVERVIEW = "accessible.inspector.overview"
    ACCESSIBLE_INSPECTOR_ATTRIBUTES = "accessible.inspector.attributes"
    ACCESSIBLE_INSPECTOR_STATISTICS = "accessible.inspector.statistics"
    ACCESSIBLE_INSPECTOR_PLUGINS = "accessible.inspector.plugins"
    ACCESSIBLE_ACTIVE_SPLIT = "accessible.active_split"
    ACCESSIBLE_WORKSPACE_TABS = "accessible.workspace_tabs"
    ACCESSIBLE_COMMAND_BAR = "accessible.command_bar"
    ACCESSIBLE_BOTTOM_TABS = "accessible.bottom_tabs"
    ACCESSIBLE_OUTPUT_LOG = "accessible.output_log"
    ACCESSIBLE_TASK_ACTIVITY = "accessible.task_activity"
    ACCESSIBLE_PROBLEMS = "accessible.problems"
    ACCESSIBLE_STATUS = "accessible.status"
    INSPECTOR_OVERVIEW_PLACEHOLDER = "inspector.overview.placeholder"
    INSPECTOR_ATTRIBUTES_PLACEHOLDER = "inspector.attributes.placeholder"
    INSPECTOR_STATISTICS_PLACEHOLDER = "inspector.statistics.placeholder"
    INSPECTOR_PLUGINS_PLACEHOLDER = "inspector.plugins.placeholder"
    WORKSPACE_NOT_READY = "workspace.not_ready"
    ACTIVE_SPLIT_DATA = "workspace.active_split.data"
    STATUS_READY = "status.ready"
    STATUS_SOURCE_EMPTY = "status.source.empty"
    STATUS_PATH_EMPTY = "status.path.empty"
    STATUS_SHAPE_EMPTY = "status.shape.empty"
    STATUS_DTYPE_EMPTY = "status.dtype.empty"
    STATUS_SLICE_EMPTY = "status.slice.empty"
    STATUS_MODE_EMPTY = "status.mode.empty"
    STATUS_TASK_IDLE = "status.task.idle"
    STATUS_COORDINATES_EMPTY = "status.coordinates.empty"
    WORKSPACE_INITIAL_MESSAGE = "workspace.initial.message"
    WORKSPACE_READY_MESSAGE = "workspace.ready.message"
    OUTPUT_READY = "output.ready"
    TASKS_NONE = "tasks.none"
    PROBLEMS_NONE = "problems.none"
    TAB_DATA = "tab.data"
    TAB_OVERVIEW = "tab.overview"
    TAB_ATTRIBUTES = "tab.attributes"
    TAB_STATISTICS = "tab.statistics"
    TAB_PLUGINS = "tab.plugins"
    TAB_TASKS = "tab.tasks"
    TAB_OUTPUT = "tab.output"
    TAB_PROBLEMS = "tab.problems"
    PANEL_NAVIGATION = "panel.navigation"
    PANEL_WORKSPACE = "panel.workspace"
    PANEL_INSPECTOR = "panel.inspector"
    DIALOG_SAVE_SUMMARY_TITLE = "dialog.save_summary.title"
    DIALOG_SAVE_CONFIRM = "dialog.save_summary.confirm"
    DIALOG_DESTRUCTIVE_TITLE = "dialog.destructive.title"
    DIALOG_DESTRUCTIVE_CONFIRM = "dialog.destructive.confirm"
    DIALOG_IMPORT_OPTIONS_TITLE = "dialog.import_options.title"
    DIALOG_IMPORT_APPLY = "dialog.import_options.apply"
    STATE_INITIAL_TITLE = "state.initial.title"
    STATE_INITIAL_SUMMARY = "state.initial.summary"
    STATE_LOADING_TITLE = "state.loading.title"
    STATE_LOADING_SUMMARY = "state.loading.summary"
    STATE_EMPTY_TITLE = "state.empty.title"
    STATE_EMPTY_SUMMARY = "state.empty.summary"
    STATE_READY_TITLE = "state.ready.title"
    STATE_READY_SUMMARY = "state.ready.summary"
    STATE_PARTIAL_TITLE = "state.partial.title"
    STATE_PARTIAL_SUMMARY = "state.partial.summary"
    STATE_ERROR_TITLE = "state.error.title"
    STATE_ERROR_SUMMARY = "state.error.summary"
    STATE_DISABLED_TITLE = "state.disabled.title"
    STATE_DISABLED_SUMMARY = "state.disabled.summary"
    STATE_DIRTY_TITLE = "state.dirty.title"
    STATE_DIRTY_SUMMARY = "state.dirty.summary"
    STATE_READ_ONLY_TITLE = "state.read_only.title"
    STATE_READ_ONLY_SUMMARY = "state.read_only.summary"
    STATE_CONFLICTED_TITLE = "state.conflicted.title"
    STATE_CONFLICTED_SUMMARY = "state.conflicted.summary"
    STATE_STALE_TITLE = "state.stale.title"
    STATE_STALE_SUMMARY = "state.stale.summary"


_CATALOG: dict[Locale, dict[UiStringKey, str]] = {
    Locale.EN_US: {
        UiStringKey.APP_TITLE: "Data Viewer",
        UiStringKey.PATH_INPUT_PLACEHOLDER: "Enter source path, then open",
        UiStringKey.SOURCE_PATH_LABEL: "Source path",
        UiStringKey.COMMAND_OPEN: "Open",
        UiStringKey.COMMAND_CANCEL_OPEN: "Cancel Open",
        UiStringKey.COMMAND_REVIEW_CHANGES: "Review Changes",
        UiStringKey.COMMAND_SAVE: "Save",
        UiStringKey.COMMAND_SAVE_AS: "Save As",
        UiStringKey.COMMAND_EXPORT: "Export",
        UiStringKey.COMMAND_LOAD_SLICE: "Load Slice",
        UiStringKey.COMMAND_CANCEL: "Cancel",
        UiStringKey.COMMAND_RETRY: "Retry",
        UiStringKey.COMMAND_DETAILS: "Details",
        UiStringKey.COMMAND_OPEN_SOURCE: "Open source",
        UiStringKey.COMMAND_CLEAR_FILTER: "Clear filter",
        UiStringKey.COMMAND_REFINE: "Refine",
        UiStringKey.COMMAND_UNAVAILABLE: "Unavailable",
        UiStringKey.COMMAND_RELOAD_SOURCE: "Reload source",
        UiStringKey.COMMAND_RECOMPUTE: "Recompute",
        UiStringKey.EDIT_CLEAN: "edit: clean (0 pending)",
        UiStringKey.HINT_NO_SOURCE: "No source loaded",
        UiStringKey.NAVIGATION_HEADER: "Structure",
        UiStringKey.ACCESSIBLE_PATH_INPUT: "Source path input",
        UiStringKey.ACCESSIBLE_NAVIGATION: "Files and structure",
        UiStringKey.ACCESSIBLE_INSPECTOR_OVERVIEW: "Inspector overview",
        UiStringKey.ACCESSIBLE_INSPECTOR_ATTRIBUTES: "Inspector attributes",
        UiStringKey.ACCESSIBLE_INSPECTOR_STATISTICS: "Inspector statistics",
        UiStringKey.ACCESSIBLE_INSPECTOR_PLUGINS: "Inspector plugin provenance",
        UiStringKey.ACCESSIBLE_ACTIVE_SPLIT: "Active split and view",
        UiStringKey.ACCESSIBLE_WORKSPACE_TABS: "Workspace tabs and split group",
        UiStringKey.ACCESSIBLE_COMMAND_BAR: "Command bar",
        UiStringKey.ACCESSIBLE_BOTTOM_TABS: "Tasks, output, and problems",
        UiStringKey.ACCESSIBLE_OUTPUT_LOG: "Output log",
        UiStringKey.ACCESSIBLE_TASK_ACTIVITY: "Task activity",
        UiStringKey.ACCESSIBLE_PROBLEMS: "Problems",
        UiStringKey.ACCESSIBLE_STATUS: "Application status",
        UiStringKey.INSPECTOR_OVERVIEW_PLACEHOLDER: "Select a node to inspect metadata.",
        UiStringKey.INSPECTOR_ATTRIBUTES_PLACEHOLDER: "Attributes for the selected resource appear here.",
        UiStringKey.INSPECTOR_STATISTICS_PLACEHOLDER: "Statistics from built-in plugins will appear here.",
        UiStringKey.INSPECTOR_PLUGINS_PLACEHOLDER: "Compatible plugins and result provenance appear here.",
        UiStringKey.WORKSPACE_NOT_READY: "Workspace: not ready",
        UiStringKey.ACTIVE_SPLIT_DATA: "split: main / view: data",
        UiStringKey.STATUS_READY: "Ready",
        UiStringKey.STATUS_SOURCE_EMPTY: "source: -",
        UiStringKey.STATUS_PATH_EMPTY: "Path: -",
        UiStringKey.STATUS_SHAPE_EMPTY: "shape: -",
        UiStringKey.STATUS_DTYPE_EMPTY: "dtype: -",
        UiStringKey.STATUS_SLICE_EMPTY: "slice: -",
        UiStringKey.STATUS_MODE_EMPTY: "mode: -",
        UiStringKey.STATUS_TASK_IDLE: "task: idle",
        UiStringKey.STATUS_COORDINATES_EMPTY: "coordinates: -",
        UiStringKey.WORKSPACE_INITIAL_MESSAGE: "No source opened yet.",
        UiStringKey.WORKSPACE_READY_MESSAGE: "Open a source and select an ARRAY node.",
        UiStringKey.OUTPUT_READY: "Ready",
        UiStringKey.TASKS_NONE: "No active tasks.",
        UiStringKey.PROBLEMS_NONE: "No problems reported.",
        UiStringKey.TAB_DATA: "Data",
        UiStringKey.TAB_OVERVIEW: "Overview",
        UiStringKey.TAB_ATTRIBUTES: "Attributes",
        UiStringKey.TAB_STATISTICS: "Statistics",
        UiStringKey.TAB_PLUGINS: "Plugins",
        UiStringKey.TAB_TASKS: "Tasks",
        UiStringKey.TAB_OUTPUT: "Output",
        UiStringKey.TAB_PROBLEMS: "Problems",
        UiStringKey.PANEL_NAVIGATION: "Navigation",
        UiStringKey.PANEL_WORKSPACE: "Workspace",
        UiStringKey.PANEL_INSPECTOR: "Inspector",
        UiStringKey.DIALOG_SAVE_SUMMARY_TITLE: "Save summary",
        UiStringKey.DIALOG_SAVE_CONFIRM: "Save reviewed changes",
        UiStringKey.DIALOG_DESTRUCTIVE_TITLE: "Confirm destructive operation",
        UiStringKey.DIALOG_DESTRUCTIVE_CONFIRM: "Confirm operation",
        UiStringKey.DIALOG_IMPORT_OPTIONS_TITLE: "Import options",
        UiStringKey.DIALOG_IMPORT_APPLY: "Apply import options",
        UiStringKey.STATE_INITIAL_TITLE: "Ready to begin",
        UiStringKey.STATE_INITIAL_SUMMARY: "Choose a source or select a resource to continue.",
        UiStringKey.STATE_LOADING_TITLE: "Loading",
        UiStringKey.STATE_LOADING_SUMMARY: "Work is running and can be cancelled when the caller provides cancellation.",
        UiStringKey.STATE_EMPTY_TITLE: "Nothing to show",
        UiStringKey.STATE_EMPTY_SUMMARY: "This state can be valid when the selected source or filter has no results.",
        UiStringKey.STATE_READY_TITLE: "Ready",
        UiStringKey.STATE_READY_SUMMARY: "Content is available with its current scope and provenance.",
        UiStringKey.STATE_PARTIAL_TITLE: "Partial view",
        UiStringKey.STATE_PARTIAL_SUMMARY: "Only a bounded preview, page, slice, or sample is displayed.",
        UiStringKey.STATE_ERROR_TITLE: "Could not complete operation",
        UiStringKey.STATE_ERROR_SUMMARY: "A safe error summary is available. Details are limited to this target.",
        UiStringKey.STATE_DISABLED_TITLE: "Unavailable",
        UiStringKey.STATE_DISABLED_SUMMARY: "This action is disabled until the required context exists.",
        UiStringKey.STATE_DIRTY_TITLE: "Unsaved changes",
        UiStringKey.STATE_DIRTY_SUMMARY: "Review, save, discard, or export changes before closing.",
        UiStringKey.STATE_READ_ONLY_TITLE: "Read-only",
        UiStringKey.STATE_READ_ONLY_SUMMARY: "This source can be inspected and exported, but v1 will not overwrite it.",
        UiStringKey.STATE_CONFLICTED_TITLE: "Conflict detected",
        UiStringKey.STATE_CONFLICTED_SUMMARY: "Saving is blocked until the source is reloaded or changes are saved elsewhere.",
        UiStringKey.STATE_STALE_TITLE: "Stale result",
        UiStringKey.STATE_STALE_SUMMARY: "The source, parameters, or selection changed after this result was produced.",
    },
    Locale.ZH_CN: {
        UiStringKey.APP_TITLE: "Data Viewer",
        UiStringKey.PATH_INPUT_PLACEHOLDER: "输入数据源路径，然后打开",
        UiStringKey.SOURCE_PATH_LABEL: "数据源路径",
        UiStringKey.COMMAND_OPEN: "打开",
        UiStringKey.COMMAND_CANCEL_OPEN: "取消打开",
        UiStringKey.COMMAND_REVIEW_CHANGES: "审查更改",
        UiStringKey.COMMAND_SAVE: "保存",
        UiStringKey.COMMAND_SAVE_AS: "另存为",
        UiStringKey.COMMAND_EXPORT: "导出",
        UiStringKey.COMMAND_LOAD_SLICE: "加载切片",
        UiStringKey.COMMAND_CANCEL: "取消",
        UiStringKey.COMMAND_RETRY: "重试",
        UiStringKey.COMMAND_DETAILS: "详情",
        UiStringKey.COMMAND_OPEN_SOURCE: "打开数据源",
        UiStringKey.COMMAND_CLEAR_FILTER: "清除筛选",
        UiStringKey.COMMAND_REFINE: "细化",
        UiStringKey.COMMAND_UNAVAILABLE: "不可用",
        UiStringKey.COMMAND_RELOAD_SOURCE: "重新加载数据源",
        UiStringKey.COMMAND_RECOMPUTE: "重新计算",
        UiStringKey.EDIT_CLEAN: "编辑：干净（0 个待处理）",
        UiStringKey.HINT_NO_SOURCE: "未加载数据源",
        UiStringKey.NAVIGATION_HEADER: "结构",
        UiStringKey.ACCESSIBLE_PATH_INPUT: "数据源路径输入框",
        UiStringKey.ACCESSIBLE_NAVIGATION: "文件和结构",
        UiStringKey.ACCESSIBLE_INSPECTOR_OVERVIEW: "检查器概览",
        UiStringKey.ACCESSIBLE_INSPECTOR_ATTRIBUTES: "检查器属性",
        UiStringKey.ACCESSIBLE_INSPECTOR_STATISTICS: "检查器统计",
        UiStringKey.ACCESSIBLE_INSPECTOR_PLUGINS: "检查器插件溯源",
        UiStringKey.ACCESSIBLE_ACTIVE_SPLIT: "当前分屏和视图",
        UiStringKey.ACCESSIBLE_WORKSPACE_TABS: "工作区标签和分屏组",
        UiStringKey.ACCESSIBLE_COMMAND_BAR: "命令栏",
        UiStringKey.ACCESSIBLE_BOTTOM_TABS: "任务、输出和问题",
        UiStringKey.ACCESSIBLE_OUTPUT_LOG: "输出日志",
        UiStringKey.ACCESSIBLE_TASK_ACTIVITY: "任务活动",
        UiStringKey.ACCESSIBLE_PROBLEMS: "问题",
        UiStringKey.ACCESSIBLE_STATUS: "应用状态",
        UiStringKey.INSPECTOR_OVERVIEW_PLACEHOLDER: "选择节点以检查元数据。",
        UiStringKey.INSPECTOR_ATTRIBUTES_PLACEHOLDER: "所选资源的属性会显示在这里。",
        UiStringKey.INSPECTOR_STATISTICS_PLACEHOLDER: "内置插件生成的统计会显示在这里。",
        UiStringKey.INSPECTOR_PLUGINS_PLACEHOLDER: "兼容插件和结果溯源会显示在这里。",
        UiStringKey.WORKSPACE_NOT_READY: "工作区：尚未就绪",
        UiStringKey.ACTIVE_SPLIT_DATA: "分屏：主区 / 视图：数据",
        UiStringKey.STATUS_READY: "就绪",
        UiStringKey.STATUS_SOURCE_EMPTY: "数据源：-",
        UiStringKey.STATUS_PATH_EMPTY: "路径：-",
        UiStringKey.STATUS_SHAPE_EMPTY: "形状：-",
        UiStringKey.STATUS_DTYPE_EMPTY: "dtype：-",
        UiStringKey.STATUS_SLICE_EMPTY: "切片：-",
        UiStringKey.STATUS_MODE_EMPTY: "模式：-",
        UiStringKey.STATUS_TASK_IDLE: "任务：空闲",
        UiStringKey.STATUS_COORDINATES_EMPTY: "坐标：-",
        UiStringKey.WORKSPACE_INITIAL_MESSAGE: "尚未打开数据源。",
        UiStringKey.WORKSPACE_READY_MESSAGE: "打开数据源并选择 ARRAY 节点。",
        UiStringKey.OUTPUT_READY: "就绪",
        UiStringKey.TASKS_NONE: "没有活动任务。",
        UiStringKey.PROBLEMS_NONE: "没有问题报告。",
        UiStringKey.TAB_DATA: "数据",
        UiStringKey.TAB_OVERVIEW: "概览",
        UiStringKey.TAB_ATTRIBUTES: "属性",
        UiStringKey.TAB_STATISTICS: "统计",
        UiStringKey.TAB_PLUGINS: "插件",
        UiStringKey.TAB_TASKS: "任务",
        UiStringKey.TAB_OUTPUT: "输出",
        UiStringKey.TAB_PROBLEMS: "问题",
        UiStringKey.PANEL_NAVIGATION: "导航",
        UiStringKey.PANEL_WORKSPACE: "工作区",
        UiStringKey.PANEL_INSPECTOR: "检查器",
        UiStringKey.DIALOG_SAVE_SUMMARY_TITLE: "保存摘要",
        UiStringKey.DIALOG_SAVE_CONFIRM: "保存已审查更改",
        UiStringKey.DIALOG_DESTRUCTIVE_TITLE: "确认破坏性操作",
        UiStringKey.DIALOG_DESTRUCTIVE_CONFIRM: "确认操作",
        UiStringKey.DIALOG_IMPORT_OPTIONS_TITLE: "导入选项",
        UiStringKey.DIALOG_IMPORT_APPLY: "应用导入选项",
        UiStringKey.STATE_INITIAL_TITLE: "准备开始",
        UiStringKey.STATE_INITIAL_SUMMARY: "选择数据源或资源以继续。",
        UiStringKey.STATE_LOADING_TITLE: "加载中",
        UiStringKey.STATE_LOADING_SUMMARY: "任务正在运行；调用方提供取消能力时可取消。",
        UiStringKey.STATE_EMPTY_TITLE: "没有可显示内容",
        UiStringKey.STATE_EMPTY_SUMMARY: "所选数据源或筛选结果为空时，这是有效状态。",
        UiStringKey.STATE_READY_TITLE: "就绪",
        UiStringKey.STATE_READY_SUMMARY: "内容已按当前范围和溯源可用。",
        UiStringKey.STATE_PARTIAL_TITLE: "部分视图",
        UiStringKey.STATE_PARTIAL_SUMMARY: "当前只显示受限预览、页面、切片或样本。",
        UiStringKey.STATE_ERROR_TITLE: "无法完成操作",
        UiStringKey.STATE_ERROR_SUMMARY: "可查看安全错误摘要；详情仅限当前目标。",
        UiStringKey.STATE_DISABLED_TITLE: "不可用",
        UiStringKey.STATE_DISABLED_SUMMARY: "所需上下文存在后，此操作才可使用。",
        UiStringKey.STATE_DIRTY_TITLE: "有未保存更改",
        UiStringKey.STATE_DIRTY_SUMMARY: "关闭前请审查、保存、放弃或导出更改。",
        UiStringKey.STATE_READ_ONLY_TITLE: "只读",
        UiStringKey.STATE_READ_ONLY_SUMMARY: "此数据源可检查和导出，但 v1 不会覆盖它。",
        UiStringKey.STATE_CONFLICTED_TITLE: "检测到冲突",
        UiStringKey.STATE_CONFLICTED_SUMMARY: "必须重新加载数据源或另存更改后才能保存。",
        UiStringKey.STATE_STALE_TITLE: "结果已过期",
        UiStringKey.STATE_STALE_SUMMARY: "此结果生成后，数据源、参数或选择范围已经变化。",
    },
}


def tr(key: UiStringKey, locale: Locale = Locale.EN_US, **values: object) -> str:
    """Translate a centralized UI string and format optional placeholders."""

    text = _CATALOG[Locale(locale)][UiStringKey(key)]
    return text.format(**values) if values else text


def missing_catalog_entries() -> dict[str, list[str]]:
    """Return missing translation keys by locale for test and CI gates."""

    required = set(UiStringKey)
    missing: dict[str, list[str]] = {}
    for locale in Locale:
        available = set(_CATALOG.get(locale, {}))
        absent = sorted(key.value for key in required - available)
        if absent:
            missing[locale.value] = absent
    return missing


__all__ = ["Locale", "UiStringKey", "missing_catalog_entries", "tr"]
