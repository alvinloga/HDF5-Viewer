"""DV-0802 Distribution Summary plugin contracts."""

from __future__ import annotations

from importlib import resources

import numpy as np

from data_viewer.plugins.parameters import validate_parameter_schema, validate_parameters
from data_viewer.plugins.registry import discover_builtin_plugins
from data_viewer.plugins.results import TableResultPayload, validate_plugin_result
from data_viewer.plugins.runner import PluginInputBinding, PluginRunRequest, PluginRunner
from tests.conformance.plugin import assert_plugin_source_avoids_forbidden_imports
from tests.test_plugin_runner import _document


DISTRIBUTION_ID = "org.dataviewer.distribution_summary"


def _run_distribution(values: np.ndarray, parameters: dict[str, object]):
    document, fake = _document(values)
    registry = discover_builtin_plugins()
    manifest = registry.manifest_for(DISTRIBUTION_ID)
    schema = validate_parameter_schema(manifest.parameters_schema)
    plugin_class = registry.load_plugin_class(DISTRIBUTION_ID)
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


def test_distribution_summary_is_discovered_after_statistics_plugins() -> None:
    """Distribution Summary ships as a deterministic packaged built-in plugin."""

    registry = discover_builtin_plugins()

    assert [manifest.id for manifest in registry.available_plugins()] == [
        "org.dataviewer.dataset_profile",
        "org.dataviewer.descriptive_statistics",
        DISTRIBUTION_ID,
    ]


def test_distribution_summary_histogram_and_robust_golden() -> None:
    """Known finite data produces exact histogram and robust-spread rows."""

    values = np.array([0.0, 1.0, 2.0, 3.0, np.nan, np.inf], dtype=np.float64)

    result = _run_distribution(
        values,
        {"bins": 3, "nan_policy": "omit", "sample_size": 0, "seed": 123},
    )

    assert result.provenance.plugin_id == DISTRIBUTION_ID
    assert result.provenance.sampled is False
    assert result.provenance.parameters == {
        "bins": 3,
        "nan_policy": "omit",
        "sample_size": 0,
        "seed": 123,
    }
    assert isinstance(result.payload, TableResultPayload)
    rows = {(row["section"], row["label"]): row["value"] for row in result.payload.rows}
    assert rows[("summary", "finite_count")] == 4
    assert rows[("summary", "missing_count")] == 1
    assert rows[("summary", "positive_infinity_count")] == 1
    assert rows[("summary", "iqr")] == 1.5
    assert rows[("summary", "mad")] == 1.0
    assert rows[("summary", "skewness")] == 0.0
    assert rows[("summary", "excess_kurtosis")] == -1.36
    assert rows[("histogram", "[0, 1)")] == 1
    assert rows[("histogram", "[1, 2)")] == 1
    assert rows[("histogram", "[2, 3]")] == 2


def test_distribution_summary_constant_and_empty_inputs_are_explicit() -> None:
    """Constant and empty inputs do not invent invalid shape statistics."""

    constant = _run_distribution(
        np.array([5.0, 5.0, 5.0], dtype=np.float64),
        {"bins": 4, "nan_policy": "omit", "sample_size": 0, "seed": 7},
    )
    constant_rows = {(row["section"], row["label"]): row["value"] for row in constant.payload.rows}
    assert constant_rows[("summary", "finite_count")] == 3
    assert constant_rows[("summary", "iqr")] == 0.0
    assert constant_rows[("summary", "skewness")] is None
    assert constant_rows[("summary", "excess_kurtosis")] is None

    empty = _run_distribution(
        np.array([np.nan, np.inf], dtype=np.float64),
        {"bins": 4, "nan_policy": "omit", "sample_size": 0, "seed": 7},
    )
    empty_rows = {(row["section"], row["label"]): row["value"] for row in empty.payload.rows}
    assert empty_rows[("summary", "finite_count")] == 0
    assert empty_rows[("summary", "iqr")] is None
    assert empty_rows[("histogram", "empty")] == 0


def test_distribution_summary_deterministic_sampling_is_recorded() -> None:
    """Sampling is never silent: method, seed, requested and actual sizes are exported."""

    values = np.arange(20, dtype=np.float64)

    result = _run_distribution(
        values,
        {"bins": 5, "nan_policy": "omit", "sample_size": 6, "seed": 42},
    )

    assert result.provenance.sampled is True
    rows = {(row["section"], row["label"]): row["value"] for row in result.payload.rows}
    assert rows[("sampling", "method")] == "without_replacement"
    assert rows[("sampling", "seed")] == 42
    assert rows[("sampling", "requested_size")] == 6
    assert rows[("sampling", "actual_size")] == 6
    assert rows[("sampling", "population_size")] == 20


def test_distribution_summary_forbidden_imports() -> None:
    """Distribution plugin code stays inside the public Plugin API boundary."""

    source_path = resources.files("data_viewer.plugins.builtin.dataset_profile").joinpath("plugin.py")
    with resources.as_file(source_path) as path:
        assert_plugin_source_avoids_forbidden_imports(path)
