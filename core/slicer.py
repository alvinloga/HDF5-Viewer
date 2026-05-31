"""Slicer — 切片解析工具"""

import re
from typing import Any


class SliceParser:
    """解析用户输入的切片字符串为 tuple of slice"""

    @staticmethod
    def parse(slice_str: str, shape: tuple) -> tuple:
        """
        解析切片字符串，如 "[0:100, 10:20]" 或 "0:100, 10:20"
        返回 tuple of slice 对象
        """
        if not slice_str or not shape:
            return tuple()

        # 去除方括号
        s = slice_str.strip()
        if s.startswith('[') and s.endswith(']'):
            s = s[1:-1]

        # 按逗号分割
        parts = [p.strip() for p in s.split(',')]

        slices = []
        for i, part in enumerate(parts):
            if i >= len(shape):
                break

            if ':' not in part:
                # 单个索引
                idx = int(part)
                slices.append(idx)
            else:
                # 切片范围
                slices.append(SliceParser._parse_range(part, shape[i]))

        return tuple(slices)

    @staticmethod
    def _parse_range(range_str: str, dim_size: int) -> slice:
        """解析单个维度的范围，如 '10:100' 或 ':100' 或 '10:'"""
        parts = range_str.split(':')

        if len(parts) == 1:
            # 单个值
            val = int(parts[0]) if parts[0] else None
            return slice(val, val + 1 if val is not None else None)
        elif len(parts) == 2:
            start = int(parts[0]) if parts[0] else None
            stop = int(parts[1]) if parts[1] else None
            return slice(start, stop)
        elif len(parts) == 3:
            start = int(parts[0]) if parts[0] else None
            stop = int(parts[1]) if parts[1] else None
            step = int(parts[2]) if parts[2] else None
            return slice(start, stop, step)
        else:
            raise ValueError(f"Invalid slice format: {range_str}")

    @staticmethod
    def default_slice(shape: tuple, max_rows: int = 200) -> tuple:
        """生成默认切片，限制预览行数（默认 200 行，避免 UI 卡死）"""
        if not shape:
            return tuple()

        slices = []
        for i, dim in enumerate(shape):
            if i == 0 and dim > max_rows:
                slices.append(slice(0, max_rows))
            elif i == 1 and dim > 100:
                # 列数也限制，避免宽表卡死
                slices.append(slice(0, 100))
            else:
                slices.append(slice(0, dim))
        return tuple(slices)

    @staticmethod
    def slice_to_str(slices: tuple) -> str:
        """将切片 tuple 转为可读字符串"""
        parts = []
        for s in slices:
            if isinstance(s, int):
                parts.append(str(s))
            elif isinstance(s, slice):
                start = s.start if s.start is not None else ''
                stop = s.stop if s.stop is not None else ''
                if s.step:
                    parts.append(f"{start}:{stop}:{s.step}")
                else:
                    parts.append(f"{start}:{stop}")
        return f"[{', '.join(parts)}]"

    @staticmethod
    def get_slice_shape(slices: tuple, original_shape: tuple) -> tuple:
        """计算切片后的形状"""
        result = []
        for i, dim in enumerate(original_shape):
            if i < len(slices):
                s = slices[i]
                if isinstance(s, int):
                    continue  # 整数索引会降维
                elif isinstance(s, slice):
                    start = s.start or 0
                    stop = s.stop if s.stop is not None else dim
                    step = s.step or 1
                    result.append((stop - start + step - 1) // step)
            else:
                result.append(dim)
        return tuple(result)
