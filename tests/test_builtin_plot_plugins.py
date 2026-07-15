"""DV-0805 declarative line/scatter/histogram/box plot plugin contracts."""

from __future__ import annotations

from importlib import resources

import numpy as np

from data_viewer.plugins.parameters import validate_parameter_schema, validate_parameters
from data_viewer.plugins.registry import discover_builtin_plugins
from data_viewer.plugins.results import PlotSpec, validate_plugin_result
from data_viewer.plugins.runner import PluginInputBinding, PluginRunRequest, PluginRunner
from tests.conformance.plugin import assert_plugin_source_avoids_forbidden_imports
from tests.test_plugin_runner import _document


LINE_PLOT_ID = "org.dataviewer.line_plot"
SCATTER_PLOT_ID = "org.dataviewer.scatter_plot"
HISTOGRAM_PLOT_ID = "org.dataviewer.histogram_plot"
BOX_PLOT_ID = "org.dataviewer.box_plot"


def _run_plot(plugin_id: str, values: np.ndarray, parameters: dict[str, object]):
    document, fake = _document(values)
    registry = discover_builtin_plugins()
    manifest = registry.manifest_for(plugin_id)
    schema = validate_parameter_schema(manifest.parameters_schema)
    plugin_class = registry.load_plugin_class(plugin_id)
    snapshot = PluginRunner().run(
        PluginRunRequest(
            manifest=manifest,
            plugin=plugin_class(),
            document=document,
            inputs=(PluginInputBinding(resource_id=fake.resource_id),),
            parameters=validate_parameters(schema, parameters),
            memory_budget_bytes=128,
            temp_budget_bytes=1024,
        )
    )
    assert snapshot.error is None
    return validate_plugin_result(snapshot.result)


def _run_plot_snapshot(plugin_id: str, values: np.ndarray, parameters: dict[str, object]):
    document, fake = _document(values)
    registry = discover_builtin_plugins()
    manifest = registry.manifest_for(plugin_id)
    schema = validate_parameter_schema(manifest.parameters_schema)
    plugin_class = registry.load_plugin_class(plugin_id)
    return PluginRunner().run(
        PluginRunRequest(
            manifest=manifest,
            plugin=plugin_class(),
            document=document,
            inputs=(PluginInputBinding(resource_id=fake.resource_id),),
            parameters=validate_parameters(schema, parameters),
            memory_budget_bytes=128,
            temp_budget_bytes=1024,
        )
    )


def test_plot_plugins_are_discovered_as_packaged_builtins() -> None:
    """The four DV-0805 plot plugins ship as independent built-in manifests."""

    registry = discover_builtin_plugins()
    ids = {manifest.id for manifest in registry.available_plugins()}

    assert {LINE_PLOT_ID, SCATTER_PLOT_ID, HISTOGRAM_PLOT_ID, BOX_PLOT_ID} <= ids


def test_line_plot_omits_nonfinite_values_and_exports_renderer_ready_spec() -> None:
    """Line plots are declarative PlotSpecs with accessibility/export metadata."""

    result = _run_plot(
        LINE_PLOT_ID,
        np.array([0.0, 1.0, np.nan, 3.0, np.inf], dtype=np.float64),
        {"sample_size": 0, "seed": 0},
    )

    assert result.kind.value == "plot"
    assert result.result_channel == "workspace.plot"
    assert isinstance(result.payload, PlotSpec)
    assert result.payload.title == "Line Plot"
    assert result.payload.x_label == "index"
    assert result.payload.y_label == "value"
    mark = result.payload.marks[0]
    assert mark.kind == "line"
    assert mark.label == "series 0"
    assert mark.x == (0.0, 1.0, 3.0)
    assert mark.y == (0.0, 1.0, 3.0)
    assert result.metadata["data_table"] == [
        {"x": 0.0, "y": 0.0, "series": "series 0"},
        {"x": 1.0, "y": 1.0, "series": "series 0"},
        {"x": 3.0, "y": 3.0, "series": "series 0"},
    ]
    assert result.provenance.plugin_id == LINE_PLOT_ID
    assert result.provenance.sampled is False
    assert "NONFINITE_DROPPED: 2 nonfinite point(s) were omitted." in result.warnings
    assert "Line Plot" in result.accessible_summary()
    assert result.to_export_record()["result_kind"] == "plot"


def test_scatter_plot_sampling_is_explicit_and_deterministic() -> None:
    """Point sampling is recorded and deterministic for scatter plots."""

    values = np.column_stack((np.arange(10, dtype=np.float64), np.arange(10, dtype=np.float64) ** 2))
    parameters = {"x_column": 0, "y_column": 1, "sample_size": 4, "seed": 42}

    first = _run_plot(SCATTER_PLOT_ID, values, parameters)
    second = _run_plot(SCATTER_PLOT_ID, values, parameters)

    first_mark = first.payload.marks[0]
    second_mark = second.payload.marks[0]
    assert first_mark.kind == "scatter"
    assert first_mark.x == second_mark.x
    assert first_mark.y == second_mark.y
    assert len(first_mark.x) == 4
    assert first.provenance.sampled is True
    assert first.metadata["sampling"] == {
        "method": "without_replacement",
        "seed": 42,
        "requested_size": 4,
        "actual_size": 4,
        "population_size": 10,
    }


def test_histogram_and_box_plot_goldens() -> None:
    """Histogram and box plugins produce known declarative mark data."""

    values = np.array([0.0, 1.0, 2.0, 3.0, np.nan], dtype=np.float64)

    histogram = _run_plot(HISTOGRAM_PLOT_ID, values, {"bins": 2, "sample_size": 0, "seed": 0})
    histogram_mark = histogram.payload.marks[0]
    assert histogram_mark.kind == "histogram"
    assert histogram_mark.x == (0.75, 2.25)
    assert histogram_mark.y == (2.0, 2.0)
    assert histogram.payload.x_label == "bin center"
    assert histogram.payload.y_label == "count"
    assert histogram.metadata["data_table"] == [
        {"x": 0.75, "y": 2.0, "series": "histogram"},
        {"x": 2.25, "y": 2.0, "series": "histogram"},
    ]

    box = _run_plot(BOX_PLOT_ID, values, {"sample_size": 0, "seed": 0})
    box_mark = box.payload.marks[0]
    assert box_mark.kind == "box"
    assert box_mark.x == (0.0, 1.0, 2.0, 3.0, 4.0)
    assert box_mark.y == (0.0, 0.75, 1.5, 2.25, 3.0)
    assert box_mark.label == "min/q1/median/q3/max"


def test_plot_plugins_refuse_empty_finite_data() -> None:
    """Plot plugins do not publish invalid empty PlotSpecs."""

    snapshot = _run_plot_snapshot(
        LINE_PLOT_ID,
        np.array([np.nan, np.inf], dtype=np.float64),
        {"sample_size": 0, "seed": 0},
    )

    assert snapshot.error is not None
    assert snapshot.error.details["plugin_id"] == LINE_PLOT_ID
    assert "no finite values available for plot" in str(snapshot.error.cause)


def test_plot_plugins_forbidden_imports() -> None:
    """Plot plugin code stays inside the public Plugin API boundary."""

    source_path = resources.files("data_viewer.plugins.builtin.plots").joinpath("plugin.py")
    with resources.as_file(source_path) as path:
        assert_plugin_source_avoids_forbidden_imports(path)
