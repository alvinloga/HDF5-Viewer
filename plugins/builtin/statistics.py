"""Statistics Plugin — 基础统计分析"""

import numpy as np
from core.datasource import DataMeta
from plugins.base import AnalyzePlugin


class StatisticsPlugin(AnalyzePlugin):
    """基础统计分析插件"""

    @property
    def name(self) -> str:
        return "Basic Statistics"

    @property
    def accepts(self) -> list[str]:
        return ['numeric', '1d', '2d']

    def run(self, data: np.ndarray, meta: DataMeta) -> dict:
        """执行统计分析"""
        try:
            # 转换为浮点数
            float_data = data.astype(float)

            # 处理 NaN
            valid_data = float_data[~np.isnan(float_data)]

            if len(valid_data) == 0:
                return {
                    'name': self.name,
                    'result': None,
                    'summary': 'No valid data'
                }

            result = {
                'count': len(valid_data),
                'nan_count': int(np.isnan(float_data).sum()),
                'mean': float(np.mean(valid_data)),
                'std': float(np.std(valid_data)),
                'min': float(np.min(valid_data)),
                'max': float(np.max(valid_data)),
                'median': float(np.median(valid_data)),
                'q25': float(np.percentile(valid_data, 25)),
                'q75': float(np.percentile(valid_data, 75)),
            }

            # 格式化摘要
            summary = (
                f"Count: {result['count']:,} | "
                f"Mean: {result['mean']:.6g} | "
                f"Std: {result['std']:.6g} | "
                f"Min: {result['min']:.6g} | "
                f"Max: {result['max']:.6g}"
            )

            return {
                'name': self.name,
                'result': result,
                'summary': summary
            }

        except Exception as e:
            return {
                'name': self.name,
                'result': None,
                'summary': f'Error: {e}'
            }
