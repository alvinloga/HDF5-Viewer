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
CORRELATION_HEATMAP_PLUGIN_ID = "org.dataviewer.correlation_heatmap"
MISSING_DATA_MAP_PLUGIN_ID = "org.dataviewer.missing_data_map"
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
        sampled_y_values, sampled_x_values, sampling, sampled = _sample_points(
            y_values,
            companion=x_values,
            sample_size=sample_size,
            seed=seed,
        )
        assert sampled_x_values is not None
        _require_points(sampled_y_values)
        warnings = _nonfinite_warnings(int(series.size - int(finite_mask.sum())))
        data_table = _data_table(sampled_x_values, sampled_y_values, "series 0")
        return _plot_result(
            plugin_id=LINE_PLOT_PLUGIN_ID,
            title="Line Plot",
            descriptor=descriptor,
            parameters=context.parameters,
            plot=PlotSpec(
                title="Line Plot",
                x_label="index",
                y_label="value",
                marks=(
                    PlotMark(
                        kind="line",
                        x=tuple(sampled_x_values),
                        y=tuple(sampled_y_values),
                        label="series 0",
                    ),
                ),
                warnings=warnings,
            ),
            sampled=sampled,
            metadata={
                "plot_family": "line",
                "data_table": data_table,
                "sampling": sampling,
                "point_count": int(sampled_y_values.size),
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
        sampled_y_values, sampled_x_values, sampling, sampled = _sample_points(
            y_values,
            companion=x_values,
            sample_size=sample_size,
            seed=seed,
        )
        assert sampled_x_values is not None
        _require_points(sampled_y_values)
        warnings = _nonfinite_warnings(int(matrix.shape[0] - int(finite_mask.sum())))
        data_table = _data_table(sampled_x_values, sampled_y_values, f"columns {x_column}/{y_column}")
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
                        x=tuple(sampled_x_values),
                        y=tuple(sampled_y_values),
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
                "point_count": int(sampled_y_values.size),
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


class CorrelationHeatmapPlugin:
    """Create a labeled correlation heatmap PlotSpec from numeric variables."""

    def run(self, context: PluginContext) -> PluginResult:
        descriptor, values = _read_single_input(context, "building correlation heatmap")
        variables_axis = _parameter_int(context.parameters, "variables_axis")
        variable_start = _parameter_int(context.parameters, "variable_start")
        variable_count = _parameter_int(context.parameters, "variable_count")
        missing_policy = _parameter_str(context.parameters, "missing_policy")
        max_variables = _parameter_int(context.parameters, "max_variables")
        matrix, labels = _variable_observation_matrix(
            values,
            variables_axis=variables_axis,
            variable_start=variable_start,
            variable_count=variable_count,
            max_variables=max_variables,
        )
        cells, warnings = _correlation_heatmap_cells(
            matrix,
            labels=labels,
            missing_policy=missing_policy,
        )
        finite_cells = [cell for cell in cells if isinstance(cell["correlation"], float)]
        if not finite_cells:
            raise ValueError("no finite correlations available for heatmap")
        x_values = tuple(float(cast(int, cell["column_index"])) for cell in finite_cells)
        y_values = tuple(float(cast(int, cell["row_index"])) for cell in finite_cells)
        heat_values = tuple(float(cast(float, cell["correlation"])) for cell in finite_cells)
        return _plot_result(
            plugin_id=CORRELATION_HEATMAP_PLUGIN_ID,
            title="Correlation Heatmap",
            descriptor=descriptor,
            parameters=context.parameters,
            plot=PlotSpec(
                title="Correlation Heatmap",
                x_label="column variable",
                y_label="row variable",
                marks=(
                    PlotMark(
                        kind="heatmap",
                        x=x_values,
                        y=y_values,
                        values=heat_values,
                        label="correlation",
                    ),
                ),
                warnings=warnings,
            ),
            sampled=False,
            metadata={
                "plot_family": "correlation_heatmap",
                "labels": list(labels),
                "value_range": [-1.0, 1.0],
                "legend": {"minimum": -1.0, "center": 0.0, "maximum": 1.0},
                "missing_policy": missing_policy,
                "data_table": cast(list[JsonValue], cells),
            },
            warnings=warnings,
        )


class MissingDataMapPlugin:
    """Create a deterministic missing-data heatmap PlotSpec."""

    def run(self, context: PluginContext) -> PluginResult:
        descriptor, values = _read_single_input(context, "building missing-data map")
        variables_axis = _parameter_int(context.parameters, "variables_axis")
        variable_start = _parameter_int(context.parameters, "variable_start")
        variable_count = _parameter_int(context.parameters, "variable_count")
        max_variables = _parameter_int(context.parameters, "max_variables")
        max_observations = _parameter_int(context.parameters, "max_observations")
        seed = _parameter_int(context.parameters, "seed")
        matrix, labels = _variable_observation_matrix(
            values,
            variables_axis=variables_axis,
            variable_start=variable_start,
            variable_count=variable_count,
            max_variables=max_variables,
        )
        sampled_matrix, observation_indices, sampling, sampled = _sample_observations(
            matrix,
            max_observations=max_observations,
            seed=seed,
        )
        cells = _missing_data_cells(
            sampled_matrix,
            labels=labels,
            observation_indices=observation_indices,
        )
        x_values = tuple(float(cast(int, cell["observation_position"])) for cell in cells)
        y_values = tuple(float(cast(int, cell["variable_index"])) for cell in cells)
        heat_values = tuple(float(cast(int, cell["missing"])) for cell in cells)
        return _plot_result(
            plugin_id=MISSING_DATA_MAP_PLUGIN_ID,
            title="Missing Data Map",
            descriptor=descriptor,
            parameters=context.parameters,
            plot=PlotSpec(
                title="Missing Data Map",
                x_label="observation",
                y_label="variable",
                marks=(
                    PlotMark(
                        kind="heatmap",
                        x=x_values,
                        y=y_values,
                        values=heat_values,
                        label="missing",
                    ),
                ),
            ),
            sampled=sampled,
            metadata={
                "plot_family": "missing_data_map",
                "labels": list(labels),
                "value_range": [0.0, 1.0],
                "legend": {"0": "present", "1": "missing"},
                "sampling": sampling,
                "data_table": cast(list[JsonValue], cells),
            },
            warnings=(),
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
        raise ValueError("heatmap plugins require at least two dimensions")
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


def _correlation_heatmap_cells(
    matrix: np.ndarray,
    *,
    labels: tuple[str, ...],
    missing_policy: str,
) -> tuple[list[dict[str, JsonValue]], tuple[str, ...]]:
    if missing_policy not in {"listwise", "pairwise"}:
        raise ValueError("missing_policy must be listwise or pairwise")
    working = np.asarray(matrix, dtype=np.float64)
    listwise_mask = np.all(np.isfinite(working), axis=0) if missing_policy == "listwise" else None
    cells: list[dict[str, JsonValue]] = []
    warnings: list[str] = []
    constant_labels: set[str] = set()
    for row_index, row_label in enumerate(labels):
        for column_index, column_label in enumerate(labels):
            row_values = working[row_index]
            column_values = working[column_index]
            mask = (
                np.isfinite(row_values) & np.isfinite(column_values)
                if listwise_mask is None
                else listwise_mask
            )
            left = row_values[mask]
            right = column_values[mask]
            correlation = _sample_correlation_or_none(left, right)
            if left.size >= 2 and (_is_constant(left) or _is_constant(right)):
                if _is_constant(left):
                    constant_labels.add(row_label)
                if _is_constant(right):
                    constant_labels.add(column_label)
            cells.append(
                {
                    "row_index": row_index,
                    "column_index": column_index,
                    "row_variable": row_label,
                    "column_variable": column_label,
                    "correlation": correlation,
                    "aligned_count": int(left.size),
                }
            )
    for label in sorted(constant_labels, key=lambda item: int(item) if item.isdecimal() else item):
        warnings.append(f"CONSTANT_VARIABLE: variable {label} has zero variance; correlation is undefined.")
    return cells, tuple(warnings)


def _sample_correlation_or_none(left: np.ndarray, right: np.ndarray) -> JsonValue:
    if left.size < 2:
        return None
    left_std = float(np.std(left, ddof=1))
    right_std = float(np.std(right, ddof=1))
    if left_std == 0.0 or right_std == 0.0:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def _is_constant(values: np.ndarray) -> bool:
    return values.size >= 2 and float(np.std(values, ddof=1)) == 0.0


def _rounded_or_none(value: JsonValue) -> JsonValue:
    if isinstance(value, float):
        return round(value, 12)
    return value


def _sample_observations(
    matrix: np.ndarray,
    *,
    max_observations: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, JsonValue] | None, bool]:
    if max_observations < 0:
        raise ValueError("max_observations must be non-negative")
    population_size = int(matrix.shape[1])
    if max_observations == 0 or max_observations >= population_size:
        return matrix, np.arange(population_size), None, False
    rng = np.random.default_rng(seed)
    indices = np.sort(rng.choice(population_size, size=max_observations, replace=False))
    sampling: dict[str, JsonValue] = {
        "method": "without_replacement",
        "axis": "observation",
        "seed": seed,
        "requested_size": max_observations,
        "actual_size": int(indices.size),
        "population_size": population_size,
    }
    return matrix[:, indices], indices, sampling, True


def _missing_data_cells(
    matrix: np.ndarray,
    *,
    labels: tuple[str, ...],
    observation_indices: np.ndarray,
) -> list[dict[str, JsonValue]]:
    cells: list[dict[str, JsonValue]] = []
    missing = np.isnan(np.asarray(matrix, dtype=np.float64))
    for variable_index, variable_label in enumerate(labels):
        for observation_position, observation_index in enumerate(observation_indices):
            is_missing = bool(missing[variable_index, observation_position])
            cells.append(
                {
                    "variable_index": variable_index,
                    "variable": variable_label,
                    "observation_position": observation_position,
                    "observation_index": int(observation_index),
                    "missing": 1 if is_missing else 0,
                }
            )
    return cells


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


def _parameter_str(parameters: object, name: str) -> str:
    value = parameters[name]  # type: ignore[index]
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a string")
    return value
