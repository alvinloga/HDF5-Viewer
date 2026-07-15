"""Plugin compatibility evaluation for selected Data Viewer resources."""

from __future__ import annotations

from dataclasses import dataclass

from data_viewer.domain import DataDomain, DataMetadata, SourceCapability
from data_viewer.plugins.manifests import PluginManifest


@dataclass(frozen=True, slots=True)
class PluginInputCandidate:
    """One selected resource candidate for plugin compatibility checks."""

    metadata: DataMetadata
    has_selection: bool = False


@dataclass(frozen=True, slots=True)
class CompatibilityDecision:
    """Compatibility decision surfaced before enabling plugin Run."""

    enabled: bool
    reasons: tuple[str, ...] = ()


def evaluate_plugin_compatibility(
    manifest: PluginManifest,
    inputs: tuple[PluginInputCandidate, ...],
    *,
    memory_budget_bytes: int,
    available_dependencies: frozenset[str] = frozenset(),
) -> CompatibilityDecision:
    """Evaluate whether a plugin can run against the selected inputs."""

    reasons: list[str] = []
    for dependency in manifest.required_dependencies:
        if dependency not in available_dependencies:
            reasons.append(f"required dependency {dependency} is unavailable")

    if len(inputs) != 1:
        reasons.append(f"plugin expects exactly 1 input; received {len(inputs)}")
        return CompatibilityDecision(enabled=False, reasons=tuple(reasons))

    candidate = inputs[0]
    metadata = candidate.metadata
    input_spec = manifest.input

    domain = DataDomain(metadata.domain).value
    if domain not in input_spec.domains:
        reasons.append(
            f"domain {domain} is not supported; expected {', '.join(input_spec.domains)}"
        )

    ndim = len(metadata.shape)
    if input_spec.min_ndim is not None and ndim < input_spec.min_ndim:
        reasons.append(f"ndim {ndim} is below minimum {input_spec.min_ndim}")
    if input_spec.max_ndim is not None and ndim > input_spec.max_ndim:
        reasons.append(f"ndim {ndim} is above maximum {input_spec.max_ndim}")

    dtype_family = dtype_family_for(metadata.dtype)
    if dtype_family not in input_spec.dtype_families:
        reasons.append(
            f"dtype family {dtype_family} is not supported; expected {', '.join(input_spec.dtype_families)}"
        )

    if input_spec.requires_random_access and SourceCapability.RANDOM_SLICE not in metadata.capabilities:
        reasons.append("random access is required but the resource does not provide RANDOM_SLICE")

    if candidate.has_selection and not input_spec.supports_selection:
        reasons.append("current selection is not supported by this plugin")

    estimated_size = metadata.logical_size_bytes
    if (
        estimated_size is not None
        and estimated_size > memory_budget_bytes
        and not input_spec.supports_chunked_input
    ):
        reasons.append(
            f"estimated size {estimated_size} bytes exceeds budget {memory_budget_bytes} bytes and plugin is not chunked"
        )

    return CompatibilityDecision(enabled=not reasons, reasons=tuple(reasons))


def dtype_family_for(dtype: str | None) -> str:
    """Map a dtype string to the manifest dtype family vocabulary."""

    text = (dtype or "").lower()
    if text in {"bool", "boolean", "bool_"} or text.startswith("bool"):
        return "boolean"
    if text.startswith(("int", "uint")) or text in {"integer"}:
        return "integer"
    if text.startswith(("float", "double")) or text in {"floating", "number"}:
        return "floating"
    if text.startswith("complex"):
        return "complex"
    if text.startswith(("str", "string", "<u", "|s", "bytes", "object")):
        return "string"
    return text or "unknown"


__all__ = [
    "CompatibilityDecision",
    "PluginInputCandidate",
    "dtype_family_for",
    "evaluate_plugin_compatibility",
]
