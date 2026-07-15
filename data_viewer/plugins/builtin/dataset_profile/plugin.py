"""Chunked Dataset Profile reference plugin for Plugin API v1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np

from data_viewer.domain import JsonValue
from data_viewer.plugins.api import (
    PLUGIN_API_VERSION,
    PluginContext,
    PluginResult,
    ResultKind,
    ResultProvenance,
)
from data_viewer.plugins.results import ResultColumn, TableResultPayload


PLUGIN_ID = "org.dataviewer.dataset_profile"
PLUGIN_VERSION = "1.0.0"
DESCRIPTIVE_STATS_PLUGIN_ID = "org.dataviewer.descriptive_statistics"
DESCRIPTIVE_STATS_PLUGIN_VERSION = "1.0.0"
DISTRIBUTION_SUMMARY_PLUGIN_ID = "org.dataviewer.distribution_summary"
DISTRIBUTION_SUMMARY_PLUGIN_VERSION = "1.0.0"


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

    def payload(
        self,
        *,
        shape: tuple[int, ...] | None,
        dtype: str | None,
        estimated_bytes: int | None,
    ) -> dict[str, object]:
        """Build the JSON-safe summary payload."""

        return {
            "shape": list(shape or ()),
            "dtype": dtype or "unknown",
            "element_count": self.element_count,
            "estimated_bytes": estimated_bytes,
            "finite_count": self.finite_count,
            "missing_count": self.missing_count,
            "positive_infinity_count": self.positive_infinity_count,
            "negative_infinity_count": self.negative_infinity_count,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "mean": self.finite_sum / self.finite_count if self.finite_count else None,
            "value_semantics": _value_semantics(dtype),
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
            payload=accumulator.payload(
                shape=descriptor.shape,
                dtype=descriptor.dtype,
                estimated_bytes=descriptor.estimated_bytes,
            ),
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


class DescriptiveStatisticsPlugin:
    """Chunked descriptive statistics for numeric array-like inputs."""

    def run(self, context: PluginContext) -> PluginResult:
        input_access = context.inputs[0]
        descriptor = input_access.descriptor
        axis = _parameter_int(context.parameters, "axis")
        nan_policy = _parameter_str(context.parameters, "nan_policy")
        quantile_low = _parameter_float(context.parameters, "quantile_low")
        quantile_high = _parameter_float(context.parameters, "quantile_high")
        chunks: list[np.ndarray] = []

        for chunk in input_access.iter_chunks(target_bytes=context.memory_budget_bytes):
            if context.is_cancelled():
                break
            chunks.append(np.asarray(chunk.values))
            context.report_progress(None, "computing descriptive statistics")

        values = _concatenate_chunks(chunks, descriptor.shape, descriptor.dtype)
        rows = _descriptive_rows(
            values,
            axis=axis,
            nan_policy=nan_policy,
            quantile_low=quantile_low,
            quantile_high=quantile_high,
        )
        return PluginResult(
            kind=ResultKind.TABLE,
            title="Descriptive Statistics",
            payload=TableResultPayload(
                columns=(
                    ResultColumn("axis", "string"),
                    ResultColumn("metric", "string"),
                    ResultColumn("value", "number"),
                ),
                rows=tuple(rows),
            ),
            provenance=ResultProvenance(
                plugin_id=DESCRIPTIVE_STATS_PLUGIN_ID,
                plugin_version=DESCRIPTIVE_STATS_PLUGIN_VERSION,
                api_version=PLUGIN_API_VERSION,
                inputs=(descriptor,),
                parameters=context.parameters,
                computation_scope="full",
                sampled=False,
            ),
            metadata={
                "value_semantics": _value_semantics(descriptor.dtype),
                "nan_policy": nan_policy,
            },
            warnings=(),
        )


class DistributionSummaryPlugin:
    """Chunked distribution summary with explicit sampling metadata."""

    def run(self, context: PluginContext) -> PluginResult:
        input_access = context.inputs[0]
        descriptor = input_access.descriptor
        bins = _parameter_int(context.parameters, "bins")
        nan_policy = _parameter_str(context.parameters, "nan_policy")
        sample_size = _parameter_int(context.parameters, "sample_size")
        seed = _parameter_int(context.parameters, "seed")
        chunks: list[np.ndarray] = []

        for chunk in input_access.iter_chunks(target_bytes=context.memory_budget_bytes):
            if context.is_cancelled():
                break
            chunks.append(np.asarray(chunk.values))
            context.report_progress(None, "summarizing distribution")

        values = _concatenate_chunks(chunks, descriptor.shape, descriptor.dtype)
        numeric = _numeric_values(values).reshape(-1)
        finite_population = numeric[np.isfinite(numeric)]
        finite_values, sampling_rows, sampled = _sample_finite_values(
            finite_population,
            sample_size=sample_size,
            seed=seed,
        )
        rows = _distribution_rows(
            numeric,
            finite_values=finite_values,
            bins=bins,
            nan_policy=nan_policy,
            sampling_rows=sampling_rows,
        )
        return PluginResult(
            kind=ResultKind.TABLE,
            title="Distribution Summary",
            payload=TableResultPayload(
                columns=(
                    ResultColumn("section", "string"),
                    ResultColumn("label", "string"),
                    ResultColumn("value", "number"),
                ),
                rows=tuple(rows),
            ),
            provenance=ResultProvenance(
                plugin_id=DISTRIBUTION_SUMMARY_PLUGIN_ID,
                plugin_version=DISTRIBUTION_SUMMARY_PLUGIN_VERSION,
                api_version=PLUGIN_API_VERSION,
                inputs=(descriptor,),
                parameters=context.parameters,
                computation_scope="full",
                sampled=sampled,
            ),
            metadata={
                "value_semantics": _value_semantics(descriptor.dtype),
                "nan_policy": nan_policy,
            },
            warnings=(),
        )


def _value_semantics(dtype: str | None) -> str:
    if dtype and np.issubdtype(np.dtype(dtype), np.complexfloating):
        return "complex_magnitude"
    return "numeric"


def _parameter_int(parameters: object, name: str) -> int:
    value = parameters[name]  # type: ignore[index]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    return value


def _parameter_float(parameters: object, name: str) -> float:
    value = parameters[name]  # type: ignore[index]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be a number")
    return float(value)


def _parameter_str(parameters: object, name: str) -> str:
    value = parameters[name]  # type: ignore[index]
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _concatenate_chunks(
    chunks: list[np.ndarray],
    shape: tuple[int, ...] | None,
    dtype: str | None,
) -> np.ndarray:
    if chunks:
        return np.concatenate(chunks, axis=0)
    return np.empty(shape or (0,), dtype=np.dtype(dtype or "float64"))


def _descriptive_rows(
    values: np.ndarray,
    *,
    axis: int,
    nan_policy: str,
    quantile_low: float,
    quantile_high: float,
) -> list[dict[str, JsonValue]]:
    if not 0.0 <= quantile_low <= quantile_high <= 1.0:
        raise ValueError("quantiles must satisfy 0 <= low <= high <= 1")
    numeric = _numeric_values(values)
    if axis == -1:
        return _rows_for_series("all", numeric.reshape(-1), nan_policy, quantile_low, quantile_high)
    if axis < 0 or axis >= numeric.ndim:
        raise ValueError(f"axis {axis} is outside rank {numeric.ndim}")
    moved = np.moveaxis(numeric, axis, 0)
    remaining_shape = moved.shape[1:]
    series_matrix = moved.reshape(moved.shape[0], -1)
    rows: list[dict[str, JsonValue]] = []
    for column_index in range(series_matrix.shape[1]):
        label = _axis_label(column_index, remaining_shape)
        rows.extend(_rows_for_series(label, series_matrix[:, column_index], nan_policy, quantile_low, quantile_high))
    return rows


def _numeric_values(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values)
    if np.issubdtype(array.dtype, np.complexfloating):
        return np.abs(array).astype(np.float64, copy=False)
    if np.issubdtype(array.dtype, np.bool_):
        return array.astype(np.float64)
    return array.astype(np.float64, copy=False)


def _axis_label(index: int, remaining_shape: tuple[int, ...]) -> str:
    if not remaining_shape:
        return "all"
    coordinates = np.unravel_index(index, remaining_shape)
    return ",".join(str(int(coordinate)) for coordinate in coordinates)


def _rows_for_series(
    axis_label: str,
    values: np.ndarray,
    nan_policy: str,
    quantile_low: float,
    quantile_high: float,
) -> list[dict[str, JsonValue]]:
    missing_count = int(np.isnan(values).sum())
    positive_infinity_count = int(np.isposinf(values).sum())
    negative_infinity_count = int(np.isneginf(values).sum())
    finite = values[np.isfinite(values)]
    if nan_policy == "propagate" and missing_count:
        finite = np.array([], dtype=np.float64)
    stats = _series_stats(finite, quantile_low=quantile_low, quantile_high=quantile_high)
    stats.update(
        {
            "count": int(finite.size),
            "missing_count": missing_count,
            "positive_infinity_count": positive_infinity_count,
            "negative_infinity_count": negative_infinity_count,
        }
    )
    ordered = (
        "count",
        "missing_count",
        "positive_infinity_count",
        "negative_infinity_count",
        "mean",
        "std",
        "minimum",
        "q25",
        "median",
        "q75",
        "maximum",
    )
    return [
        {"axis": axis_label, "metric": metric, "value": cast(JsonValue, stats[metric])}
        for metric in ordered
    ]


def _series_stats(
    finite: np.ndarray,
    *,
    quantile_low: float,
    quantile_high: float,
) -> dict[str, JsonValue]:
    if finite.size == 0:
        return {
            "mean": None,
            "std": None,
            "minimum": None,
            "q25": None,
            "median": None,
            "q75": None,
            "maximum": None,
        }
    return {
        "mean": float(np.mean(finite, dtype=np.float64)),
        "std": float(np.std(finite, ddof=1)) if finite.size > 1 else None,
        "minimum": float(np.min(finite)),
        "q25": float(np.quantile(finite, quantile_low)),
        "median": float(np.quantile(finite, 0.5)),
        "q75": float(np.quantile(finite, quantile_high)),
        "maximum": float(np.max(finite)),
    }


def _sample_finite_values(
    finite_values: np.ndarray,
    *,
    sample_size: int,
    seed: int,
) -> tuple[np.ndarray, list[dict[str, JsonValue]], bool]:
    if sample_size < 0:
        raise ValueError("sample_size must be non-negative")
    population_size = int(finite_values.size)
    if sample_size == 0 or sample_size >= population_size:
        return finite_values, [], False
    rng = np.random.default_rng(seed)
    indices = np.sort(rng.choice(population_size, size=sample_size, replace=False))
    rows: list[dict[str, JsonValue]] = [
        {"section": "sampling", "label": "method", "value": "without_replacement"},
        {"section": "sampling", "label": "seed", "value": seed},
        {"section": "sampling", "label": "requested_size", "value": sample_size},
        {"section": "sampling", "label": "actual_size", "value": int(indices.size)},
        {"section": "sampling", "label": "population_size", "value": population_size},
    ]
    return finite_values[indices], rows, True


def _distribution_rows(
    values: np.ndarray,
    *,
    finite_values: np.ndarray,
    bins: int,
    nan_policy: str,
    sampling_rows: list[dict[str, JsonValue]],
) -> list[dict[str, JsonValue]]:
    if bins <= 0:
        raise ValueError("bins must be positive")
    missing_count = int(np.isnan(values).sum())
    if nan_policy == "propagate" and missing_count:
        finite_values = np.array([], dtype=np.float64)
    rows: list[dict[str, JsonValue]] = [
        {"section": "summary", "label": "finite_count", "value": int(finite_values.size)},
        {"section": "summary", "label": "missing_count", "value": missing_count},
        {
            "section": "summary",
            "label": "positive_infinity_count",
            "value": int(np.isposinf(values).sum()),
        },
        {
            "section": "summary",
            "label": "negative_infinity_count",
            "value": int(np.isneginf(values).sum()),
        },
    ]
    rows.extend(_robust_shape_rows(finite_values))
    rows.extend(_histogram_rows(finite_values, bins=bins))
    rows.extend(sampling_rows)
    return rows


def _robust_shape_rows(finite_values: np.ndarray) -> list[dict[str, JsonValue]]:
    if finite_values.size == 0:
        iqr: JsonValue = None
        mad: JsonValue = None
        skewness: JsonValue = None
        excess_kurtosis: JsonValue = None
    else:
        q25 = float(np.quantile(finite_values, 0.25))
        median = float(np.quantile(finite_values, 0.5))
        q75 = float(np.quantile(finite_values, 0.75))
        iqr = q75 - q25
        mad = float(np.median(np.abs(finite_values - median)))
        centered = finite_values - float(np.mean(finite_values))
        std = float(np.std(finite_values))
        if finite_values.size >= 3 and std > 0.0:
            skewness = float(np.mean((centered / std) ** 3))
        else:
            skewness = None
        if finite_values.size >= 4 and std > 0.0:
            excess_kurtosis = float(np.mean((centered / std) ** 4) - 3.0)
        else:
            excess_kurtosis = None
    return [
        {"section": "summary", "label": "iqr", "value": iqr},
        {"section": "summary", "label": "mad", "value": mad},
        {"section": "summary", "label": "skewness", "value": _rounded_or_none(skewness)},
        {"section": "summary", "label": "excess_kurtosis", "value": _rounded_or_none(excess_kurtosis)},
    ]


def _histogram_rows(finite_values: np.ndarray, *, bins: int) -> list[dict[str, JsonValue]]:
    if finite_values.size == 0:
        return [{"section": "histogram", "label": "empty", "value": 0}]
    counts, edges = np.histogram(finite_values, bins=bins)
    rows: list[dict[str, JsonValue]] = []
    for index, count in enumerate(counts):
        left = _format_edge(float(edges[index]))
        right = _format_edge(float(edges[index + 1]))
        close = "]" if index == len(counts) - 1 else ")"
        rows.append(
            {
                "section": "histogram",
                "label": f"[{left}, {right}{close}",
                "value": int(count),
            }
        )
    return rows


def _format_edge(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.6g}"


def _rounded_or_none(value: JsonValue) -> JsonValue:
    if isinstance(value, float):
        return round(value, 12)
    return value
