"""Reusable conformance checks for built-in Plugin API v1 plugins."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from data_viewer.app.documents import DocumentController
from data_viewer.domain import ResourceId, SelectionSpec
from data_viewer.plugins.api import DataViewerPlugin
from data_viewer.plugins.compatibility import (
    PluginInputCandidate,
    evaluate_plugin_compatibility,
)
from data_viewer.plugins.manifests import PluginManifest
from data_viewer.plugins.parameters import (
    default_parameters,
    validate_parameter_schema,
    validate_parameters,
)
from data_viewer.plugins.results import validate_plugin_result
from data_viewer.plugins.runner import (
    PluginInputBinding,
    PluginRunRequest,
    PluginRunner,
)
from data_viewer.tasks import CancellationToken
from data_viewer.tasks import TaskSnapshot, TaskState


FORBIDDEN_PLUGIN_IMPORT_PREFIXES = (
    "data_viewer.gui",
    "data_viewer.ui",
    "data_viewer.sources",
    "data_viewer.app.documents",
    "h5py",
    "nibabel",
    "openpyxl",
    "pandas",
    "PyQt6",
)


def assert_plugin_source_avoids_forbidden_imports(
    source_path: Path,
    *,
    forbidden_prefixes: tuple[str, ...] = FORBIDDEN_PLUGIN_IMPORT_PREFIXES,
) -> None:
    """Assert a plugin does not import GUI, adapter, or raw format handles."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    violations = tuple(
        name
        for name in imports
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in forbidden_prefixes)
    )
    assert violations == ()


def assert_single_input_plugin_conforms(
    *,
    manifest: PluginManifest,
    plugin: DataViewerPlugin,
    document: DocumentController,
    resource_id: ResourceId,
    expected_payload: dict[str, object],
    memory_budget_bytes: int = 64,
) -> tuple[object, tuple[TaskSnapshot, ...]]:
    """Run the shared v1 checks for one-input built-in analysis plugins."""

    metadata = document.get_metadata(resource_id, cancellation=CancellationToken())
    compatible = evaluate_plugin_compatibility(
        manifest,
        (PluginInputCandidate(metadata=metadata),),
        memory_budget_bytes=memory_budget_bytes,
        available_dependencies=frozenset(manifest.required_dependencies),
    )
    assert compatible.enabled, compatible.reasons

    wrong_domain = evaluate_plugin_compatibility(
        manifest,
        (),
        memory_budget_bytes=memory_budget_bytes,
    )
    assert wrong_domain.reasons == ("plugin expects exactly 1 input; received 0",)

    schema = validate_parameter_schema(manifest.parameters_schema)
    defaults = default_parameters(schema)
    parameters = validate_parameters(schema, defaults)
    snapshots: list[TaskSnapshot] = []
    task = document.create_task(f"plugin.run:{manifest.id}:conformance")
    task.add_listener(snapshots.append)
    snapshot = PluginRunner().run(
        PluginRunRequest(
            manifest=manifest,
            plugin=plugin,
            document=document,
            inputs=(PluginInputBinding(resource_id=resource_id, selection=SelectionSpec.all()),),
            parameters=parameters,
            memory_budget_bytes=memory_budget_bytes,
            temp_budget_bytes=1024,
            task=task,
        )
    )

    assert snapshot.state is TaskState.SUCCEEDED
    result = snapshot.result
    validated = validate_plugin_result(result)
    assert dict(validated.payload) == expected_payload
    assert validated.provenance.plugin_id == manifest.id
    assert validated.provenance.plugin_version == manifest.version
    assert validated.provenance.parameters == parameters
    assert validated.provenance.inputs[0].resource_path == resource_id.node_path
    assert validated.provenance.sampled is False
    return validated, tuple(snapshots)


def assert_plugin_cancels_across_chunks(
    *,
    manifest: PluginManifest,
    plugin: DataViewerPlugin,
    document: DocumentController,
    resource_id: ResourceId,
    memory_budget_bytes: int = 64,
) -> None:
    """Assert cancellation during chunk access publishes no partial final result."""

    task = document.create_task(f"plugin.run:{manifest.id}:cancel-test")
    task.cancellation.cancel()

    snapshot = PluginRunner().run(
        PluginRunRequest(
            manifest=manifest,
            plugin=plugin,
            document=document,
            inputs=(PluginInputBinding(resource_id=resource_id, selection=SelectionSpec.all()),),
            parameters=validate_parameters(
                validate_parameter_schema(manifest.parameters_schema),
                default_parameters(validate_parameter_schema(manifest.parameters_schema)),
            ),
            memory_budget_bytes=memory_budget_bytes,
            temp_budget_bytes=1024,
            task=task,
        )
    )

    assert snapshot.state is TaskState.CANCELLED
    assert snapshot.result is None


def expected_profile_payload(values: np.ndarray) -> dict[str, object]:
    """Return the reference Dataset Profile summary for a numeric ndarray."""

    finite = values[np.isfinite(values)]
    return {
        "shape": list(values.shape),
        "dtype": str(values.dtype),
        "element_count": int(values.size),
        "finite_count": int(finite.size),
        "missing_count": int(np.isnan(values).sum()) if np.issubdtype(values.dtype, np.floating) else 0,
        "positive_infinity_count": int(np.isposinf(values).sum())
        if np.issubdtype(values.dtype, np.floating)
        else 0,
        "negative_infinity_count": int(np.isneginf(values).sum())
        if np.issubdtype(values.dtype, np.floating)
        else 0,
        "minimum": float(finite.min()) if finite.size else None,
        "maximum": float(finite.max()) if finite.size else None,
        "mean": float(finite.mean()) if finite.size else None,
        "computation_scope": "full",
        "sampled": False,
    }
