"""DV-0701 contracts for Plugin API v1 manifests and built-in registry."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from data_viewer.plugins.api import PLUGIN_API_VERSION, DataViewerPlugin, ResultKind
from data_viewer.plugins.manifests import (
    PluginManifest,
    PluginManifestError,
    load_plugin_manifest,
    validate_plugin_manifest,
)
from data_viewer.plugins.registry import BuiltinPluginRegistry, discover_builtin_plugins


def _valid_manifest(**overrides: object) -> dict[str, object]:
    manifest: dict[str, object] = {
        "schema_version": 1,
        "api_version": 1,
        "id": "org.dataviewer.dataset_profile",
        "name": "Dataset Profile",
        "version": "1.0.0",
        "description": "Summarizes shape and dtype.",
        "entry_point": "data_viewer.plugins.builtin.dataset_profile.plugin:DatasetProfilePlugin",
        "kind": "analysis",
        "input": {
            "domains": ["array", "table"],
            "min_ndim": 1,
            "max_ndim": None,
            "dtype_families": ["boolean", "integer", "floating", "complex"],
            "requires_random_access": False,
            "supports_chunked_input": True,
            "supports_selection": True,
        },
        "parameters_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "result_kinds": ["summary", "table"],
    }
    manifest.update(overrides)
    return manifest


def _write_manifest(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_plugin_public_api_version_and_result_kinds_are_stable() -> None:
    """The public plugin API exposes version 1 and typed result kinds."""

    assert PLUGIN_API_VERSION == 1
    assert ResultKind.SUMMARY.value == "summary"
    assert ResultKind.PLOT.value == "plot"
    assert hasattr(DataViewerPlugin, "run")


def test_valid_manifest_is_typed_without_importing_plugin_code() -> None:
    """Manifest validation returns typed metadata and does not import entry points."""

    manifest = validate_plugin_manifest(_valid_manifest())

    assert isinstance(manifest, PluginManifest)
    assert manifest.id == "org.dataviewer.dataset_profile"
    assert manifest.api_version == PLUGIN_API_VERSION
    assert manifest.input.domains == ("array", "table")
    assert manifest.result_kinds == (ResultKind.SUMMARY, ResultKind.TABLE)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", 2, "schema_version"),
        ("api_version", 2, "api_version"),
        ("id", "dataset profile", "id"),
        ("version", "1", "version"),
        ("entry_point", "plugins.builtin.statistics:Plugin", "entry_point"),
        ("kind", "external", "kind"),
        ("result_kinds", ["summary", "unknown"], "result_kinds"),
    ],
)
def test_manifest_validation_rejects_invalid_public_fields(
    field: str,
    value: object,
    message: str,
) -> None:
    """Invalid or unsupported manifest fields fail before plugin import."""

    data = _valid_manifest(**{field: value})
    with pytest.raises(PluginManifestError, match=message):
        validate_plugin_manifest(data)


def test_manifest_validation_rejects_unknown_keys() -> None:
    """Unknown keys are rejected in v1 to catch misspellings."""

    data = _valid_manifest()
    data["permission_request"] = "filesystem"

    with pytest.raises(PluginManifestError, match="unknown"):
        validate_plugin_manifest(data)


def test_load_plugin_manifest_reports_invalid_json_boundary(tmp_path: Path) -> None:
    """Manifest files are parsed and validated at the registry boundary."""

    path = tmp_path / "plugin.json"
    path.write_text('{"schema_version": 1, "api_version": 1', encoding="utf-8")

    with pytest.raises(PluginManifestError, match="JSON"):
        load_plugin_manifest(path)


def test_builtin_registry_keeps_bad_plugins_as_diagnostics_without_failing_startup(tmp_path: Path) -> None:
    """Bad built-in manifests are diagnostics; startup discovery still succeeds."""

    good = tmp_path / "good.plugin.json"
    _write_manifest(good, _valid_manifest(id="org.dataviewer.good", name="Good Plugin"))
    bad = tmp_path / "bad.plugin.json"
    _write_manifest(bad, _valid_manifest(api_version=99, id="org.dataviewer.bad"))

    registry = discover_builtin_plugins((good, bad))

    assert [plugin.id for plugin in registry.available_plugins()] == ["org.dataviewer.good"]
    assert [diagnostic.code for diagnostic in registry.diagnostics()] == ["PLUGIN_MANIFEST_INVALID"]
    assert "api_version" in registry.diagnostics()[0].message


def test_builtin_registry_rejects_duplicate_ids_but_keeps_unique_plugins(tmp_path: Path) -> None:
    """Duplicate IDs are deterministic diagnostics and do not hide unrelated plugins."""

    first = tmp_path / "first.plugin.json"
    _write_manifest(first, _valid_manifest(id="org.dataviewer.duplicate", name="A"))
    duplicate = tmp_path / "duplicate.plugin.json"
    _write_manifest(duplicate, _valid_manifest(id="org.dataviewer.duplicate", name="B"))
    other = tmp_path / "other.plugin.json"
    _write_manifest(other, _valid_manifest(id="org.dataviewer.other", name="Other"))

    registry = discover_builtin_plugins((first, duplicate, other))

    assert [plugin.id for plugin in registry.available_plugins()] == [
        "org.dataviewer.duplicate",
        "org.dataviewer.other",
    ]
    assert [diagnostic.code for diagnostic in registry.diagnostics()] == ["PLUGIN_ID_DUPLICATE"]


def test_builtin_registry_order_is_deterministic_by_kind_then_name(tmp_path: Path) -> None:
    """Plugin order is stable independent of manifest path order."""

    zeta = tmp_path / "zeta.plugin.json"
    _write_manifest(
        zeta,
        _valid_manifest(id="org.dataviewer.zeta", name="Zeta", kind="visualization"),
    )
    alpha = tmp_path / "alpha.plugin.json"
    _write_manifest(alpha, _valid_manifest(id="org.dataviewer.alpha", name="Alpha", kind="analysis"))
    beta = tmp_path / "beta.plugin.json"
    _write_manifest(beta, _valid_manifest(id="org.dataviewer.beta", name="Beta", kind="analysis"))

    registry = discover_builtin_plugins((zeta, beta, alpha))

    assert [plugin.id for plugin in registry.available_plugins()] == [
        "org.dataviewer.alpha",
        "org.dataviewer.beta",
        "org.dataviewer.zeta",
    ]


def test_registry_imports_entry_point_lazily(monkeypatch: pytest.MonkeyPatch) -> None:
    """Entry points are imported only when a caller explicitly loads the plugin."""

    imported: list[str] = []

    class DatasetProfilePlugin:
        pass

    def fake_import_module(name: str) -> object:
        imported.append(name)
        return SimpleNamespace(DatasetProfilePlugin=DatasetProfilePlugin)

    manifest = validate_plugin_manifest(_valid_manifest())
    registry = BuiltinPluginRegistry.from_manifests((manifest,))
    monkeypatch.setattr("data_viewer.plugins.registry.import_module", fake_import_module)

    assert imported == []
    plugin_class = registry.load_plugin_class("org.dataviewer.dataset_profile")

    assert plugin_class is DatasetProfilePlugin
    assert imported == ["data_viewer.plugins.builtin.dataset_profile.plugin"]


def test_registry_load_failure_is_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lazy import failures return structured diagnostics instead of raw import errors."""

    def fake_import_module(_name: str) -> object:
        raise RuntimeError("boom")

    registry = BuiltinPluginRegistry.from_manifests((validate_plugin_manifest(_valid_manifest()),))
    monkeypatch.setattr("data_viewer.plugins.registry.import_module", fake_import_module)

    with pytest.raises(LookupError, match="Could not load plugin"):
        registry.load_plugin_class("org.dataviewer.dataset_profile")
    assert registry.diagnostics()[-1].code == "PLUGIN_IMPORT_FAILED"
