"""DV-0804 Dataset Compare plugin contracts."""

from __future__ import annotations

from importlib import resources
from typing import Any

import numpy as np
import pytest

from data_viewer.app.documents import DocumentController
from data_viewer.domain import (
    ArrayPayload,
    DataDomain,
    DataMetadata,
    DataViewerError,
    ErrorCode,
    NodeKind,
    OperationScope,
    ReadResult,
    ResourceId,
    ResourceNode,
    SelectionSpec,
    SourceCapability,
    SourceFingerprint,
)
from data_viewer.plugins.parameters import validate_parameter_schema, validate_parameters
from data_viewer.plugins.registry import discover_builtin_plugins
from data_viewer.plugins.results import TableResultPayload, validate_plugin_result
from data_viewer.plugins.runner import PluginInputBinding, PluginRunRequest, PluginRunner
from data_viewer.sources import ManagedSourceSession, NodePage, ReadRequest
from tests.conformance.plugin import assert_plugin_source_avoids_forbidden_imports


DATASET_COMPARE_ID = "org.dataviewer.dataset_compare"


class CompareArraySession:
    """Two-resource array session for dataset-compare tests."""

    def __init__(self, left: np.ndarray, right: np.ndarray) -> None:
        self.values = {
            ResourceId("file:///tmp/dataset-compare.npy", "/left"): left,
            ResourceId("file:///tmp/dataset-compare.npy", "/right"): right,
        }
        self.left_id, self.right_id = tuple(self.values)
        self.source_uri = "file:///tmp/dataset-compare.npy"
        self.fingerprint = SourceFingerprint(size_bytes=left.nbytes + right.nbytes, modified_time_ns=1)
        self.capabilities = SourceCapability.RANDOM_SLICE

    def root(self) -> ResourceNode:
        return ResourceNode(
            resource_id=ResourceId(self.source_uri, "/"),
            name="root",
            node_kind=NodeKind.ROOT,
            domain=DataDomain.HIERARCHICAL_ARRAY,
            has_children=True,
        )

    def list_children(self, *args: object, **kwargs: object) -> NodePage:
        return NodePage(items=(), next_cursor=None, total_count=0)

    def get_metadata(self, resource: ResourceId, **kwargs: object) -> DataMetadata:
        values = self.values[resource]
        return DataMetadata(
            resource_id=resource,
            name=resource.node_path.strip("/"),
            domain=DataDomain.ARRAY,
            node_kind=NodeKind.RESOURCE,
            shape=tuple(int(item) for item in values.shape),
            dtype=str(values.dtype),
            logical_size_bytes=int(values.nbytes),
            capabilities=SourceCapability.RANDOM_SLICE,
        )

    def read(self, request: ReadRequest, **kwargs: object) -> ReadResult:
        values = self.values[request.resource_id]
        selection = request.selection.normalize(tuple(int(item) for item in values.shape)).unwrap()
        selected = values[selection.to_numpy_key()]
        if int(selected.nbytes) > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Fake compare read exceeded the requested budget.",
                operation="fake.compare.read",
                details={"bytes_read": int(selected.nbytes), "max_bytes": request.max_bytes},
            )
        return ReadResult(
            payload=ArrayPayload(
                values=np.asarray(selected),
                original_shape=tuple(int(item) for item in values.shape),
                selection=selection,
            ),
            scope=OperationScope.SLICE,
            bytes_read=int(selected.nbytes),
            is_sampled=False,
            sample=None,
        )

    def search(self, *args: object, **kwargs: object) -> NodePage:
        return NodePage(items=(), next_cursor=None, total_count=0)

    def refresh_fingerprint(self) -> SourceFingerprint:
        return self.fingerprint

    def close(self) -> None:
        return None


def _compare_document(left: np.ndarray, right: np.ndarray) -> tuple[DocumentController, CompareArraySession]:
    fake = CompareArraySession(left, right)
    document = DocumentController(ManagedSourceSession(fake))
    document.navigate_to(fake.left_id)
    return document, fake


def _run_compare(left: np.ndarray, right: np.ndarray, parameters: dict[str, object]):
    document, fake = _compare_document(left, right)
    registry = discover_builtin_plugins()
    manifest = registry.manifest_for(DATASET_COMPARE_ID)
    schema = validate_parameter_schema(manifest.parameters_schema)
    plugin_class = registry.load_plugin_class(DATASET_COMPARE_ID)
    snapshot = PluginRunner().run(
        PluginRunRequest(
            manifest=manifest,
            plugin=plugin_class(),
            document=document,
            inputs=(
                PluginInputBinding(resource_id=fake.left_id, selection=SelectionSpec.all()),
                PluginInputBinding(resource_id=fake.right_id, selection=SelectionSpec.all()),
            ),
            parameters=validate_parameters(schema, parameters),
            memory_budget_bytes=256,
            temp_budget_bytes=1024,
        )
    )
    assert snapshot.error is None
    return validate_plugin_result(snapshot.result)


