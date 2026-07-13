"""Structured Data Viewer errors shared across adapters and application code."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from .metadata import FrozenJsonMapping, JsonValue
from .resources import ResourceId


class ErrorCategory(StrEnum):
    """Subsystem category for stable errors."""

    SOURCE = "source"
    RESOURCE = "resource"
    SELECTION = "selection"
    BUDGET = "budget"
    READ = "read"
    CAPABILITY = "capability"
    PLUGIN = "plugin"
    TASK = "task"
    WORKSPACE = "workspace"
    EDITING = "editing"
    CONFIG = "config"
    INTERNAL = "internal"


class ErrorSeverity(StrEnum):
    """User-facing severity for routing and diagnostics."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorTargetKind(StrEnum):
    """Stable target kind for an error."""

    APPLICATION = "application"
    SOURCE = "source"
    RESOURCE = "resource"
    SELECTION = "selection"
    PLUGIN = "plugin"
    TASK = "task"
    WORKSPACE = "workspace"
    CONFIG = "config"


class ErrorCode(StrEnum):
    """Stable Data Viewer error codes."""

    SOURCE_UNSUPPORTED = "SOURCE_UNSUPPORTED"
    SOURCE_AMBIGUOUS = "SOURCE_AMBIGUOUS"
    SOURCE_MALFORMED = "SOURCE_MALFORMED"
    SOURCE_ENCRYPTED = "SOURCE_ENCRYPTED"
    SOURCE_OPEN_FAILED = "SOURCE_OPEN_FAILED"
    SOURCE_CLOSED = "SOURCE_CLOSED"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    SELECTION_INVALID = "SELECTION_INVALID"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    READ_CANCELLED = "READ_CANCELLED"
    READ_FAILED = "READ_FAILED"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    PLUGIN_UNAVAILABLE = "PLUGIN_UNAVAILABLE"
    PLUGIN_INVALID = "PLUGIN_INVALID"
    PLUGIN_FAILED = "PLUGIN_FAILED"
    TASK_CANCELLED = "TASK_CANCELLED"
    TASK_FAILED = "TASK_FAILED"
    WORKSPACE_INVALID = "WORKSPACE_INVALID"
    WORKSPACE_UNSUPPORTED = "WORKSPACE_UNSUPPORTED"
    WORKSPACE_IO_FAILED = "WORKSPACE_IO_FAILED"
    EDIT_CONFLICT = "EDIT_CONFLICT"
    EDIT_VALIDATION_FAILED = "EDIT_VALIDATION_FAILED"
    CONFIG_INVALID = "CONFIG_INVALID"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True, slots=True)
class ErrorCodeSpec:
    """Default semantics for an error code."""

    category: ErrorCategory
    severity: ErrorSeverity
    retryable: bool


