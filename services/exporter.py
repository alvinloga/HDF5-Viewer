"""Exporter — 数据导出服务"""

import numpy as np
import csv
from pathlib import Path
from typing import TextIO


class DataExporter:
    """数据导出器"""

    @staticmethod
    def to_csv(data: np.ndarray, file_path: str, delimiter: str = ',') -> bool:
        """导出为 CSV"""
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=delimiter)

                if data.ndim == 1:
                    # 1D: 单列
                    writer.writerow(["Index", "Value"])
                    for i, val in enumerate(data):
                        writer.writerow([i, DataExporter._format_value(val)])

                elif data.ndim == 2:
                    # 2D: 标准表格
                    headers = [f"Col_{i}" for i in range(data.shape[1])]
                    writer.writerow(headers)
                    for row in data:
                        writer.writerow([DataExporter._format_value(v) for v in row])

                else:
                    # 高维: 展平
                    writer.writerow(["Index", "Value"])
                    flat = data.flatten()
                    for i, val in enumerate(flat):
                        writer.writerow([i, DataExporter._format_value(val)])

            return True

        except Exception as e:
            print(f"Export error: {e}")
            return False

    @staticmethod
    def to_npy(data: np.ndarray, file_path: str) -> bool:
        """导出为 NumPy 格式"""
        try:
            np.save(file_path, data)
            return True
        except Exception as e:
            print(f"Export error: {e}")
            return False

    @staticmethod
    def _format_value(val) -> str:
        """格式化数值"""
        if isinstance(val, (np.floating, float)):
            if np.isnan(val):
                return "NaN"
            elif np.isinf(val):
                return "Inf" if val > 0 else "-Inf"
            else:
                return f"{val:.10g}"
        elif isinstance(val, (np.integer, int)):
            return str(val)
        elif isinstance(val, bytes):
            try:
                return val.decode('utf-8')
            except:
                return str(val)
        else:
            return str(val)
