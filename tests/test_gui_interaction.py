"""GUI 交互测试 - 测试用户界面功能"""

import sys
import os
import tempfile
import numpy as np
import h5py

# 添加项目根目录到 path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def test_main_window_creation():
    """测试主窗口创建"""
    print("\n=== Testing Main Window Creation ===")

    from PyQt6.QtWidgets import QApplication
    from gui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)

    try:
        config = {'ui': {'sidebarWidth': 280}}
        window = MainWindow(config)
        assert window is not None
        assert window.windowTitle() == "HDF5 Viewer"
        print(f"  [OK] Main window created")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_tab_manager():
    """测试标签页管理器"""
    print("\n=== Testing Tab Manager ===")

    from PyQt6.QtWidgets import QApplication
    from gui.editor.tab_manager import TabManager
    from core.registry import DataSourceRegistry
    from core.h5_source import H5Source

    app = QApplication.instance() or QApplication(sys.argv)

    try:
        # 注册数据源
        DataSourceRegistry.register(H5Source)

        # 创建测试文件
        with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
            temp_path = f.name

        with h5py.File(temp_path, 'w') as f:
            f.create_dataset('data', data=np.random.randn(10, 10))

        # 创建标签页管理器
        tab_manager = TabManager()

        # 测试打开文件
        result = tab_manager.open_file(temp_path)
        assert result == True
        print(f"  [OK] Open file")

        # 测试获取当前面板
        panel = tab_manager.get_current_panel()
        assert panel is not None
        print(f"  [OK] Get current panel")

        # 测试获取所有路径
        paths = tab_manager.get_all_paths()
        assert len(paths) == 1
        assert paths[0] == temp_path
        print(f"  [OK] Get all paths")

        # 测试关闭文件
        tab_manager.close_file(temp_path)
        paths = tab_manager.get_all_paths()
        assert len(paths) == 0
        print(f"  [OK] Close file")

        os.unlink(temp_path)
        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_explorer_panel():
    """测试 Explorer 面板"""
    print("\n=== Testing Explorer Panel ===")

    from PyQt6.QtWidgets import QApplication
    from gui.sidebar.explorer import ExplorerPanel
    from core.datasource import TreeNode, NodeType, DataMeta

    app = QApplication.instance() or QApplication(sys.argv)

    try:
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
        print(f"  [OK] Load tree")

        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_slice_input():
    """测试切片输入控件"""
    print("\n=== Testing Slice Input ===")

    from PyQt6.QtWidgets import QApplication
    from gui.editor.file_panel import SliceInput

    app = QApplication.instance() or QApplication(sys.argv)

    try:
        slice_input = SliceInput()

        # 测试设置形状提示
        slice_input.set_shape_hint((1000, 100))
        assert slice_input.input.placeholderText() != ""
        print(f"  [OK] Set shape hint")

        # 测试快捷切片
        slice_input._apply_quick_slice("first")
        assert slice_input.input.text() == "[0:100, :]"
        print(f"  [OK] Quick slice: first")

        slice_input._apply_quick_slice("last")
        assert "900:1000" in slice_input.input.text()
        print(f"  [OK] Quick slice: last")

        slice_input._apply_quick_slice("all")
        assert slice_input.input.text() == "[:, :]"
        print(f"  [OK] Quick slice: all")

        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_data_table():
    """测试数据表格"""
    print("\n=== Testing Data Table ===")

    from PyQt6.QtWidgets import QApplication
    from gui.editor.data_table import DataTable, DataTablePanel

    app = QApplication.instance() or QApplication(sys.argv)

    try:
        # 测试 DataTable
        table = DataTable()

        # 测试加载数据
        data = np.random.randn(100, 50)
        table.load_data(data)
        assert table._model.rowCount() == 100
        assert table._model.columnCount() == 50
        print(f"  [OK] Load 2D data")

        # 测试加载 1D 数据
        data_1d = np.random.randn(100)
        table.load_data(data_1d)
        assert table._model.rowCount() == 100
        assert table._model.columnCount() == 2  # Index + Value
        print(f"  [OK] Load 1D data")

        # 测试清空
        table.clear_data()
        assert table._model.rowCount() == 0
        print(f"  [OK] Clear data")

        # 测试 DataTablePanel
        panel = DataTablePanel()
        panel.load_data(data)
        assert panel.table._model.rowCount() == 100
        print(f"  [OK] DataTablePanel")

        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_status_bar():
    """测试状态栏"""
    print("\n=== Testing Status Bar ===")

    from PyQt6.QtWidgets import QApplication
    from gui.status_bar import StatusBar
    from core.event_bus import EventBus

    app = QApplication.instance() or QApplication(sys.argv)

    try:
        status_bar = StatusBar()

        # 测试设置消息
        status_bar.set_message("Test message")
        assert status_bar.file_label.text() == "Test message"
        print(f"  [OK] Set message")

        # 测试事件处理
        bus = EventBus()
        bus.emit(EventBus.STATUS_MESSAGE, "Event message")
        assert status_bar.file_label.text() == "Event message"
        print(f"  [OK] Event handling")

        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_bottom_panel():
    """测试底部面板"""
    print("\n=== Testing Bottom Panel ===")

    from PyQt6.QtWidgets import QApplication
    from gui.bottom_panel import BottomPanel, PropertiesView
    from core.datasource import DataMeta, NodeType

    app = QApplication.instance() or QApplication(sys.argv)

    try:
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
        print(f"  [OK] Load metadata")

        # 测试 BottomPanel
        panel = BottomPanel()
        assert panel.tabs.count() == 2  # Properties + Output
        print(f"  [OK] Bottom panel tabs")

        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_activity_bar():
    """测试活动栏"""
    print("\n=== Testing Activity Bar ===")

    from PyQt6.QtWidgets import QApplication
    from gui.activity_bar import ActivityBar

    app = QApplication.instance() or QApplication(sys.argv)

    try:
        activity_bar = ActivityBar()

        # 测试按钮
        assert len(activity_bar._buttons) == 4  # explorer, search, plugins, settings
        print(f"  [OK] Activity bar buttons")

        # 测试设置活动面板
        activity_bar.set_active("explorer")
        assert activity_bar._current_panel == "explorer"
        print(f"  [OK] Set active panel")

        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_search_panel():
    """测试搜索面板"""
    print("\n=== Testing Search Panel ===")

    from PyQt6.QtWidgets import QApplication
    from services.search import SearchPanel

    app = QApplication.instance() or QApplication(sys.argv)

    try:
        search_panel = SearchPanel()

        # 测试加载结果
        results = ["/group1/data1", "/group2/data2", "/data3"]
        search_panel.results.load_results(results)
        assert search_panel.results.topLevelItemCount() == 3
        print(f"  [OK] Load search results")

        return True

    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("HDF5 Viewer - GUI Interaction Tests")
    print("=" * 60)

    tests = [
        test_main_window_creation,
        test_tab_manager,
        test_explorer_panel,
        test_slice_input,
        test_data_table,
        test_status_bar,
        test_bottom_panel,
        test_activity_bar,
        test_search_panel,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
