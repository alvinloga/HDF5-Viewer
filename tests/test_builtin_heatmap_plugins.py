"""DV-0807 correlation heatmap and missing-data map plugin contracts."""

from __future__ import annotations

from importlib import resources

import numpy as np

from data_viewer.plugins.parameters import validate_parameter_schema, validate_parameters
from data_viewer.plugins.registry import discover_builtin_plugins
from data_viewer.plugins.results import PlotSpec, validate_plugin_result
from data_viewer.plugins.runner import PluginInputBinding, PluginRunRequest, PluginRunner
from tests.conformance.plugin import assert_plugin_source_avoids_forbidden_imports
from tests.test_plugin_runner import _document


CORRELATION_HEATMAP_ID = "org.dataviewer.correlation_heatmap"
MISSING_DATA_MAP_ID = "org.dataviewer.missing_data_map"


def _run_heatmap(plugin_id: str, values: np.ndarray, parameters: dict[str, object]):
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
            memory_budget_bytes=256,
            temp_budget_bytes=1024,
        )
    )
    assert snapshot.error is None
    return validate_plugin_result(snapshot.result)


def test_heatmap_plugins_are_discovered_as_packaged_builtins() -> None:
    """DV-0807 ships heatmap plugins as independent built-in manifests."""

    registry = discover_builtin_plugins()
    ids = {manifest.id for manifest in registry.available_plugins()}

    assert {CORRELATION_HEATMAP_ID, MISSING_DATA_MAP_ID} <= ids


def test_correlation_heatmap_exports_labeled_range_and_table_alternative() -> None:
    """Correlation heatmap cells are labeled, range-bounded, and accessible."""

    values = np.array(
        [
            [1.0, 1.0],
            [2.0, 2.0],
            [3.0, 4.0],
        ],
        dtype=np.float64,
    )

    result = _run_heatmap(
        CORRELATION_HEATMAP_ID,
        values,
        {
            "variables_axis": 1,
            "variable_start": 0,
            "variable_count": 0,
            "missing_policy": "listwise",
            "max_variables": 16,
        },
    )

    assert result.kind.value == "plot"
    assert result.result_channel == "workspace.plot"
    assert isinstance(result.payload, PlotSpec)
    assert result.payload.title == "Correlation Heatmap"
    assert result.payload.x_label == "column variable"
    assert result.payload.y_label == "row variable"
    mark = result.payload.marks[0]
    assert mark.kind == "heatmap"
    assert mark.label == "correlation"
    assert mark.x == (0.0, 1.0, 0.0, 1.0)
    assert mark.y == (0.0, 0.0, 1.0, 1.0)
    assert mark.values == (
        1.0,
        float(np.corrcoef(values[:, 0], values[:, 1])[0, 1]),
        float(np.corrcoef(values[:, 1], values[:, 0])[0, 1]),
        1.0,
    )
    assert result.metadata["plot_family"] == "correlation_heatmap"
    assert result.metadata["labels"] == ["0", "1"]
    assert result.metadata["value_range"] == [-1.0, 1.0]
    assert result.metadata["legend"] == {"minimum": -1.0, "center": 0.0, "maximum": 1.0}
    assert result.metadata["data_table"][1] == {
        "row_index": 0,
        "column_index": 1,
        "row_variable": "0",
        "column_variable": "1",
        "correlation": mark.values[1],
        "aligned_count": 3,
    }
    assert "Correlation Heatmap" in result.accessible_summary()


def test_missing_data_map_records_sampling_and_table_alternative() -> None:
    """Missing-data maps use explicit 0/1 semantics with deterministic sampling."""

    values = np.array(
        [
            [1.0, np.nan, 3.0],
            [4.0, 5.0, np.nan],
            [7.0, 8.0, 9.0],
        ],
        dtype=np.float64,
    )

    first = _run_heatmap(
        MISSING_DATA_MAP_ID,
        values,
        {
            "variables_axis": 1,
            "variable_start": 0,
            "variable_count": 0,
            "max_variables": 16,
            "max_observations": 2,
            "seed": 7,
        },
    )
    second = _run_heatmap(
        MISSING_DATA_MAP_ID,
        values,
        {
            "variables_axis": 1,
            "variable_start": 0,
            "variable_count": 0,
            "max_variables": 16,
            "max_observations": 2,
            "seed": 7,
        },
    )

    mark = first.payload.marks[0]
    assert mark.kind == "heatmap"
    assert mark.label == "missing"
    assert mark.values == second.payload.marks[0].values
    assert set(mark.values) <= {0.0, 1.0}
    assert first.provenance.sampled is True
    assert first.metadata["plot_family"] == "missing_data_map"
    assert first.metadata["value_range"] == [0.0, 1.0]
    assert first.metadata["legend"] == {"0": "present", "1": "missing"}
    assert first.metadata["sampling"] == {
        "method": "without_replacement",
        "axis": "observation",
        "seed": 7,
        "requested_size": 2,
        "actual_size": 2,
        "population_size": 3,
    }
    assert len(first.metadata["data_table"]) == 6


def test_heatmap_plugins_forbidden_imports() -> None:
    """Heatmap plugin code stays inside the public Plugin API boundary."""

    source_path = resources.files("data_viewer.plugins.builtin.plots").joinpath("plugin.py")
    with resources.as_file(source_path) as path:
        assert_plugin_source_avoids_forbidden_imports(path)
