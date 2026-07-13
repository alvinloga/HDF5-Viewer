"""Domain and capability values shared by adapters, plugins, and UI models."""

from __future__ import annotations

from enum import IntFlag, StrEnum, auto
from typing import Iterable


class DataDomain(StrEnum):
    """High-level resource domains understood by Data Viewer v1."""

    HIERARCHICAL_ARRAY = "hierarchical_array"
    ARRAY = "array"
    TABLE = "table"
    TEXT = "text"
    STRUCTURED = "structured"
    WORKBOOK = "workbook"
    VOLUME = "volume"
    METADATA = "metadata"


class NodeKind(StrEnum):
    """The role a node plays in a source hierarchy."""

    ROOT = "root"
    CONTAINER = "container"
    RESOURCE = "resource"
    METADATA = "metadata"


class SourceCapability(IntFlag):
    """Adapter-declared operations available for a resource or source."""

    NONE = 0
    HIERARCHY = auto()
    RANDOM_SLICE = auto()
    PAGED_ROWS = auto()
    STREAMING_READ = auto()
    SEARCH = auto()
    EDIT_PATCH = auto()
    ATOMIC_REWRITE = auto()
    SAVE_AS = auto()
    SPATIAL_METADATA = auto()
    COLUMN_SCHEMA = auto()


def capabilities_to_names(capabilities: SourceCapability) -> tuple[str, ...]:
    """Serialize capability flags as stable enum names."""
    names: list[str] = []
    for capability in SourceCapability:
        if capability is SourceCapability.NONE or capability not in capabilities:
            continue
        if capability.name is None:
            raise ValueError(f"unnamed source capability: {capability}")
        names.append(capability.name)
    return tuple(names)


def capabilities_from_names(names: Iterable[str]) -> SourceCapability:
    """Deserialize capability names into a flag set."""
    capabilities = SourceCapability.NONE
    for name in names:
        try:
            capabilities |= SourceCapability[name]
        except KeyError as exc:
            raise ValueError(f"unknown source capability: {name}") from exc
    return capabilities
