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
CORRELATION_COVARIANCE_PLUGIN_ID = "org.dataviewer.correlation_covariance"
CORRELATION_COVARIANCE_PLUGIN_VERSION = "1.0.0"
DATASET_COMPARE_PLUGIN_ID = "org.dataviewer.dataset_compare"
DATASET_COMPARE_PLUGIN_VERSION = "1.0.0"


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


class CorrelationCovariancePlugin:
    """Correlation and covariance matrix plugin with explicit alignment policy."""

    def run(self, context: PluginContext) -> PluginResult:
        input_access = context.inputs[0]
        descriptor = input_access.descriptor
        variables_axis = _parameter_int(context.parameters, "variables_axis")
        variable_start = _parameter_int(context.parameters, "variable_start")
        variable_count = _parameter_int(context.parameters, "variable_count")
        missing_policy = _parameter_str(context.parameters, "missing_policy")
        max_variables = _parameter_int(context.parameters, "max_variables")
        chunks: list[np.ndarray] = []

        for chunk in input_access.iter_chunks(target_bytes=context.memory_budget_bytes):
            if context.is_cancelled():
                break
            chunks.append(np.asarray(chunk.values))
            context.report_progress(None, "computing correlation and covariance")

        values = _concatenate_chunks(chunks, descriptor.shape, descriptor.dtype)
        matrix, labels = _variable_observation_matrix(
            values,
            variables_axis=variables_axis,
            variable_start=variable_start,
            variable_count=variable_count,
            max_variables=max_variables,
        )
        rows, warnings = _correlation_covariance_rows(
            matrix,
            labels=labels,
            missing_policy=missing_policy,
        )
        return PluginResult(
            kind=ResultKind.TABLE,
            title="Correlation/Covariance",
            payload=TableResultPayload(
                columns=(
                    ResultColumn("metric", "string"),
                    ResultColumn("row_variable", "string"),
                    ResultColumn("column_variable", "string"),
                    ResultColumn("value", "number"),
                    ResultColumn("aligned_count", "integer"),
                ),
                rows=tuple(rows),
            ),
            provenance=ResultProvenance(
                plugin_id=CORRELATION_COVARIANCE_PLUGIN_ID,
                plugin_version=CORRELATION_COVARIANCE_PLUGIN_VERSION,
                api_version=PLUGIN_API_VERSION,
                inputs=(descriptor,),
                parameters=context.parameters,
                computation_scope="full",
                sampled=False,
            ),
            metadata={
                "value_semantics": _value_semantics(descriptor.dtype),
                "variables_axis": variables_axis,
                "variable_start": variable_start,
                "variable_count": len(labels),
                "missing_policy": missing_policy,
            },
            warnings=tuple(warnings),
        )


