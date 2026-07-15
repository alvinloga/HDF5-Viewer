"""DV-0702 compatibility evaluator and parameter form contracts."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QSpinBox

from data_viewer.domain import DataDomain, DataMetadata, NodeKind, ResourceId, SourceCapability
from data_viewer.gui.plugin_forms import ParameterFormWidget
from data_viewer.plugins.compatibility import (
    CompatibilityDecision,
    PluginInputCandidate,
    evaluate_plugin_compatibility,
)
from data_viewer.plugins.manifests import PluginManifest, validate_plugin_manifest
from data_viewer.plugins.parameters import (
    ParameterValidationError,
    default_parameters,
    validate_parameter_schema,
    validate_parameters,
)


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(["data-viewer-plugin-form-test"])
    return app


def _manifest(**overrides: object) -> PluginManifest:
    data: dict[str, object] = {
        "schema_version": 1,
        "api_version": 1,
        "id": "org.dataviewer.profile",
        "name": "Dataset Profile",
        "version": "1.0.0",
        "description": "Profiles arrays.",
        "entry_point": "data_viewer.plugins.builtin.profile.plugin:ProfilePlugin",
        "kind": "analysis",
        "input": {
            "domains": ["array"],
            "min_ndim": 1,
            "max_ndim": 3,
            "dtype_families": ["integer", "floating"],
            "requires_random_access": True,
            "supports_chunked_input": False,
            "supports_selection": True,
        },
        "parameters_schema": {
            "type": "object",
            "properties": {
                "nan_policy": {
                    "type": "string",
                    "enum": ["omit", "propagate"],
                    "default": "omit",
                    "title": "NaN policy",
                },
                "bins": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 512,
                    "default": 32,
                },
                "include_missing": {
                    "type": "boolean",
                    "default": False,
                },
            },
            "additionalProperties": False,
        },
        "result_kinds": ["summary"],
    }
    data.update(overrides)
    return validate_plugin_manifest(data)


def _metadata(
    *,
    domain: DataDomain = DataDomain.ARRAY,
    shape: tuple[int, ...] = (8, 4),
    dtype: str = "float64",
    capabilities: SourceCapability = SourceCapability.RANDOM_SLICE,
    logical_size_bytes: int | None = 256,
) -> DataMetadata:
    return DataMetadata(
        resource_id=ResourceId("file:///tmp/source.npy", "/array"),
        name="array",
        domain=domain,
        node_kind=NodeKind.RESOURCE,
        shape=shape,
        dtype=dtype,
        capabilities=capabilities,
        logical_size_bytes=logical_size_bytes,
    )


def test_compatibility_enabled_for_matching_resource() -> None:
    """Compatible plugins are enabled with no disabled reasons."""

    decision = evaluate_plugin_compatibility(
        _manifest(),
        (PluginInputCandidate(metadata=_metadata(), has_selection=True),),
        memory_budget_bytes=1024,
    )

    assert decision == CompatibilityDecision(enabled=True, reasons=())


def test_compatibility_reports_exact_disabled_reasons() -> None:
    """Every incompatible dimension of the selected resource is visible."""

    decision = evaluate_plugin_compatibility(
        _manifest(),
        (
            PluginInputCandidate(
                metadata=_metadata(
                    domain=DataDomain.TABLE,
                    shape=(2, 3, 4, 5),
                    dtype="str",
                    capabilities=SourceCapability.PAGED_ROWS,
                    logical_size_bytes=4096,
                ),
                has_selection=True,
            ),
        ),
        memory_budget_bytes=128,
    )

    assert not decision.enabled
    assert decision.reasons == (
        "domain table is not supported; expected array",
        "ndim 4 is above maximum 3",
        "dtype family string is not supported; expected integer, floating",
        "random access is required but the resource does not provide RANDOM_SLICE",
        "estimated size 4096 bytes exceeds budget 128 bytes and plugin is not chunked",
    )


def test_compatibility_rejects_selection_when_plugin_declines_selection() -> None:
    """Selection requirements are checked before Run is enabled."""

    manifest = _manifest(
        input={
            "domains": ["array"],
            "min_ndim": 1,
            "max_ndim": None,
            "dtype_families": ["floating"],
            "requires_random_access": False,
            "supports_chunked_input": True,
            "supports_selection": False,
        }
    )

    decision = evaluate_plugin_compatibility(
        manifest,
        (PluginInputCandidate(metadata=_metadata(), has_selection=True),),
        memory_budget_bytes=128,
    )

    assert not decision.enabled
    assert decision.reasons == ("current selection is not supported by this plugin",)


def test_compatibility_reports_multi_input_and_dependency_reasons() -> None:
    """Input count and required dependency availability reasons are exact."""

    multi_input_decision = evaluate_plugin_compatibility(
        _manifest(),
        (
            PluginInputCandidate(metadata=_metadata()),
            PluginInputCandidate(metadata=_metadata()),
        ),
        memory_budget_bytes=1024,
    )

    assert multi_input_decision.reasons == ("plugin expects exactly 1 input; received 2",)

    dependency_decision = evaluate_plugin_compatibility(
        _manifest(required_dependencies=["scipy", "nibabel"]),
        (PluginInputCandidate(metadata=_metadata()),),
        memory_budget_bytes=1024,
        available_dependencies=frozenset({"scipy"}),
    )

    assert not dependency_decision.enabled
    assert dependency_decision.reasons == ("required dependency nibabel is unavailable",)


def test_parameter_schema_defaults_and_validation_are_immutable() -> None:
    """Parameter defaults are JSON-safe, immutable, and reject unknown fields."""

    schema = validate_parameter_schema(_manifest().parameters_schema)
    defaults = default_parameters(schema)

    assert defaults == {"nan_policy": "omit", "bins": 32, "include_missing": False}
    with pytest.raises(TypeError):
        defaults["bins"] = 64  # type: ignore[index]

    values = validate_parameters(schema, {"nan_policy": "propagate", "bins": 64, "include_missing": True})
    assert values == {"nan_policy": "propagate", "bins": 64, "include_missing": True}

    with pytest.raises(ParameterValidationError, match="unknown"):
        validate_parameters(schema, {"nan_policy": "omit", "extra": True})
    with pytest.raises(ParameterValidationError, match="bins"):
        validate_parameters(schema, {"nan_policy": "omit", "bins": 0, "include_missing": False})


def test_parameter_form_renders_standard_widgets_and_round_trips_values() -> None:
    """The standard parameter renderer creates widgets; plugins create no dialogs."""

    app = _qapp()
    schema = validate_parameter_schema(_manifest().parameters_schema)
    widget = ParameterFormWidget(schema)
    app.processEvents()

    assert widget.findChildren(QDialog) == []
    combo = widget.findChild(QComboBox, "parameter_nan_policy")
    bins = widget.findChild(QSpinBox, "parameter_bins")
    include = widget.findChild(QCheckBox, "parameter_include_missing")
    assert combo is not None and bins is not None and include is not None
    assert combo.accessibleName() == "NaN policy"
    assert bins.focusPolicy().name == "StrongFocus"
    assert widget.values() == {"nan_policy": "omit", "bins": 32, "include_missing": False}

    combo.setCurrentText("propagate")
    bins.setValue(128)
    include.setChecked(True)

    assert widget.values() == {"nan_policy": "propagate", "bins": 128, "include_missing": True}
    assert widget.validate_current() == {"nan_policy": "propagate", "bins": 128, "include_missing": True}
