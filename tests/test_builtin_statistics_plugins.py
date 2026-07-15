"""DV-0801 Dataset Profile and Descriptive Statistics plugin contracts."""

from __future__ import annotations

from importlib import resources

import numpy as np

from data_viewer.plugins.parameters import validate_parameter_schema, validate_parameters
from data_viewer.plugins.registry import discover_builtin_plugins
from data_viewer.plugins.results import TableResultPayload, validate_plugin_result
from data_viewer.plugins.runner import PluginInputBinding, PluginRunRequest, PluginRunner
from tests.conformance.plugin import assert_plugin_source_avoids_forbidden_imports
from tests.test_plugin_runner import _document


DATASET_PROFILE_ID = "org.dataviewer.dataset_profile"
DESCRIPTIVE_STATS_ID = "org.dataviewer.descriptive_statistics"


def _run_plugin(plugin_id: str, values: np.ndarray, parameters: dict[str, object]):
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
            memory_budget_bytes=32,
            temp_budget_bytes=1024,
        )
    )
    assert snapshot.error is None
    return validate_plugin_result(snapshot.result)


def test_statistics_plugins_are_discovered_in_deterministic_order() -> None:
    """P8 statistics plugins are packaged built-ins with stable manifest ordering."""

    registry = discover_builtin_plugins()

    assert [manifest.id for manifest in registry.available_plugins()][:2] == [
        DATASET_PROFILE_ID,
        DESCRIPTIVE_STATS_ID,
    ]


def test_dataset_profile_reports_storage_and_complex_edge_metrics() -> None:
    """Dataset Profile includes storage estimates and complex magnitude semantics."""

    values = np.array([1 + 2j, 3 + 4j, np.nan + 0j, np.inf + 0j], dtype=np.complex128)

    result = _run_plugin(DATASET_PROFILE_ID, values, {})

    assert dict(result.payload) == {
        "shape": [4],
        "dtype": "complex128",
        "element_count": 4,
        "estimated_bytes": values.nbytes,
        "finite_count": 2,
        "missing_count": 1,
        "positive_infinity_count": 1,
        "negative_infinity_count": 0,
        "minimum": float(abs(1 + 2j)),
        "maximum": float(abs(3 + 4j)),
        "mean": float(np.mean(np.abs(values[np.isfinite(values)]))),
        "value_semantics": "complex_magnitude",
        "computation_scope": "full",
        "sampled": False,
    }


def test_descriptive_statistics_flattened_golden_and_provenance() -> None:
    """Descriptive Statistics computes stable full-scope metrics with explicit NaN policy."""

    values = np.array([1.0, np.nan, 2.0, 4.0, np.inf], dtype=np.float64)

    result = _run_plugin(
        DESCRIPTIVE_STATS_ID,
        values,
        {"axis": -1, "nan_policy": "omit", "quantile_low": 0.25, "quantile_high": 0.75},
    )

    assert result.provenance.plugin_id == DESCRIPTIVE_STATS_ID
    assert result.provenance.parameters == {
        "axis": -1,
        "nan_policy": "omit",
        "quantile_low": 0.25,
        "quantile_high": 0.75,
    }
    assert isinstance(result.payload, TableResultPayload)
    rows = {row["metric"]: row["value"] for row in result.payload.rows}
    assert rows == {
        "count": 3,
        "missing_count": 1,
        "positive_infinity_count": 1,
        "negative_infinity_count": 0,
        "mean": np.mean([1.0, 2.0, 4.0]),
        "std": np.std([1.0, 2.0, 4.0], ddof=1),
        "minimum": 1.0,
        "q25": 1.5,
        "median": 2.0,
        "q75": 3.0,
        "maximum": 4.0,
    }


def test_descriptive_statistics_axis_zero_golden() -> None:
    """Axis-aware stats preserve the requested axis in row labels."""

    values = np.array([[1.0, np.nan, 5.0], [3.0, 4.0, np.inf]], dtype=np.float64)

    result = _run_plugin(
        DESCRIPTIVE_STATS_ID,
        values,
        {"axis": 0, "nan_policy": "omit", "quantile_low": 0.25, "quantile_high": 0.75},
    )

    rows = {(row["axis"], row["metric"]): row["value"] for row in result.payload.rows}
    assert rows[("0", "mean")] == 2.0
    assert rows[("1", "mean")] == 4.0
    assert rows[("2", "mean")] == 5.0
    assert rows[("2", "positive_infinity_count")] == 1


def test_descriptive_statistics_forbidden_imports() -> None:
    """Statistics plugin code stays inside the public Plugin API boundary."""

    source_path = resources.files("data_viewer.plugins.builtin.dataset_profile").joinpath("plugin.py")
    with resources.as_file(source_path) as path:
        assert_plugin_source_avoids_forbidden_imports(path)
