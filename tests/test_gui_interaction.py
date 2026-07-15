"""GUI 交互测试 - 测试用户界面功能"""

import sys
import os
import numpy as np
import h5py
import pytest

# 添加项目根目录到 path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_h5(tmp_path):
    """创建临时 HDF5 文件路径，测试结束后自动清理"""
    return str(tmp_path / "test.h5")


@pytest.fixture
def qapp():
    """确保 QApplication 实例存在"""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    return app


# ── 测试 ──────────────────────────────────────────────────────────────────

def test_main_window_creation(qapp):
    """测试主窗口创建"""
    from gui.main_window import MainWindow

    config = {'ui': {'sidebarWidth': 280}}
    window = MainWindow(config)
    assert window is not None
    assert window.windowTitle() == "HDF5 Viewer"  # legacy window title


def test_tab_manager(qapp, tmp_h5):
    """测试标签页管理器"""
    from gui.editor.tab_manager import TabManager
    from core.registry import DataSourceRegistry
    from core.h5_source import H5Source

    # 注册数据源
    DataSourceRegistry.register(H5Source)

    # 创建测试文件
    with h5py.File(tmp_h5, 'w') as f:
        f.create_dataset('data', data=np.random.randn(10, 10))

    # 创建标签页管理器
    tab_manager = TabManager()

    # 测试打开文件
    result = tab_manager.open_file(tmp_h5)
    assert result

    # 测试获取当前面板
    panel = tab_manager.get_current_panel()
    assert panel is not None

    # 测试获取所有路径
    paths = tab_manager.get_all_paths()
    assert len(paths) == 1
    assert paths[0] == tmp_h5

    # 测试关闭文件
    tab_manager.close_file(tmp_h5)
    paths = tab_manager.get_all_paths()
    assert len(paths) == 0


def test_explorer_panel(qapp):
    """测试 Explorer 面板"""
    from gui.sidebar.explorer import ExplorerPanel
    from core.datasource import TreeNode, NodeType, DataMeta

    explorer = ExplorerPanel()

    # 创建测试树
    tree = TreeNode(
        name="test.h5",
        path="/",
        node_type=NodeType.GROUP,
        children=[
            TreeNode(
                name="group1",
                path="/group1",
                node_type=NodeType.GROUP,
                children=[
                    TreeNode(
                        name="data1",
                        path="/group1/data1",
                        node_type=NodeType.DATASET,
                        meta=DataMeta(
                            path="/group1/data1",
                            name="data1",
                            shape=(10, 10),
                            dtype="float64"
                        )
                    )
                ]
            ),
            TreeNode(
                name="data2",
                path="/data2",
                node_type=NodeType.DATASET,
                meta=DataMeta(
                    path="/data2",
                    name="data2",
                    shape=(100,),
                    dtype="float64"
                )
            )
        ]
    )

    # 加载树
    explorer.load_tree(tree, "test.h5")
    assert explorer.tree.topLevelItemCount() > 0


def test_slice_input(qapp):
    """测试切片输入控件"""
    from gui.editor.file_panel import SliceInput

    slice_input = SliceInput()

    # 测试设置形状提示
    slice_input.set_shape_hint((1000, 100))
    assert slice_input.input.placeholderText() != ""

    # 测试快捷切片
    slice_input._apply_quick_slice("first")
    assert slice_input.input.text() == "[0:100, :]"

    slice_input._apply_quick_slice("last")
    assert "900:1000" in slice_input.input.text()

    slice_input._apply_quick_slice("all")
    assert slice_input.input.text() == "[:, :]"


def test_data_table(qapp):
    """测试数据表格"""
    from gui.editor.data_table import DataTable, DataTablePanel

    # 测试 DataTable
    table = DataTable()

    # 测试加载数据
    data = np.random.randn(100, 50)
    table.load_data(data)
    assert table._model.rowCount() == 100
    assert table._model.columnCount() == 50

    # 测试加载 1D 数据
    data_1d = np.random.randn(100)
    table.load_data(data_1d)
    assert table._model.rowCount() == 100
    assert table._model.columnCount() == 2  # Index + Value

    # 测试清空
    table.clear_data()
    assert table._model.rowCount() == 0

    # 测试 DataTablePanel
    panel = DataTablePanel()
    panel.load_data(data)
    assert panel.table._model.rowCount() == 100


def test_status_bar(qapp):
    """测试状态栏"""
    from gui.status_bar import StatusBar
    from core.event_bus import EventBus

    status_bar = StatusBar()

    # 测试设置消息
    status_bar.set_message("Test message")
    assert status_bar.file_label.text() == "Test message"

    # 测试事件处理
    bus = EventBus()
    bus.emit(EventBus.STATUS_MESSAGE, "Event message")
    assert status_bar.file_label.text() == "Event message"


def test_bottom_panel(qapp):
    """测试底部面板"""
    from gui.bottom_panel import BottomPanel, PropertiesView
    from core.datasource import DataMeta

    # 测试 PropertiesView
    props = PropertiesView()

    meta = DataMeta(
        path="/test/data",
        name="data",
        shape=(100, 100),
        dtype="float64",
        ndim=2,
        size=10000,
        chunks=(10, 10),
        compression="gzip",
        attrs={"units": "meters", "description": "test data"}
    )

    props.load_metadata(meta)
    assert props.topLevelItemCount() > 0

    # 测试 BottomPanel
    panel = BottomPanel()
    assert panel.tabs.count() >= 2  # Properties + Output (+ 可能更多)


def test_activity_bar(qapp):
    """测试活动栏"""
    from gui.activity_bar import ActivityBar

    activity_bar = ActivityBar()

    # 测试按钮
    assert len(activity_bar._buttons) >= 2  # 至少 explorer + settings

    # 测试设置活动面板
    activity_bar.set_active("explorer")
    assert activity_bar._current_panel == "explorer"


def test_search_panel(qapp):
    """测试搜索面板"""
    from services.search import SearchPanel

    search_panel = SearchPanel()

    # 测试加载结果
    results = ["/group1/data1", "/group2/data2", "/data3"]
    search_panel.results.load_results(results)
    assert search_panel.results.topLevelItemCount() == 3
