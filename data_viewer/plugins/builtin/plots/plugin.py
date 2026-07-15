"""Declarative plot plugins for Plugin API v1."""

from __future__ import annotations

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
from data_viewer.plugins.results import PlotMark, PlotSpec


LINE_PLOT_PLUGIN_ID = "org.dataviewer.line_plot"
SCATTER_PLOT_PLUGIN_ID = "org.dataviewer.scatter_plot"
HISTOGRAM_PLOT_PLUGIN_ID = "org.dataviewer.histogram_plot"
BOX_PLOT_PLUGIN_ID = "org.dataviewer.box_plot"
PLOT_PLUGIN_VERSION = "1.0.0"


class LinePlotPlugin:
    """Create a renderer-owned line PlotSpec from finite 1D values."""

    def run(self, context: PluginContext) -> PluginResult:
        descriptor, values = _read_single_input(context, "building line plot")
        sample_size = _parameter_int(context.parameters, "sample_size")
        seed = _parameter_int(context.parameters, "seed")
        series = _numeric_values(values).reshape(-1)
        finite_mask = np.isfinite(series)
        x_values = np.arange(series.size, dtype=np.float64)[finite_mask]
        y_values = series[finite_mask]
        y_values, x_values, sampling, sampled = _sample_points(
            y_values,
            companion=x_values,
            sample_size=sample_size,
            seed=seed,
        )
        assert x_values is not None
        _require_points(y_values)
        warnings = _nonfinite_warnings(int(series.size - int(finite_mask.sum())))
        data_table = _data_table(x_values, y_values, "series 0")
        return _plot_result(
            plugin_id=LINE_PLOT_PLUGIN_ID,
            title="Line Plot",
            descriptor=descriptor,
            parameters=context.parameters,
            plot=PlotSpec(
                title="Line Plot",
                x_label="index",
                y_label="value",
                marks=(PlotMark(kind="line", x=tuple(x_values), y=tuple(y_values), label="series 0"),),
                warnings=warnings,
            ),
            sampled=sampled,
            metadata={
                "plot_family": "line",
                "data_table": data_table,
                "sampling": sampling,
                "point_count": int(y_values.size),
                "omitted_nonfinite_count": int(series.size - int(finite_mask.sum())),
            },
            warnings=warnings,
        )


class ScatterPlotPlugin:
    """Create a renderer-owned scatter PlotSpec from selected numeric columns."""

    def run(self, context: PluginContext) -> PluginResult:
        descriptor, values = _read_single_input(context, "building scatter plot")
        x_column = _parameter_int(context.parameters, "x_column")
        y_column = _parameter_int(context.parameters, "y_column")
        sample_size = _parameter_int(context.parameters, "sample_size")
        seed = _parameter_int(context.parameters, "seed")
        matrix = _numeric_matrix(values)
        if x_column < 0 or x_column >= matrix.shape[1]:
            raise ValueError(f"x_column {x_column} is outside column count {matrix.shape[1]}")
        if y_column < 0 or y_column >= matrix.shape[1]:
            raise ValueError(f"y_column {y_column} is outside column count {matrix.shape[1]}")
        x_source = matrix[:, x_column]
        y_source = matrix[:, y_column]
        finite_mask = np.isfinite(x_source) & np.isfinite(y_source)
        x_values = x_source[finite_mask]
        y_values = y_source[finite_mask]
        y_values, x_values, sampling, sampled = _sample_points(
            y_values,
            companion=x_values,
            sample_size=sample_size,
            seed=seed,
        )
        assert x_values is not None
        _require_points(y_values)
        warnings = _nonfinite_warnings(int(matrix.shape[0] - int(finite_mask.sum())))
        data_table = _data_table(x_values, y_values, f"columns {x_column}/{y_column}")
        return _plot_result(
            plugin_id=SCATTER_PLOT_PLUGIN_ID,
            title="Scatter Plot",
            descriptor=descriptor,
            parameters=context.parameters,
            plot=PlotSpec(
                title="Scatter Plot",
                x_label=f"column {x_column}",
                y_label=f"column {y_column}",
                marks=(
                    PlotMark(
                        kind="scatter",
                        x=tuple(x_values),
                        y=tuple(y_values),
                        label=f"columns {x_column}/{y_column}",
                    ),
                ),
                warnings=warnings,
            ),
            sampled=sampled,
            metadata={
                "plot_family": "scatter",
                "data_table": data_table,
                "sampling": sampling,
                "point_count": int(y_values.size),
                "omitted_nonfinite_count": int(matrix.shape[0] - int(finite_mask.sum())),
            },
            warnings=warnings,
        )


