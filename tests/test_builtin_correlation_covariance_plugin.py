"""DV-0803 Correlation/Covariance plugin contracts."""

from __future__ import annotations

from importlib import resources

import numpy as np
import pytest

from data_viewer.plugins.parameters import validate_parameter_schema, validate_parameters
from data_viewer.plugins.registry import discover_builtin_plugins
from data_viewer.plugins.results import TableResultPayload, validate_plugin_result
from data_viewer.plugins.runner import PluginInputBinding, PluginRunRequest, PluginRunner
from tests.conformance.plugin import assert_plugin_source_avoids_forbidden_imports
from tests.test_plugin_runner import _document


CORRELATION_ID = "org.dataviewer.correlation_covariance"


def _run_correlation(values: np.ndarray, parameters: dict[str, object]):
    document, fake = _document(values)
    registry = discover_builtin_plugins()
    manifest = registry.manifest_for(CORRELATION_ID)
    schema = validate_parameter_schema(manifest.parameters_schema)
    plugin_class = registry.load_plugin_class(CORRELATION_ID)
    snapshot = PluginRunner().run(
        PluginRunRequest(
            manifest=manifest,
            plugin=plugin_class(),
            document=document,
            inputs=(PluginInputBinding(resource_id=fake.resource_id),),
            parameters=validate_parameters(schema, parameters),
            memory_budget_bytes=64,
            temp_budget_bytes=1024,
        )
    )
    assert snapshot.error is None
    return validate_plugin_result(snapshot.result)


def _run_correlation_snapshot(values: np.ndarray, parameters: dict[str, object]):
    document, fake = _document(values)
    registry = discover_builtin_plugins()
    manifest = registry.manifest_for(CORRELATION_ID)
    schema = validate_parameter_schema(manifest.parameters_schema)
    plugin_class = registry.load_plugin_class(CORRELATION_ID)
    return PluginRunner().run(
        PluginRunRequest(
            manifest=manifest,
            plugin=plugin_class(),
            document=document,
            inputs=(PluginInputBinding(resource_id=fake.resource_id),),
            parameters=validate_parameters(schema, parameters),
            memory_budget_bytes=64,
            temp_budget_bytes=1024,
        )
    )


def _matrix_rows(result) -> dict[tuple[str, str, str], object]:
    assert isinstance(result.payload, TableResultPayload)
    return {
        (str(row["metric"]), str(row["row_variable"]), str(row["column_variable"])): row["value"]
        for row in result.payload.rows
    }


def _count_rows(result) -> dict[tuple[str, str], object]:
    assert isinstance(result.payload, TableResultPayload)
    return {
        (str(row["row_variable"]), str(row["column_variable"])): row["aligned_count"]
        for row in result.payload.rows
        if row["metric"] == "correlation"
    }


def test_correlation_covariance_is_discovered_as_packaged_builtin() -> None:
    """Correlation/Covariance ships as a validated built-in plugin manifest."""

    registry = discover_builtin_plugins()
    ids = [manifest.id for manifest in registry.available_plugins()]

    assert CORRELATION_ID in ids


def test_correlation_covariance_known_matrix_golden() -> None:
    """Known column variables produce labeled symmetric correlation/covariance rows."""

    values = np.array(
        [
            [1.0, 2.0, 1.0],
            [2.0, 4.0, 2.0],
            [3.0, 6.0, 2.0],
            [4.0, 8.0, 4.0],
        ],
        dtype=np.float64,
    )

    result = _run_correlation(
        values,
        {
            "variables_axis": 1,
            "variable_start": 0,
            "variable_count": 0,
            "missing_policy": "listwise",
            "max_variables": 8,
        },
    )

    assert result.provenance.plugin_id == CORRELATION_ID
    assert result.provenance.sampled is False
    assert result.provenance.parameters == {
        "variables_axis": 1,
        "variable_start": 0,
        "variable_count": 0,
        "missing_policy": "listwise",
        "max_variables": 8,
    }
    rows = _matrix_rows(result)
    expected_corr = np.corrcoef(values, rowvar=False)
    expected_cov = np.cov(values, rowvar=False, ddof=1)
    for row_variable in range(3):
        for column_variable in range(3):
            key = (str(row_variable), str(column_variable))
            assert rows[("correlation", *key)] == pytest.approx(
                float(expected_corr[row_variable, column_variable]),
                abs=1e-12,
            )
            assert rows[("covariance", *key)] == pytest.approx(
                float(expected_cov[row_variable, column_variable]),
                abs=1e-12,
            )


