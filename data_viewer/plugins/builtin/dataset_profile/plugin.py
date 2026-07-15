"""Chunked Dataset Profile reference plugin for Plugin API v1."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from data_viewer.plugins.api import (
    PLUGIN_API_VERSION,
    PluginContext,
    PluginResult,
    ResultKind,
    ResultProvenance,
)


PLUGIN_ID = "org.dataviewer.dataset_profile"
PLUGIN_VERSION = "1.0.0"


@dataclass(slots=True)
class _ProfileAccumulator:
    element_count: int = 0
    finite_count: int = 0
    missing_count: int = 0
    positive_infinity_count: int = 0
    negative_infinity_count: int = 0
    finite_sum: float = 0.0
    minimum: float | None = None
    maximum: float | None = None

    def add(self, values: np.ndarray) -> None:
        """Accumulate one numeric chunk without retaining it."""

        array = np.asarray(values)
        self.element_count += int(array.size)
        if array.size == 0:
            return

        if np.issubdtype(array.dtype, np.complexfloating):
            finite_mask = np.isfinite(array)
            finite_values = np.abs(array[finite_mask])
            self.missing_count += int(np.isnan(array).sum())
            self.positive_infinity_count += int(np.isposinf(array.real).sum())
            self.negative_infinity_count += int(np.isneginf(array.real).sum())
        elif np.issubdtype(array.dtype, np.floating):
            finite_mask = np.isfinite(array)
            finite_values = array[finite_mask]
            self.missing_count += int(np.isnan(array).sum())
            self.positive_infinity_count += int(np.isposinf(array).sum())
            self.negative_infinity_count += int(np.isneginf(array).sum())
        else:
            finite_values = array.reshape(-1)

        if finite_values.size == 0:
            return

        finite_values = np.asarray(finite_values, dtype=np.float64)
        self.finite_count += int(finite_values.size)
        self.finite_sum += float(finite_values.sum(dtype=np.float64))
        part_min = float(finite_values.min())
        part_max = float(finite_values.max())
        self.minimum = part_min if self.minimum is None else min(self.minimum, part_min)
        self.maximum = part_max if self.maximum is None else max(self.maximum, part_max)

    def payload(self, *, shape: tuple[int, ...] | None, dtype: str | None) -> dict[str, object]:
        """Build the JSON-safe summary payload."""

        return {
            "shape": list(shape or ()),
            "dtype": dtype or "unknown",
            "element_count": self.element_count,
            "finite_count": self.finite_count,
            "missing_count": self.missing_count,
            "positive_infinity_count": self.positive_infinity_count,
            "negative_infinity_count": self.negative_infinity_count,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "mean": self.finite_sum / self.finite_count if self.finite_count else None,
            "computation_scope": "full",
            "sampled": False,
        }


class DatasetProfilePlugin:
    """Reference built-in plugin proving chunked Plugin API v1 behavior."""

    def run(self, context: PluginContext) -> PluginResult:
        input_access = context.inputs[0]
        descriptor = input_access.descriptor
        accumulator = _ProfileAccumulator()
        chunks_seen = 0

        for chunk in input_access.iter_chunks(target_bytes=context.memory_budget_bytes):
            if context.is_cancelled():
                break
            chunks_seen += 1
            accumulator.add(chunk.values)
            context.report_progress(None, "profiling chunks")

        if context.is_cancelled():
            # The runner owns the final cancellation state and will prevent
            # this provisional result from being published.
            context.report_progress(None, "cancelling")

        return PluginResult(
            kind=ResultKind.SUMMARY,
            title="Dataset Profile",
            payload=accumulator.payload(shape=descriptor.shape, dtype=descriptor.dtype),
            provenance=ResultProvenance(
                plugin_id=PLUGIN_ID,
                plugin_version=PLUGIN_VERSION,
                api_version=PLUGIN_API_VERSION,
                inputs=(descriptor,),
                parameters=context.parameters,
                computation_scope="full",
                sampled=False,
            ),
            metadata={"chunks": chunks_seen},
            warnings=(),
        )