class HistogramPlotPlugin:
    """Create a declarative histogram PlotSpec from finite numeric values."""

    def run(self, context: PluginContext) -> PluginResult:
        descriptor, values = _read_single_input(context, "building histogram plot")
        bins = _parameter_int(context.parameters, "bins")
        sample_size = _parameter_int(context.parameters, "sample_size")
        seed = _parameter_int(context.parameters, "seed")
        if bins <= 0:
            raise ValueError("bins must be positive")
        series = _numeric_values(values).reshape(-1)
        finite_values = series[np.isfinite(series)]
        finite_values, _unused, sampling, sampled = _sample_points(
            finite_values,
            companion=None,
            sample_size=sample_size,
            seed=seed,
        )
        _require_points(finite_values)
        counts, edges = np.histogram(finite_values, bins=bins)
        centers = (edges[:-1] + edges[1:]) / 2.0
        y_values = counts.astype(np.float64)
        warnings = _nonfinite_warnings(int(series.size - int(np.isfinite(series).sum())))
        data_table = _data_table(centers, y_values, "histogram")
        return _plot_result(
            plugin_id=HISTOGRAM_PLOT_PLUGIN_ID,
            title="Histogram",
            descriptor=descriptor,
            parameters=context.parameters,
            plot=PlotSpec(
                title="Histogram",
                x_label="bin center",
                y_label="count",
                marks=(
                    PlotMark(
                        kind="histogram",
                        x=tuple(float(value) for value in centers),
                        y=tuple(float(value) for value in y_values),
                        label="histogram",
                    ),
                ),
                warnings=warnings,
            ),
            sampled=sampled,
            metadata={
                "plot_family": "histogram",
                "data_table": data_table,
                "sampling": sampling,
                "bin_count": int(bins),
                "omitted_nonfinite_count": int(series.size - int(np.isfinite(series).sum())),
            },
            warnings=warnings,
        )


class BoxPlotPlugin:
    """Create a declarative five-number summary PlotSpec."""

    def run(self, context: PluginContext) -> PluginResult:
        descriptor, values = _read_single_input(context, "building box plot")
        sample_size = _parameter_int(context.parameters, "sample_size")
        seed = _parameter_int(context.parameters, "seed")
        series = _numeric_values(values).reshape(-1)
        finite_values = series[np.isfinite(series)]
        finite_values, _unused, sampling, sampled = _sample_points(
            finite_values,
            companion=None,
            sample_size=sample_size,
            seed=seed,
        )
        _require_points(finite_values)
        summary = np.quantile(finite_values, (0.0, 0.25, 0.5, 0.75, 1.0))
        x_values = np.arange(5, dtype=np.float64)
        warnings = _nonfinite_warnings(int(series.size - int(np.isfinite(series).sum())))
        data_table: list[JsonValue] = []
        for index, value, label in zip(
            x_values,
            summary,
            ("minimum", "q1", "median", "q3", "maximum"),
            strict=True,
        ):
            data_table.append({"x": float(index), "y": float(value), "series": label})
        return _plot_result(
            plugin_id=BOX_PLOT_PLUGIN_ID,
            title="Box Plot",
            descriptor=descriptor,
            parameters=context.parameters,
            plot=PlotSpec(
                title="Box Plot",
                x_label="summary statistic",
                y_label="value",
                marks=(
                    PlotMark(
                        kind="box",
                        x=tuple(float(value) for value in x_values),
                        y=tuple(float(value) for value in summary),
                        label="min/q1/median/q3/max",
                    ),
                ),
                warnings=warnings,
            ),
            sampled=sampled,
            metadata={
                "plot_family": "box",
                "data_table": data_table,
                "sampling": sampling,
                "point_count": int(finite_values.size),
                "omitted_nonfinite_count": int(series.size - int(np.isfinite(series).sum())),
            },
            warnings=warnings,
        )