class DatasetComparePlugin:
    """Exact-shape numeric dataset comparison with explicit error rules."""

    def run(self, context: PluginContext) -> PluginResult:
        if len(context.inputs) != 2:
            raise ValueError("dataset compare requires exactly two inputs")
        missing_policy = _parameter_str(context.parameters, "missing_policy")
        relative_error_mode = _parameter_str(context.parameters, "relative_error_mode")
        left_access, right_access = context.inputs
        left_descriptor = left_access.descriptor
        right_descriptor = right_access.descriptor

        if left_descriptor.shape != right_descriptor.shape:
            raise ValueError(f"shape mismatch: {left_descriptor.shape} != {right_descriptor.shape}")

        left_values = _concatenate_chunks(
            [np.asarray(chunk.values) for chunk in left_access.iter_chunks(target_bytes=context.memory_budget_bytes)],
            left_descriptor.shape,
            left_descriptor.dtype,
        )
        context.report_progress(None, "read left dataset")
        right_values = _concatenate_chunks(
            [np.asarray(chunk.values) for chunk in right_access.iter_chunks(target_bytes=context.memory_budget_bytes)],
            right_descriptor.shape,
            right_descriptor.dtype,
        )
        context.report_progress(None, "read right dataset")

        rows = _dataset_compare_rows(
            left_values,
            right_values,
            left_dtype=left_descriptor.dtype,
            right_dtype=right_descriptor.dtype,
            missing_policy=missing_policy,
            relative_error_mode=relative_error_mode,
        )
        return PluginResult(
            kind=ResultKind.TABLE,
            title="Dataset Compare",
            payload=TableResultPayload(
                columns=(
                    ResultColumn("section", "string"),
                    ResultColumn("metric", "string"),
                    ResultColumn("value", "number"),
                ),
                rows=tuple(rows),
            ),
            provenance=ResultProvenance(
                plugin_id=DATASET_COMPARE_PLUGIN_ID,
                plugin_version=DATASET_COMPARE_PLUGIN_VERSION,
                api_version=PLUGIN_API_VERSION,
                inputs=(left_descriptor, right_descriptor),
                parameters=context.parameters,
                computation_scope="full",
                sampled=False,
            ),
            metadata={
                "alignment_policy": "exact_shape",
                "missing_policy": missing_policy,
                "relative_error_mode": relative_error_mode,
                "left_shape": list(left_descriptor.shape or ()),
                "right_shape": list(right_descriptor.shape or ()),
                "left_dtype": left_descriptor.dtype,
                "right_dtype": right_descriptor.dtype,
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


def _variable_observation_matrix(
    values: np.ndarray,
    *,
    variables_axis: int,
    variable_start: int,
    variable_count: int,
    max_variables: int,
) -> tuple[np.ndarray, tuple[str, ...]]:
    numeric = _numeric_values(values)
    if numeric.ndim < 2:
        raise ValueError("correlation/covariance requires at least two dimensions")
    if variables_axis < 0 or variables_axis >= numeric.ndim:
        raise ValueError(f"variables_axis {variables_axis} is outside rank {numeric.ndim}")
    if variable_start < 0:
        raise ValueError("variable_start must be non-negative")
    if variable_count < 0:
        raise ValueError("variable_count must be non-negative")
    if max_variables <= 0:
        raise ValueError("max_variables must be positive")

    moved = np.moveaxis(numeric, variables_axis, 0)
    total_variables = moved.shape[0]
    if variable_start >= total_variables:
        raise ValueError(
            f"variable_start {variable_start} is outside variable count {total_variables}"
        )
    stop = total_variables if variable_count == 0 else min(total_variables, variable_start + variable_count)
    selected = moved[variable_start:stop]
    selected_count = int(selected.shape[0])
    if selected_count == 0:
        raise ValueError("at least one variable must be selected")
    if selected_count > max_variables:
        raise ValueError(
            f"selected variable count {selected_count} exceeds max_variables {max_variables}"
        )

    observations = selected.reshape(selected_count, -1)
    labels = tuple(str(index) for index in range(variable_start, stop))
    return observations, labels


def _correlation_covariance_rows(
    matrix: np.ndarray,
    *,
    labels: tuple[str, ...],
    missing_policy: str,
) -> tuple[list[dict[str, JsonValue]], list[str]]:
    if missing_policy not in {"listwise", "pairwise"}:
        raise ValueError("missing_policy must be listwise or pairwise")

    working = np.asarray(matrix, dtype=np.float64)
    listwise_mask = np.all(np.isfinite(working), axis=0) if missing_policy == "listwise" else None
    rows: list[dict[str, JsonValue]] = []
    warnings: list[str] = []
    constant_warning_labels: set[str] = set()

    for row_index, row_label in enumerate(labels):
        for column_index, column_label in enumerate(labels):
            row_values = working[row_index]
            column_values = working[column_index]
            if listwise_mask is None:
                mask = np.isfinite(row_values) & np.isfinite(column_values)
            else:
                mask = listwise_mask
            left = row_values[mask]
            right = column_values[mask]
            aligned_count = int(left.size)
            covariance = _sample_covariance_or_none(left, right)
            correlation = _sample_correlation_or_none(left, right)
            if aligned_count >= 2 and (_is_constant(left) or _is_constant(right)):
                if _is_constant(left):
                    constant_warning_labels.add(row_label)
                if _is_constant(right):
                    constant_warning_labels.add(column_label)
            rows.append(
                {
                    "metric": "correlation",
                    "row_variable": row_label,
                    "column_variable": column_label,
                    "value": _rounded_or_none(correlation),
                    "aligned_count": aligned_count,
                }
            )
            rows.append(
                {
                    "metric": "covariance",
                    "row_variable": row_label,
                    "column_variable": column_label,
                    "value": _rounded_or_none(covariance),
                    "aligned_count": aligned_count,
                }
            )

    for label in sorted(constant_warning_labels, key=lambda item: int(item) if item.isdecimal() else item):
        warnings.append(f"CONSTANT_VARIABLE: variable {label} has zero variance; correlation is undefined.")
    return rows, warnings


def _sample_covariance_or_none(left: np.ndarray, right: np.ndarray) -> JsonValue:
    if left.size < 2:
        return None
    left_centered = left - float(np.mean(left))
    right_centered = right - float(np.mean(right))
    return float(np.dot(left_centered, right_centered) / (left.size - 1))


def _sample_correlation_or_none(left: np.ndarray, right: np.ndarray) -> JsonValue:
    if left.size < 2:
        return None
    left_std = float(np.std(left, ddof=1))
    right_std = float(np.std(right, ddof=1))
    if left_std == 0.0 or right_std == 0.0:
        return None
    covariance = _sample_covariance_or_none(left, right)
    if not isinstance(covariance, float):
        return None
    return float(covariance / (left_std * right_std))


def _is_constant(values: np.ndarray) -> bool:
    return values.size >= 2 and float(np.std(values, ddof=1)) == 0.0


def _dataset_compare_rows(
    left_values: np.ndarray,
    right_values: np.ndarray,
    *,
    left_dtype: str | None,
    right_dtype: str | None,
    missing_policy: str,
    relative_error_mode: str,
) -> list[dict[str, JsonValue]]:
    if missing_policy != "pairwise":
        raise ValueError("dataset compare v1 supports only pairwise missing policy")
    if relative_error_mode != "left":
        raise ValueError("dataset compare v1 supports only left relative error mode")
    if left_values.shape != right_values.shape:
        raise ValueError(f"shape mismatch: {left_values.shape} != {right_values.shape}")

    left = _numeric_values(left_values).reshape(-1)
    right = _numeric_values(right_values).reshape(-1)
    equal_mask = left == right
    finite_mask = np.isfinite(left) & np.isfinite(right)
    nonfinite_pair_count = int(left.size - int(finite_mask.sum()))
    absolute_errors = np.abs(left[finite_mask] - right[finite_mask])
    relative_errors, relative_undefined_count = _relative_errors_left(
        left[finite_mask],
        absolute_errors,
    )
    rows: list[dict[str, JsonValue]] = [
        {"section": "compatibility", "metric": "shape_match", "value": left_values.shape == right_values.shape},
        {"section": "compatibility", "metric": "dtype_match", "value": left_dtype == right_dtype},
        {"section": "compatibility", "metric": "left_dtype", "value": left_dtype or "unknown"},
        {"section": "compatibility", "metric": "right_dtype", "value": right_dtype or "unknown"},
        {"section": "compatibility", "metric": "alignment_policy", "value": "exact_shape"},
        {"section": "counts", "metric": "element_count", "value": int(left.size)},
        {"section": "counts", "metric": "equal_count", "value": int(equal_mask.sum())},
        {"section": "counts", "metric": "different_count", "value": int(left.size - int(equal_mask.sum()))},
        {"section": "counts", "metric": "finite_pair_count", "value": int(finite_mask.sum())},
        {"section": "counts", "metric": "nonfinite_pair_count", "value": nonfinite_pair_count},
        {"section": "errors", "metric": "max_absolute_error", "value": _max_or_none(absolute_errors)},
        {"section": "errors", "metric": "mean_absolute_error", "value": _mean_or_none(absolute_errors)},
        {"section": "errors", "metric": "max_relative_error", "value": _max_or_none(relative_errors)},
        {"section": "errors", "metric": "mean_relative_error", "value": _mean_or_none(relative_errors)},
        {
            "section": "errors",
            "metric": "relative_error_undefined_count",
            "value": relative_undefined_count,
        },
    ]
    return rows


def _relative_errors_left(
    left: np.ndarray,
    absolute_errors: np.ndarray,
) -> tuple[np.ndarray, int]:
    if left.size == 0:
        return np.array([], dtype=np.float64), 0
    denominator = np.abs(left)
    zero_denominator = denominator == 0.0
    undefined = zero_denominator & (absolute_errors != 0.0)
    valid = ~undefined
    relative = np.zeros(int(valid.sum()), dtype=np.float64)
    if relative.size:
        relative = np.divide(
            absolute_errors[valid],
            denominator[valid],
            out=np.zeros_like(absolute_errors[valid], dtype=np.float64),
            where=denominator[valid] != 0.0,
        )
    return relative, int(undefined.sum())


def _max_or_none(values: np.ndarray) -> JsonValue:
    if values.size == 0:
        return None
    return _rounded_or_none(float(np.max(values)))


def _mean_or_none(values: np.ndarray) -> JsonValue:
    if values.size == 0:
        return None
    return _rounded_or_none(float(np.mean(values)))
