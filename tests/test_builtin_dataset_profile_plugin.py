"""DV-0705 reference built-in plugin and conformance kit contracts."""

from __future__ import annotations

from importlib import resources

import numpy as np
import pytest

from data_viewer.plugins.registry import discover_builtin_plugins
from data_viewer.tasks import CancellationToken
from tests.conformance.plugin import (
    assert_plugin_cancels_across_chunks,
    assert_plugin_source_avoids_forbidden_imports,
    assert_single_input_plugin_conforms,
    expected_profile_payload,
)
from tests.test_plugin_runner import _document


PLUGIN_ID = "org.dataviewer.dataset_profile"


def test_dataset_profile_is_discovered_without_import_errors() -> None:
    """The packaged reference plugin manifest is discovered and ordered by the registry."""

    registry = discover_builtin_plugins()
    manifests = registry.available_plugins()

    assert registry.diagnostics() == ()
    assert manifests[0].id == PLUGIN_ID
    assert manifests[0].name == "Dataset Profile"


def test_dataset_profile_passes_shared_conformance_and_numerical_golden() -> None:
    """The reference plugin demonstrates manifest, params, chunks, results, and provenance."""

    values = np.array([[1.0, np.nan], [np.inf, -2.0], [5.0, -np.inf]], dtype=np.float64)
    document, fake = _document(values)
    registry = discover_builtin_plugins()
    manifest = registry.manifest_for(PLUGIN_ID)
    plugin_class = registry.load_plugin_class(PLUGIN_ID)
    plugin = plugin_class()

    _validated, snapshots = assert_single_input_plugin_conforms(
        manifest=manifest,
        plugin=plugin,
        document=document,
        resource_id=fake.resource_id,
        expected_payload=expected_profile_payload(values),
        memory_budget_bytes=16,
    )

    progress_messages = [snapshot.progress.message for snapshot in snapshots]
    assert any(message == "profiling chunks" for message in progress_messages)


def test_dataset_profile_cancel_and_forbidden_import_conformance() -> None:
    """The reference plugin is cooperatively cancellable and avoids forbidden imports."""

    document, fake = _document(np.arange(64, dtype=np.float64).reshape(16, 4))
    registry = discover_builtin_plugins()
    manifest = registry.manifest_for(PLUGIN_ID)
    plugin_class = registry.load_plugin_class(PLUGIN_ID)

    assert_plugin_cancels_across_chunks(
        manifest=manifest,
        plugin=plugin_class(),
        document=document,
        resource_id=fake.resource_id,
        memory_budget_bytes=32,
    )

    source_path = resources.files("data_viewer.plugins.builtin.dataset_profile").joinpath("plugin.py")
    with resources.as_file(source_path) as path:
        assert_plugin_source_avoids_forbidden_imports(path)


def test_dataset_profile_reports_safe_error_for_nonnumeric_input() -> None:
    """Edge inputs that the manifest should not accept fail before plugin execution."""

    document, fake = _document(np.array(["a", "b"], dtype=np.str_))
    registry = discover_builtin_plugins()
    manifest = registry.manifest_for(PLUGIN_ID)

    from data_viewer.plugins.compatibility import PluginInputCandidate, evaluate_plugin_compatibility

    decision = evaluate_plugin_compatibility(
        manifest,
        (
            PluginInputCandidate(
                metadata=document.get_metadata(fake.resource_id, cancellation=CancellationToken())
            ),
        ),
        memory_budget_bytes=1024,
    )

    assert not decision.enabled
    assert decision.reasons == ("dtype family string is not supported; expected boolean, integer, floating, complex",)


@pytest.mark.parametrize("values", [np.array([], dtype=np.float64), np.array([np.nan], dtype=np.float64)])
def test_dataset_profile_edge_inputs_have_deterministic_payload(values: np.ndarray) -> None:
    """Empty and all-missing numeric arrays return explicit null extrema instead of crashing."""

    document, fake = _document(values)
    registry = discover_builtin_plugins()
    manifest = registry.manifest_for(PLUGIN_ID)
    plugin_class = registry.load_plugin_class(PLUGIN_ID)

    assert_single_input_plugin_conforms(
        manifest=manifest,
        plugin=plugin_class(),
        document=document,
        resource_id=fake.resource_id,
        expected_payload=expected_profile_payload(values),
    )
