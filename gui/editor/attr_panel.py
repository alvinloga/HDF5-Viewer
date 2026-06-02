"""AttrPanel — 属性值查看面板（只读）"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
import numpy as np

from .data_table import DataTablePanel


class AttrPanel(QWidget):
    """属性值查看面板

    将 HDF5 属性值转换为 numpy 数组后，
    用 DataTablePanel 以表格形式显示。
    只读，不可编辑。
    """

    def __init__(self, attr_name: str, attr_value, parent=None):
        super().__init__(parent)
        self._attr_name = attr_name
        self._raw_value = attr_value

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 信息栏
        type_str = self._describe_type(attr_value)
        self._info_label = QLabel(f"  {attr_name}  ({type_str})  [Read-only]")
        layout.addWidget(self._info_label)

        # 数据表格
        self.data_table = DataTablePanel(self)
        layout.addWidget(self.data_table)

        # 应用默认主题
        self.apply_theme("dark")

        # 加载数据
        data = self._to_ndarray(attr_value)
        if data is not None:
            self.data_table.load_data(data)

    @staticmethod
    def _describe_type(value) -> str:
        """描述属性值类型"""
        if isinstance(value, np.ndarray):
            return f"ndarray {value.shape} {value.dtype}"
        elif isinstance(value, (list, tuple)):
            return f"{type(value).__name__} len={len(value)}"
        elif isinstance(value, bytes):
            return f"bytes len={len(value)}"
        elif isinstance(value, str):
            return f"str len={len(value)}"
        else:
            return type(value).__name__

    @staticmethod
    def _to_ndarray(value) -> np.ndarray | None:
        """将属性值转换为 numpy 数组用于显示

        类型处理：
        - 标量（int/float/bool） → 1x1 数组
        - str/bytes → 1x1 数组（字符串作为单个值）
        - list/tuple → 转 ndarray
        - ndarray → 直接用
        - 其他 → str() 转换后 1x1
        """
        try:
            if isinstance(value, np.ndarray):
                if value.ndim == 0:
                    # 0-d 数组，提取标量
                    return np.array([[value.item()]])
                return value
            elif isinstance(value, (list, tuple)):
                arr = np.array(value)
                if arr.ndim == 0:
                    return np.array([[arr.item()]])
                if arr.ndim == 1:
                    return arr
                return arr
            elif isinstance(value, str):
                return np.array([[value]])
            elif isinstance(value, bytes):
                try:
                    decoded = value.decode('utf-8')
                    return np.array([[decoded]])
                except Exception:
                    return np.array([[value.hex()]])
            elif isinstance(value, (int, float, bool, np.integer, np.floating)):
                return np.array([[value]])
            else:
                return np.array([[str(value)]])
        except Exception:
            return np.array([[str(value)]])

    def apply_theme(self, theme: str):
        from ..theme import get_theme_colors
        colors = get_theme_colors(theme)
        self._info_label.setStyleSheet(f"""
            QLabel {{
                background-color: {colors['bg_tertiary']};
                color: {colors['text_secondary']};
                font-size: 11px;
                padding: 4px 8px;
                border-bottom: 1px solid {colors['border']};
            }}
        """)
        self.data_table.apply_theme(theme)

    def get_attr_name(self) -> str:
        """获取属性名"""
        return self._attr_name
