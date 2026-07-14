"""Public Plugin API v1 types.

This module is intentionally small for DV-0701. Later P7 tasks add budgeted
input access, parameter validation, runner integration, and typed result
validators without changing the public API version.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray


PLUGIN_API_VERSION = 1


class ResultKind(StrEnum):
    """Result categories supported by Plugin API v1."""

    SUMMARY = "summary"
    TABLE = "table"
    ARRAY = "array"
    IMAGE = "image"
    PLOT = "plot"
    COLLECTION = "collection"


@dataclass(frozen=True, slots=True)
class InputDescriptor:
    """Serializable description of one plugin input."""

    source_id: str
    source_fingerprint: Mapping[str, object]
    resource_path: str
    domain: str
    shape: tuple[int, ...] | None
    dtype: str | None
    selection: Mapping[str, object]
    estimated_elements: int | None
    estimated_bytes: int | None


@dataclass(frozen=True, slots=True)
class DataChunk:
    """One bounded plugin input chunk."""

    values: NDArray[np.generic]
    origin: tuple[int, ...]
    selection: Mapping[str, object]
    is_last: bool


@runtime_checkable
class InputAccess(Protocol):
    """Budgeted plugin access to one input resource."""

    descriptor: InputDescriptor

    def read(self, selection: Mapping[str, object]) -> NDArray[np.generic]:
        """Read a bounded explicit selection."""

    def iter_chunks(self, target_bytes: int) -> Iterator[DataChunk]:
        """Iterate bounded chunks sized by the runner budget."""


@dataclass(frozen=True, slots=True)
class PluginContext:
    """Immutable runtime context supplied by the plugin runner."""

    run_id: str
    inputs: tuple[InputAccess, ...]
    parameters: Mapping[str, object]
    memory_budget_bytes: int
    temp_budget_bytes: int
    is_cancelled: Callable[[], bool]
    report_progress: Callable[[float | None, str], None]
    emit_warning: Callable[[str, str], None]


@dataclass(frozen=True, slots=True)
class ResultProvenance:
    """Provenance every published plugin result must carry."""

    plugin_id: str
    plugin_version: str
    api_version: int
    inputs: tuple[InputDescriptor, ...]
    parameters: Mapping[str, object]
    computation_scope: str
    sampled: bool


@dataclass(frozen=True, slots=True)
class PluginResult:
    """Top-level result object returned by a plugin."""

    kind: ResultKind
    title: str
    payload: object
    provenance: ResultProvenance
    metadata: Mapping[str, object]
    warnings: tuple[str, ...] = ()


@runtime_checkable
class DataViewerPlugin(Protocol):
    """Protocol implemented by Plugin API v1 plugins."""

    def run(self, context: PluginContext) -> PluginResult:
        """Run the plugin and return exactly one final result."""


__all__ = [
    "PLUGIN_API_VERSION",
    "DataChunk",
    "DataViewerPlugin",
    "InputAccess",
    "InputDescriptor",
    "PluginContext",
    "PluginResult",
    "ResultKind",
    "ResultProvenance",
]