def _run_compare_snapshot(left: np.ndarray, right: np.ndarray, parameters: dict[str, object]):
    document, fake = _compare_document(left, right)
    registry = discover_builtin_plugins()
    manifest = registry.manifest_for(DATASET_COMPARE_ID)
    schema = validate_parameter_schema(manifest.parameters_schema)
    plugin_class = registry.load_plugin_class(DATASET_COMPARE_ID)
    return PluginRunner().run(
        PluginRunRequest(
            manifest=manifest,
            plugin=plugin_class(),
            document=document,
            inputs=(
                PluginInputBinding(resource_id=fake.left_id, selection=SelectionSpec.all()),
                PluginInputBinding(resource_id=fake.right_id, selection=SelectionSpec.all()),
            ),
            parameters=validate_parameters(schema, parameters),
            memory_budget_bytes=256,
            temp_budget_bytes=1024,
        )
    )


def _rows(result: Any) -> dict[tuple[str, str], object]:
    assert isinstance(result.payload, TableResultPayload)
    return {(str(row["section"]), str(row["metric"])): row["value"] for row in result.payload.rows}


def test_dataset_compare_is_discovered_as_packaged_builtin() -> None:
    """Dataset Compare ships as a validated built-in plugin manifest."""

    registry = discover_builtin_plugins()

    assert DATASET_COMPARE_ID in [manifest.id for manifest in registry.available_plugins()]


def test_dataset_compare_identical_arrays_golden() -> None:
    """Identical arrays expose exact compatibility, equality, and zero-error metrics."""

    values = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)

    result = _run_compare(
        values,
        values.copy(),
        {"missing_policy": "pairwise", "relative_error_mode": "left"},
    )

    assert result.provenance.plugin_id == DATASET_COMPARE_ID
    assert result.provenance.sampled is False
    rows = _rows(result)
    assert rows[("compatibility", "shape_match")] is True
    assert rows[("compatibility", "dtype_match")] is True
    assert rows[("compatibility", "alignment_policy")] == "exact_shape"
    assert rows[("counts", "element_count")] == 4
    assert rows[("counts", "equal_count")] == 4
    assert rows[("errors", "max_absolute_error")] == 0.0
    assert rows[("errors", "max_relative_error")] == 0.0


def test_dataset_compare_near_different_nonfinite_and_zero_rules() -> None:
    """Absolute/relative errors are explicit for finite pairs and nonfinite values."""

    left = np.array([0.0, 1.0, 2.0, np.nan, np.inf], dtype=np.float64)
    right = np.array([0.0, 1.5, 1.0, np.nan, np.inf], dtype=np.float64)

    result = _run_compare(
        left,
        right,
        {"missing_policy": "pairwise", "relative_error_mode": "left"},
    )

    rows = _rows(result)
    assert rows[("counts", "element_count")] == 5
    assert rows[("counts", "equal_count")] == 2
    assert rows[("counts", "different_count")] == 3
    assert rows[("counts", "finite_pair_count")] == 3
    assert rows[("counts", "nonfinite_pair_count")] == 2
    assert rows[("errors", "max_absolute_error")] == 1.0
    assert rows[("errors", "mean_absolute_error")] == pytest.approx(0.5, abs=1e-12)
    assert rows[("errors", "max_relative_error")] == pytest.approx(0.5, abs=1e-12)
    assert rows[("errors", "relative_error_undefined_count")] == 0
    assert result.metadata["missing_policy"] == "pairwise"


def test_dataset_compare_refuses_ambiguous_broadcasting() -> None:
    """Shape mismatch fails before payload metrics instead of broadcasting implicitly."""

    snapshot = _run_compare_snapshot(
        np.arange(4, dtype=np.float64).reshape(2, 2),
        np.arange(2, dtype=np.float64),
        {"missing_policy": "pairwise", "relative_error_mode": "left"},
    )

    assert snapshot.error is not None
    assert snapshot.error.details["plugin_id"] == DATASET_COMPARE_ID
    assert "shape mismatch: (2, 2) != (2,)" in str(snapshot.error.cause)


def test_dataset_compare_forbidden_imports() -> None:
    """Dataset Compare plugin code stays inside the public Plugin API boundary."""

    source_path = resources.files("data_viewer.plugins.builtin.dataset_profile").joinpath("plugin.py")
    with resources.as_file(source_path) as path:
        assert_plugin_source_avoids_forbidden_imports(path)