def _read_single_input(context: PluginContext, progress_message: str):
    input_access = context.inputs[0]
    descriptor = input_access.descriptor
    chunks: list[np.ndarray] = []
    for chunk in input_access.iter_chunks(target_bytes=context.memory_budget_bytes):
        if context.is_cancelled():
            break
        chunks.append(np.asarray(chunk.values))
        context.report_progress(None, progress_message)
    if chunks:
        values = np.concatenate(chunks, axis=0)
    else:
        values = np.empty(descriptor.shape or (0,), dtype=np.dtype(descriptor.dtype or "float64"))
    return descriptor, values


def _plot_result(
    *,
    plugin_id: str,
    title: str,
    descriptor,
    parameters,
    plot: PlotSpec,
    sampled: bool,
    metadata: dict[str, JsonValue],
    warnings: tuple[str, ...],
) -> PluginResult:
    return PluginResult(
        kind=ResultKind.PLOT,
        title=title,
        payload=plot,
        provenance=ResultProvenance(
            plugin_id=plugin_id,
            plugin_version=PLOT_PLUGIN_VERSION,
            api_version=PLUGIN_API_VERSION,
            inputs=(descriptor,),
            parameters=parameters,
            computation_scope="full",
            sampled=sampled,
        ),
        metadata=metadata,
        warnings=warnings,
    )


def _numeric_values(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values)
    if np.issubdtype(array.dtype, np.complexfloating):
        return np.abs(array).astype(np.float64, copy=False)
    if np.issubdtype(array.dtype, np.bool_):
        return array.astype(np.float64)
    return array.astype(np.float64, copy=False)


def _numeric_matrix(values: np.ndarray) -> np.ndarray:
    numeric = _numeric_values(values)
    if numeric.ndim != 2:
        raise ValueError("scatter plot requires a 2D input with numeric columns")
    if numeric.shape[1] < 2:
        raise ValueError("scatter plot requires at least two columns")
    return numeric


def _sample_points(
    y_values: np.ndarray,
    *,
    companion: np.ndarray | None,
    sample_size: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray | None, dict[str, JsonValue] | None, bool]:
    if sample_size < 0:
        raise ValueError("sample_size must be non-negative")
    population_size = int(y_values.size)
    if sample_size == 0 or sample_size >= population_size:
        return y_values, companion, None, False
    rng = np.random.default_rng(seed)
    indices = np.sort(rng.choice(population_size, size=sample_size, replace=False))
    sampling: dict[str, JsonValue] = {
        "method": "without_replacement",
        "seed": seed,
        "requested_size": sample_size,
        "actual_size": int(indices.size),
        "population_size": population_size,
    }
    sampled_companion = None if companion is None else companion[indices]
    return y_values[indices], sampled_companion, sampling, True


def _require_points(values: np.ndarray) -> None:
    if values.size == 0:
        raise ValueError("no finite values available for plot")


def _nonfinite_warnings(count: int) -> tuple[str, ...]:
    if count <= 0:
        return ()
    return (f"NONFINITE_DROPPED: {count} nonfinite point(s) were omitted.",)


def _data_table(x_values: np.ndarray, y_values: np.ndarray, series: str) -> list[JsonValue]:
    rows: list[JsonValue] = []
    for x, y in zip(x_values, y_values, strict=True):
        rows.append(
            {
                "x": cast(JsonValue, float(x)),
                "y": cast(JsonValue, float(y)),
                "series": series,
            }
        )
    return rows


def _parameter_int(parameters: object, name: str) -> int:
    value = parameters[name]  # type: ignore[index]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    return value
