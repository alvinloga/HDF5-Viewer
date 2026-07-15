"""Safe diagnostics values and redaction helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import json
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


@dataclass(frozen=True, slots=True)
class PluginInventoryItem:
    """Safe plugin inventory entry for diagnostics bundles."""

    plugin_id: str
    name: str
    version: str
    api_version: int
    enabled: bool

    def __post_init__(self) -> None:
        for label, value in (
            ("plugin_id", self.plugin_id),
            ("name", self.name),
            ("version", self.version),
        ):
            if not value:
                raise ValueError(f"plugin inventory {label} must not be empty")
        if self.api_version < 1:
            raise ValueError("plugin API version must be positive")

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "api_version": self.api_version,
            "enabled": self.enabled,
        }


@dataclass(frozen=True, slots=True)
class DiagnosticsBundle:
    """Previewable diagnostics package that never uploads automatically."""

    generated_at_utc: str
    app_version: str
    platform: str
    python_version: str
    plugins: tuple[PluginInventoryItem, ...] = ()
    recent_events: tuple[DiagnosticEvent, ...] = ()
    task_records: tuple[Mapping[str, JsonValue], ...] = ()

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "generated_at_utc": self.generated_at_utc,
            "app_version": self.app_version,
            "platform": self.platform,
            "python_version": self.python_version,
            "plugins": [plugin.to_json() for plugin in self.plugins],
            "recent_events": [event.to_json() for event in self.recent_events],
            "task_records": [dict(record) for record in self.task_records],
        }

    def preview_json(self) -> str:
        """Return deterministic user-preview JSON before any diagnostics export."""

        return json.dumps(self.to_json(), ensure_ascii=False, indent=2, sort_keys=True)


class DiagnosticsBundleService:
    """Build redacted diagnostics bundles from safe app-layer values."""

    def __init__(
        self,
        *,
        app_version: str,
        platform: str,
        python_version: str,
        redactor: DiagnosticsRedactor | None = None,
    ) -> None:
        self._app_version = app_version
        self._platform = platform
        self._python_version = python_version
        self._redactor = redactor or DiagnosticsRedactor()

    def build_bundle(
        self,
        *,
        plugins: Iterable[PluginInventoryItem] = (),
        recent_events: Iterable[DiagnosticEvent] = (),
        task_records: Iterable[Mapping[str, JsonValue]] = (),
        generated_at_utc: str | None = None,
    ) -> DiagnosticsBundle:
        redacted_events = tuple(self._redact_event(event) for event in recent_events)
        redacted_tasks = tuple(self._redact_mapping(record) for record in task_records)
        return DiagnosticsBundle(
            generated_at_utc=generated_at_utc or _utc_now(),
            app_version=self._app_version,
            platform=self._platform,
            python_version=self._python_version,
            plugins=tuple(plugins),
            recent_events=redacted_events,
            task_records=redacted_tasks,
        )

    def _redact_event(self, event: DiagnosticEvent) -> DiagnosticEvent:
        error = self._redact_mapping(event.error)
        context = self._redact_mapping(event.context)
        return DiagnosticEvent(
            timestamp_utc=event.timestamp_utc,
            error=error,
            context=context,
        )

    def _redact_mapping(
        self,
        value: Mapping[str, JsonValue],
    ) -> Mapping[str, JsonValue]:
        redacted = self._redactor.redact_json(dict(value))
        if not isinstance(redacted, dict):
            raise ValueError("redacted diagnostics value must remain an object")
        return redacted


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _normalize_path_text(value: str) -> str:
    return value.replace("\\", "/").rstrip("/")
