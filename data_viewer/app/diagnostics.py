"""Safe diagnostics values and redaction helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from data_viewer.domain.errors import DataViewerError
from data_viewer.domain.metadata import FrozenJsonMapping, JsonValue


@dataclass(frozen=True, slots=True)
class DiagnosticsRedactor:
    """Redact configured path prefixes from diagnostic JSON values."""

    sensitive_roots: tuple[str, ...] = ()

    def __init__(self, sensitive_roots: Iterable[str] = ()) -> None:
        object.__setattr__(
            self,
            "sensitive_roots",
            tuple(
                normalized
                for root in sensitive_roots
                if (normalized := _normalize_path_text(root))
            ),
        )

    def redact_text(self, value: str) -> str:
        redacted = _normalize_path_text(value)
        for root in self.sensitive_roots:
            if redacted == root:
                redacted = "<redacted>"
            elif redacted.startswith(f"{root}/"):
                redacted = f"<redacted>{redacted[len(root):]}"
        return redacted

    def redact_json(self, value: JsonValue) -> JsonValue:
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, list):
            return [self.redact_json(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): self.redact_json(item)
                for key, item in sorted(value.items())
            }
        return value


@dataclass(frozen=True, slots=True)
class DiagnosticEvent:
    """A safe diagnostic event suitable for Problems/diagnostics export."""

    timestamp_utc: str
    error: Mapping[str, JsonValue]
    context: Mapping[str, JsonValue] = field(default_factory=FrozenJsonMapping)

    def __post_init__(self) -> None:
        if not self.timestamp_utc:
            raise ValueError("diagnostic event timestamp must not be empty")
        object.__setattr__(self, "error", FrozenJsonMapping(self.error))
        object.__setattr__(self, "context", FrozenJsonMapping(self.context))

    @classmethod
    def from_error(
        cls,
        error: DataViewerError,
        *,
        redactor: DiagnosticsRedactor | None = None,
        context: Mapping[str, JsonValue] | None = None,
        timestamp_utc: str | None = None,
    ) -> "DiagnosticEvent":
        error_json = error.to_json()
        context_json: Mapping[str, JsonValue] = context or {}
        if redactor is not None:
            redacted_error = redactor.redact_json(error_json)
            redacted_context = redactor.redact_json(dict(context_json))
            if not isinstance(redacted_error, dict):
                raise ValueError("redacted diagnostic error must remain an object")
            if not isinstance(redacted_context, dict):
                raise ValueError("redacted diagnostic context must remain an object")
            error_json = redacted_error
            context_json = redacted_context
        if not isinstance(error_json, dict):
            raise ValueError("redacted diagnostic error must remain an object")
        if not isinstance(context_json, dict):
            raise ValueError("redacted diagnostic context must remain an object")
        return cls(
            timestamp_utc=timestamp_utc or _utc_now(),
            error=error_json,
            context=context_json,
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "timestamp_utc": self.timestamp_utc,
            "error": FrozenJsonMapping(self.error).to_json(),
            "context": FrozenJsonMapping(self.context).to_json(),
        }


@dataclass(frozen=True, slots=True)
class DiagnosticsSnapshot:
    """A deterministic diagnostics snapshot value."""

    generated_at_utc: str
    app_version: str
    platform: str
    python_version: str
    events: tuple[DiagnosticEvent, ...] = ()

    def __post_init__(self) -> None:
        for label, value in (
            ("generated_at_utc", self.generated_at_utc),
            ("app_version", self.app_version),
            ("platform", self.platform),
            ("python_version", self.python_version),
        ):
            if not value:
                raise ValueError(f"diagnostics {label} must not be empty")
        object.__setattr__(self, "events", tuple(self.events))

    @classmethod
    def from_events(
        cls,
        *,
        events: Iterable[DiagnosticEvent],
        app_version: str,
        platform: str,
        python_version: str,
        generated_at_utc: str | None = None,
    ) -> "DiagnosticsSnapshot":
        return cls(
            generated_at_utc=generated_at_utc or _utc_now(),
            app_version=app_version,
            platform=platform,
            python_version=python_version,
            events=tuple(events),
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "generated_at_utc": self.generated_at_utc,
            "app_version": self.app_version,
            "platform": self.platform,
            "python_version": self.python_version,
            "events": [event.to_json() for event in self.events],
        }


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _normalize_path_text(value: str) -> str:
    return value.replace("\\", "/").rstrip("/")