def test_correlation_covariance_pairwise_and_listwise_missing_policies() -> None:
    """Missing policies make alignment counts explicit for every pair."""

    values = np.array(
        [
            [1.0, 10.0, 1.0],
            [2.0, np.nan, 2.0],
            [3.0, 30.0, np.nan],
            [4.0, 40.0, 4.0],
        ],
        dtype=np.float64,
    )
    parameters = {
        "variables_axis": 1,
        "variable_start": 0,
        "variable_count": 0,
        "max_variables": 8,
    }

    pairwise = _run_correlation(values, {**parameters, "missing_policy": "pairwise"})
    listwise = _run_correlation(values, {**parameters, "missing_policy": "listwise"})

    pairwise_counts = _count_rows(pairwise)
    assert pairwise_counts[("0", "1")] == 3
    assert pairwise_counts[("0", "2")] == 3
    assert pairwise_counts[("1", "2")] == 2
    assert pairwise.metadata["missing_policy"] == "pairwise"

    listwise_counts = _count_rows(listwise)
    assert listwise_counts[("0", "1")] == 2
    assert listwise_counts[("0", "2")] == 2
    assert listwise_counts[("1", "2")] == 2
    assert listwise.metadata["missing_policy"] == "listwise"


def test_correlation_covariance_selects_contiguous_variable_range() -> None:
    """Variable start/count select a labeled contiguous range on the variables axis."""

    values = np.array(
        [
            [10.0, 1.0, 2.0, 99.0],
            [20.0, 2.0, 4.0, 98.0],
            [30.0, 3.0, 6.0, 97.0],
        ],
        dtype=np.float64,
    )

    result = _run_correlation(
        values,
        {
            "variables_axis": 1,
            "variable_start": 1,
            "variable_count": 2,
            "missing_policy": "listwise",
            "max_variables": 8,
        },
    )

    rows = _matrix_rows(result)
    assert set(key[1:] for key in rows) == {("1", "1"), ("1", "2"), ("2", "1"), ("2", "2")}
    assert rows[("correlation", "1", "2")] == pytest.approx(1.0, abs=1e-12)
    assert result.metadata["variable_start"] == 1
    assert result.metadata["variable_count"] == 2


def test_correlation_covariance_constant_variable_warning() -> None:
    """Constant variables keep covariance defined but mark correlation as invalid."""

    result = _run_correlation(
        np.array([[1.0, 5.0], [2.0, 5.0], [3.0, 5.0]], dtype=np.float64),
        {
            "variables_axis": 1,
            "variable_start": 0,
            "variable_count": 0,
            "missing_policy": "listwise",
            "max_variables": 8,
        },
    )

    rows = _matrix_rows(result)
    assert rows[("correlation", "0", "1")] is None
    assert rows[("correlation", "1", "1")] is None
    assert rows[("covariance", "0", "1")] == 0.0
    assert "CONSTANT_VARIABLE: variable 1 has zero variance; correlation is undefined." in result.warnings


def test_correlation_covariance_refuses_variable_count_over_budget() -> None:
    """The plugin refuses matrix work that exceeds its declared variable budget."""

    snapshot = _run_correlation_snapshot(
        np.arange(12, dtype=np.float64).reshape(3, 4),
        {
            "variables_axis": 1,
            "variable_start": 0,
            "variable_count": 0,
            "missing_policy": "listwise",
            "max_variables": 3,
        },
    )

    assert snapshot.error is not None
    assert snapshot.error.details["plugin_id"] == CORRELATION_ID
    assert "selected variable count 4 exceeds max_variables 3" in str(snapshot.error.cause)


def test_correlation_covariance_forbidden_imports() -> None:
    """Correlation plugin code stays inside the public Plugin API boundary."""

    source_path = resources.files("data_viewer.plugins.builtin.dataset_profile").joinpath("plugin.py")
    with resources.as_file(source_path) as path:
        assert_plugin_source_avoids_forbidden_imports(path)