ERROR_CODE_SPECS: dict[ErrorCode, ErrorCodeSpec] = {
    ErrorCode.SOURCE_UNSUPPORTED: ErrorCodeSpec(
        ErrorCategory.SOURCE, ErrorSeverity.ERROR, False
    ),
    ErrorCode.SOURCE_AMBIGUOUS: ErrorCodeSpec(
        ErrorCategory.SOURCE, ErrorSeverity.ERROR, False
    ),
    ErrorCode.SOURCE_MALFORMED: ErrorCodeSpec(
        ErrorCategory.SOURCE, ErrorSeverity.ERROR, False
    ),
    ErrorCode.SOURCE_ENCRYPTED: ErrorCodeSpec(
        ErrorCategory.SOURCE, ErrorSeverity.ERROR, False
    ),
    ErrorCode.SOURCE_OPEN_FAILED: ErrorCodeSpec(
        ErrorCategory.SOURCE, ErrorSeverity.ERROR, True
    ),
    ErrorCode.SOURCE_CLOSED: ErrorCodeSpec(
        ErrorCategory.SOURCE, ErrorSeverity.ERROR, False
    ),
    ErrorCode.SOURCE_CHANGED: ErrorCodeSpec(
        ErrorCategory.SOURCE, ErrorSeverity.WARNING, True
    ),
    ErrorCode.RESOURCE_NOT_FOUND: ErrorCodeSpec(
        ErrorCategory.RESOURCE, ErrorSeverity.WARNING, True
    ),
    ErrorCode.SELECTION_INVALID: ErrorCodeSpec(
        ErrorCategory.SELECTION, ErrorSeverity.ERROR, False
    ),
    ErrorCode.BUDGET_EXCEEDED: ErrorCodeSpec(
        ErrorCategory.BUDGET, ErrorSeverity.WARNING, True
    ),
    ErrorCode.READ_CANCELLED: ErrorCodeSpec(
        ErrorCategory.READ, ErrorSeverity.INFO, True
    ),
    ErrorCode.READ_FAILED: ErrorCodeSpec(
        ErrorCategory.READ, ErrorSeverity.ERROR, True
    ),
    ErrorCode.CAPABILITY_UNAVAILABLE: ErrorCodeSpec(
        ErrorCategory.CAPABILITY, ErrorSeverity.ERROR, False
    ),
    ErrorCode.PLUGIN_UNAVAILABLE: ErrorCodeSpec(
        ErrorCategory.PLUGIN, ErrorSeverity.WARNING, False
    ),
    ErrorCode.PLUGIN_INVALID: ErrorCodeSpec(
        ErrorCategory.PLUGIN, ErrorSeverity.ERROR, False
    ),
    ErrorCode.PLUGIN_FAILED: ErrorCodeSpec(
        ErrorCategory.PLUGIN, ErrorSeverity.ERROR, False
    ),
    ErrorCode.TASK_CANCELLED: ErrorCodeSpec(
        ErrorCategory.TASK, ErrorSeverity.INFO, True
    ),
    ErrorCode.TASK_FAILED: ErrorCodeSpec(
        ErrorCategory.TASK, ErrorSeverity.ERROR, True
    ),
    ErrorCode.WORKSPACE_INVALID: ErrorCodeSpec(
        ErrorCategory.WORKSPACE, ErrorSeverity.ERROR, False
    ),
    ErrorCode.WORKSPACE_UNSUPPORTED: ErrorCodeSpec(
        ErrorCategory.WORKSPACE, ErrorSeverity.ERROR, False
    ),
    ErrorCode.WORKSPACE_IO_FAILED: ErrorCodeSpec(
        ErrorCategory.WORKSPACE, ErrorSeverity.ERROR, True
    ),
    ErrorCode.EDIT_CONFLICT: ErrorCodeSpec(
        ErrorCategory.EDITING, ErrorSeverity.WARNING, True
    ),
    ErrorCode.EDIT_VALIDATION_FAILED: ErrorCodeSpec(
        ErrorCategory.EDITING, ErrorSeverity.ERROR, False
    ),
    ErrorCode.CONFIG_INVALID: ErrorCodeSpec(
        ErrorCategory.CONFIG, ErrorSeverity.WARNING, False
    ),
    ErrorCode.INTERNAL_ERROR: ErrorCodeSpec(
        ErrorCategory.INTERNAL, ErrorSeverity.CRITICAL, False
    ),
}


@dataclass(frozen=True, slots=True)
class ErrorTarget:
    """Structured target for an error."""

    kind: ErrorTargetKind
    identifier: JsonValue

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", ErrorTargetKind(self.kind))
        FrozenJsonMapping({"identifier": self.identifier})

    def to_json(self) -> dict[str, JsonValue]:
        return {"kind": self.kind.value, "identifier": self.identifier}

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "ErrorTarget":
        return cls(
            kind=ErrorTargetKind(str(value["kind"])),
            identifier=value["identifier"],
        )


