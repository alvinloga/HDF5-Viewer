"""Export receipt values with provenance and outcome evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Mapping

from data_viewer.domain import ErrorCode, JsonValue, ResourceId, SourceFingerprint

from .plan import ExportPlan, ExportScope, ExportTargetFormat, ExportValueMode


class ExportOutcome(StrEnum):
    """Terminal export outcome."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ExportReceipt:
    """Receipt recording what an export attempted and what happened."""

    source_fingerprint: SourceFingerprint
    target_path: Path
    target_format: ExportTargetFormat
    scope: ExportScope
    value_mode: ExportValueMode
    outcome: ExportOutcome
    application_version: str
    created_at_utc: str
    resource_id: ResourceId | None = None
    selection: Mapping[str, JsonValue] | None = None
    parameters: Mapping[str, JsonValue] | None = None
    warnings: tuple[str, ...] = ()
    bytes_written: int = 0
    error_code: ErrorCode | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_path", Path(self.target_path))
        object.__setattr__(self, "target_format", ExportTargetFormat(self.target_format))
        object.__setattr__(self, "scope", ExportScope(self.scope))
        object.__setattr__(self, "value_mode", ExportValueMode(self.value_mode))
        object.__setattr__(self, "outcome", ExportOutcome(self.outcome))
        object.__setattr__(self, "parameters", dict(self.parameters or {}))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        if self.bytes_written < 0:
            raise ValueError("bytes_written must be non-negative")
        if self.outcome is ExportOutcome.SUCCEEDED and self.error_code is not None:
            raise ValueError("successful export receipt cannot include an error code")

    @property
    def succeeded(self) -> bool:
        return self.outcome is ExportOutcome.SUCCEEDED

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "source_fingerprint": self.source_fingerprint.to_json(),
            "resource_id": self.resource_id.to_json() if self.resource_id else None,
            "selection": dict(self.selection) if self.selection else None,
            "parameters": dict(self.parameters or {}),
            "target_path": str(self.target_path),
            "target_format": self.target_format.value,
            "scope": self.scope.value,
            "value_mode": self.value_mode.value,
            "outcome": self.outcome.value,
            "application_version": self.application_version,
            "created_at_utc": self.created_at_utc,
            "warnings": list(self.warnings),
            "bytes_written": self.bytes_written,
            "error_code": self.error_code.value if self.error_code else None,
            "error_message": self.error_message,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "ExportReceipt":
        resource = value.get("resource_id")
        fingerprint = value["source_fingerprint"]
        error_code = value.get("error_code")
        warnings = value.get("warnings", [])
        return cls(
            source_fingerprint=SourceFingerprint.from_json(_expect_mapping(fingerprint)),
            resource_id=ResourceId.from_json(_expect_mapping(resource))
            if isinstance(resource, dict)
            else None,
            selection=_expect_mapping(value["selection"])
            if isinstance(value.get("selection"), dict)
            else None,
            parameters=_expect_mapping(value.get("parameters", {})),
            target_path=Path(str(value["target_path"])),
            target_format=ExportTargetFormat(str(value["target_format"])),
            scope=ExportScope(str(value["scope"])),
            value_mode=ExportValueMode(str(value["value_mode"])),
            outcome=ExportOutcome(str(value["outcome"])),
            application_version=str(value["application_version"]),
            created_at_utc=str(value["created_at_utc"]),
            warnings=tuple(str(item) for item in _expect_list(warnings)),
            bytes_written=_expect_int(value.get("bytes_written", 0)),
            error_code=ErrorCode(str(error_code)) if error_code is not None else None,
            error_message=str(value["error_message"])
            if value.get("error_message") is not None
            else None,
        )


def receipt_from_plan(
    plan: ExportPlan,
    *,
    outcome: ExportOutcome,
    application_version: str,
    bytes_written: int = 0,
    error_code: ErrorCode | None = None,
    error_message: str | None = None,
) -> ExportReceipt:
    """Create a receipt that mirrors the reviewed export plan."""

    selection: Mapping[str, JsonValue] | None = None
    if plan.selection is not None:
        selection = plan.selection.to_json()
    elif plan.table_page is not None:
        selection = plan.table_page.to_json()
    return ExportReceipt(
        source_fingerprint=plan.source_fingerprint,
        resource_id=plan.resource_id,
        selection=selection,
        parameters=plan.parameters,
        target_path=plan.target_path,
        target_format=plan.target_format,
        scope=plan.scope,
        value_mode=plan.value_mode,
        outcome=outcome,
        application_version=application_version,
        created_at_utc=_utc_now(),
        warnings=plan.warnings,
        bytes_written=bytes_written,
        error_code=error_code,
        error_message=error_message,
    )


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _expect_mapping(value: JsonValue) -> Mapping[str, JsonValue]:
    if isinstance(value, dict):
        return value
    raise ValueError("expected a JSON object")


def _expect_list(value: JsonValue) -> list[JsonValue]:
    if isinstance(value, list):
        return value
    raise ValueError("expected a JSON array")


def _expect_int(value: JsonValue) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected an integer JSON value")
    return value


__all__ = [
    "ExportOutcome",
    "ExportReceipt",
    "receipt_from_plan",
]
