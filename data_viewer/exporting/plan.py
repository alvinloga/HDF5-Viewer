"""Export planning values for explicit Data Viewer exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Mapping

from data_viewer.domain import (
    JsonValue,
    NormalizedSelection,
    NormalizedTablePage,
    ResourceId,
    SourceFingerprint,
)


class ExportScope(StrEnum):
    """Explicit source scope being exported."""

    FULL_RESOURCE = "full_resource"
    CURRENT_SLICE = "current_slice"
    CURRENT_SELECTION = "current_selection"
    FILTERED_ROWS = "filtered_rows"
    PLUGIN_RESULT = "plugin_result"
    RENDERED_VISUALIZATION = "rendered_visualization"


class ExportValueMode(StrEnum):
    """Semantic value representation used by an export."""

    RAW = "raw"
    DISPLAY = "display"
    SCALED = "scaled"


class ExportTargetFormat(StrEnum):
    """Target file format selected for an export."""

    NPY = "npy"
    CSV = "csv"
    JSON = "json"
    TXT = "txt"
    PNG = "png"
    BINARY = "binary"


@dataclass(frozen=True, slots=True)
class ExportPlan:
    """Reviewed export plan before bytes are written."""

    source_fingerprint: SourceFingerprint
    target_path: Path
    target_format: ExportTargetFormat
    scope: ExportScope
    value_mode: ExportValueMode
    resource_id: ResourceId | None = None
    selection: NormalizedSelection | None = None
    table_page: NormalizedTablePage | None = None
    parameters: Mapping[str, JsonValue] = field(default_factory=dict)
    overwrite: bool = False
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_format", ExportTargetFormat(self.target_format))
        object.__setattr__(self, "scope", ExportScope(self.scope))
        object.__setattr__(self, "value_mode", ExportValueMode(self.value_mode))
        object.__setattr__(self, "target_path", Path(self.target_path))
        object.__setattr__(self, "parameters", dict(self.parameters))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        if self.scope in {
            ExportScope.FULL_RESOURCE,
            ExportScope.CURRENT_SLICE,
            ExportScope.CURRENT_SELECTION,
            ExportScope.FILTERED_ROWS,
        } and self.resource_id is None:
            raise ValueError("resource exports require a resource_id")
        if self.scope in {ExportScope.CURRENT_SLICE, ExportScope.CURRENT_SELECTION}:
            if self.selection is None:
                raise ValueError("slice and selection exports require normalized selection")
        if self.scope is ExportScope.FILTERED_ROWS and self.table_page is None:
            raise ValueError("filtered row exports require a normalized table page")

    def to_json(self) -> dict[str, JsonValue]:
        """Serialize the plan for receipts, work queues, and diagnostics."""

        return {
            "source_fingerprint": self.source_fingerprint.to_json(),
            "resource_id": self.resource_id.to_json() if self.resource_id else None,
            "selection": self.selection.to_json() if self.selection else None,
            "table_page": self.table_page.to_json() if self.table_page else None,
            "target_path": str(self.target_path),
            "target_format": self.target_format.value,
            "scope": self.scope.value,
            "value_mode": self.value_mode.value,
            "parameters": dict(self.parameters),
            "overwrite": self.overwrite,
            "warnings": list(self.warnings),
        }


def build_export_plan(
    *,
    source_fingerprint: SourceFingerprint,
    target_path: Path,
    scope: ExportScope,
    value_mode: ExportValueMode,
    resource_id: ResourceId | None = None,
    selection: NormalizedSelection | None = None,
    table_page: NormalizedTablePage | None = None,
    target_format: ExportTargetFormat | None = None,
    parameters: Mapping[str, JsonValue] | None = None,
    overwrite: bool = False,
    warnings: tuple[str, ...] = (),
) -> ExportPlan:
    """Build a deterministic export plan with suffix-based defaults."""

    resolved_format = target_format or infer_export_format(target_path)
    plan_warnings = list(warnings)
    if resolved_format is ExportTargetFormat.CSV:
        plan_warnings.append("CSV export escapes spreadsheet formula-like text cells.")
    if value_mode is ExportValueMode.DISPLAY:
        plan_warnings.append("Display-mode export may contain formatted values.")
    if value_mode is ExportValueMode.SCALED:
        plan_warnings.append("Scaled export must preserve scaling provenance in the receipt.")
    return ExportPlan(
        source_fingerprint=source_fingerprint,
        resource_id=resource_id,
        selection=selection,
        table_page=table_page,
        target_path=target_path,
        target_format=resolved_format,
        scope=scope,
        value_mode=value_mode,
        parameters=parameters or {},
        overwrite=overwrite,
        warnings=tuple(dict.fromkeys(plan_warnings)),
    )


def infer_export_format(path: Path) -> ExportTargetFormat:
    """Infer an export target format from a file suffix."""

    suffix = path.suffix.lower()
    if suffix == ".npy":
        return ExportTargetFormat.NPY
    if suffix == ".csv":
        return ExportTargetFormat.CSV
    if suffix == ".json":
        return ExportTargetFormat.JSON
    if suffix == ".txt":
        return ExportTargetFormat.TXT
    if suffix == ".png":
        return ExportTargetFormat.PNG
    return ExportTargetFormat.BINARY


__all__ = [
    "ExportPlan",
    "ExportScope",
    "ExportTargetFormat",
    "ExportValueMode",
    "build_export_plan",
    "infer_export_format",
]