@dataclass(frozen=True, slots=True)
class UserErrorMessage:
    """Safe user-facing error message without traceback or raw cause text."""

    code: ErrorCode
    severity: ErrorSeverity
    message: str
    remediation: str | None

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
            "remediation": self.remediation,
        }


class DataViewerError(Exception):
    """Structured exception that separates safe UI text from diagnostic cause."""

    code: ErrorCode
    message: str
    operation: str
    category: ErrorCategory
    severity: ErrorSeverity
    resource_id: ResourceId | None
    target: ErrorTarget | None
    retryable: bool
    remediation: str | None
    details: FrozenJsonMapping
    cause_id: str | None
    cause: BaseException | None

    def __init__(
        self,
        *,
        code: ErrorCode,
        message: str,
        operation: str,
        category: ErrorCategory | None = None,
        severity: ErrorSeverity | None = None,
        resource_id: ResourceId | None = None,
        target: ErrorTarget | None = None,
        retryable: bool | None = None,
        remediation: str | None = None,
        details: Mapping[str, JsonValue] | None = None,
        cause_id: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        self.code = ErrorCode(code)
        spec = ERROR_CODE_SPECS[self.code]
        self.message = _expect_non_empty(message, "error message")
        self.operation = _expect_non_empty(operation, "error operation")
        self.category = ErrorCategory(category) if category is not None else spec.category
        self.severity = ErrorSeverity(severity) if severity is not None else spec.severity
        self.resource_id = resource_id
        self.target = target if target is not None else _default_target(resource_id)
        self.retryable = spec.retryable if retryable is None else _expect_bool(
            retryable, "retryable"
        )
        self.remediation = remediation
        self.details = FrozenJsonMapping(details or {})
        self.cause_id = cause_id
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"

    def to_user_message(self) -> UserErrorMessage:
        return UserErrorMessage(
            code=self.code,
            severity=self.severity,
            message=self.message,
            remediation=self.remediation,
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "code": self.code.value,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "operation": self.operation,
            "resource_id": self.resource_id.to_json()
            if self.resource_id is not None
            else None,
            "target": self.target.to_json() if self.target is not None else None,
            "retryable": self.retryable,
            "remediation": self.remediation,
            "details": self.details.to_json(),
            "cause_id": self.cause_id,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "DataViewerError":
        resource_value = value.get("resource_id")
        target_value = value.get("target")
        return cls(
            code=ErrorCode(str(value["code"])),
            category=ErrorCategory(str(value["category"])),
            severity=ErrorSeverity(str(value["severity"])),
            message=str(value["message"]),
            operation=str(value["operation"]),
            resource_id=ResourceId.from_json(
                _expect_mapping(resource_value, "resource_id")
            )
            if isinstance(resource_value, dict)
            else None,
            target=ErrorTarget.from_json(_expect_mapping(target_value, "target"))
            if isinstance(target_value, dict)
            else None,
            retryable=_expect_bool(value["retryable"], "retryable"),
            remediation=str(value["remediation"])
            if value.get("remediation") is not None
            else None,
            details=_expect_mapping(value.get("details", {}), "details"),
            cause_id=str(value["cause_id"])
            if value.get("cause_id") is not None
            else None,
        )

    def to_log_record(self) -> dict[str, JsonValue]:
        record = self.to_json()
        if self.cause is not None:
            record["cause_type"] = type(self.cause).__name__
            record["cause_message"] = str(self.cause)
        return record


def _default_target(resource_id: ResourceId | None) -> ErrorTarget | None:
    if resource_id is None:
        return None
    return ErrorTarget(ErrorTargetKind.RESOURCE, resource_id.to_json())


def _expect_non_empty(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _expect_bool(value: JsonValue, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean value")
    return value


def _expect_mapping(value: JsonValue, label: str) -> Mapping[str, JsonValue]:
    if isinstance(value, dict):
        return value
    raise ValueError(f"{label} must be a JSON object")
