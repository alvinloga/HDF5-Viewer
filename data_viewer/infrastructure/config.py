"""Versioned application configuration with schema validation and recovery."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CONFIG_SCHEMA_VERSION: int = 1


def _expect_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def _expect_non_negative_int(value: int, label: str) -> int:
    value = _expect_int(value, label)
    if value < 0:
        raise ValueError(f"{label} must be non-negative")
    return value


def _expect_optional_str(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string or null")
    return value


def _expect_str_list(value: Any, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list | tuple):
        raise ValueError(f"{label} must be a list")
    normalized = tuple(_expect_optional_str(item, f"{label} item") for item in value)
    return tuple(item for item in normalized if item is not None)


def _expect_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


@dataclass(frozen=True, slots=True)
class UIConfig:
    """Application UI preference configuration."""

    theme: str = "light"
    sidebar_width: int = 280
    secondary_panel_width: int = 280
    secondary_panel_visible: bool = False

    def __post_init__(self) -> None:
        theme = str(self.theme or "light").lower()
        if theme not in {"light", "dark", "system"}:
            raise ValueError("theme must be light, dark, or system")
        object.__setattr__(self, "theme", theme)
        object.__setattr__(
            self,
            "sidebar_width",
            _expect_non_negative_int(self.sidebar_width, "sidebar_width"),
        )
        object.__setattr__(
            self,
            "secondary_panel_width",
            _expect_non_negative_int(self.secondary_panel_width, "secondary_panel_width"),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "theme": self.theme,
            "sidebar_width": self.sidebar_width,
            "secondary_panel_width": self.secondary_panel_width,
            "secondary_panel_visible": self.secondary_panel_visible,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any] | None) -> "UIConfig":
        if value is None:
            return cls()
        data = _expect_mapping(value, "ui")
        return cls(
            theme=str(data.get("theme", cls().theme)),
            sidebar_width=_expect_non_negative_int(
                data.get("sidebar_width", cls().sidebar_width),
                "sidebar_width",
            ),
            secondary_panel_width=_expect_non_negative_int(
                data.get("secondary_panel_width", cls().secondary_panel_width),
                "secondary_panel_width",
            ),
            secondary_panel_visible=bool(data.get("secondary_panel_visible", False)),
        )


@dataclass(frozen=True, slots=True)
class CacheConfig:
    """Cache limit configuration."""

    max_bytes: int = 512 * 1024 * 1024
    max_entries: int = 128
    max_age_days: int = 7
    allow_disk_pressure_fallback: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_bytes", _expect_non_negative_int(self.max_bytes, "max_bytes"))
        object.__setattr__(self, "max_entries", _expect_non_negative_int(self.max_entries, "max_entries"))
        object.__setattr__(self, "max_age_days", _expect_non_negative_int(self.max_age_days, "max_age_days"))

    def to_json(self) -> dict[str, Any]:
        return {
            "max_bytes": self.max_bytes,
            "max_entries": self.max_entries,
            "max_age_days": self.max_age_days,
            "allow_disk_pressure_fallback": self.allow_disk_pressure_fallback,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any] | None) -> "CacheConfig":
        if value is None:
            return cls()
        data = _expect_mapping(value, "cache")
        return cls(
            max_bytes=_expect_non_negative_int(
                data.get("max_bytes", CacheConfig().max_bytes),
                "max_bytes",
            ),
            max_entries=_expect_non_negative_int(
                data.get("max_entries", CacheConfig().max_entries),
                "max_entries",
            ),
            max_age_days=_expect_non_negative_int(
                data.get("max_age_days", CacheConfig().max_age_days),
                "max_age_days",
            ),
            allow_disk_pressure_fallback=bool(data.get("allow_disk_pressure_fallback", True)),
        )


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """Logging redaction and retention configuration."""

    level: str = "INFO"
    console_level: str = "INFO"
    file_enabled: bool = True
    file_max_bytes: int = 10 * 1024 * 1024
    file_backups: int = 3
    sensitive_paths: tuple[str, ...] = field(default_factory=tuple)
    sensitive_values: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "level",
            str(self.level or "").upper() or "INFO",
        )
        object.__setattr__(
            self,
            "console_level",
            str(self.console_level or "").upper() or self.level,
        )
        if self.file_backups < 0:
            raise ValueError("file_backups must be non-negative")
        object.__setattr__(
            self,
            "file_backups",
            _expect_non_negative_int(self.file_backups, "file_backups"),
        )
        object.__setattr__(
            self,
            "file_max_bytes",
            _expect_non_negative_int(self.file_max_bytes, "file_max_bytes"),
        )
        object.__setattr__(
            self,
            "sensitive_paths",
            _expect_str_list(self.sensitive_paths, "sensitive_paths"),
        )
        object.__setattr__(
            self,
            "sensitive_values",
            _expect_str_list(self.sensitive_values, "sensitive_values"),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "console_level": self.console_level,
            "file_enabled": self.file_enabled,
            "file_max_bytes": self.file_max_bytes,
            "file_backups": self.file_backups,
            "sensitive_paths": list(self.sensitive_paths),
            "sensitive_values": list(self.sensitive_values),
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any] | None) -> "LoggingConfig":
        if value is None:
            return cls()
        data = _expect_mapping(value, "logging")
        return cls(
            level=str(data.get("level", cls().level)),
            console_level=str(data.get("console_level", cls().console_level)),
            file_enabled=bool(data.get("file_enabled", True)),
            file_max_bytes=_expect_non_negative_int(
                data.get("file_max_bytes", cls().file_max_bytes),
                "file_max_bytes",
            ),
            file_backups=_expect_non_negative_int(
                data.get("file_backups", cls().file_backups),
                "file_backups",
            ),
            sensitive_paths=_expect_str_list(data.get("sensitive_paths"), "sensitive_paths"),
            sensitive_values=_expect_str_list(data.get("sensitive_values"), "sensitive_values"),
        )


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Versioned and validated application configuration value."""

    schema_version: int = CONFIG_SCHEMA_VERSION
    ui: UIConfig = field(default_factory=UIConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _expect_non_negative_int(self.schema_version, "schema_version"),
        )
        if self.schema_version != CONFIG_SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema version: {self.schema_version}")

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ui": self.ui.to_json(),
            "cache": self.cache.to_json(),
            "logging": self.logging.to_json(),
            "updated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "AppConfig":
        data = _expect_mapping(value, "config")
        schema_version = _expect_non_negative_int(
            data.get("schema_version", CONFIG_SCHEMA_VERSION),
            "schema_version",
        )
        if schema_version != CONFIG_SCHEMA_VERSION:
            raise ValueError(f"Unsupported config schema version: {schema_version}")
        return cls(
            schema_version=schema_version,
            ui=UIConfig.from_json(
                data.get("ui") if isinstance(data.get("ui"), Mapping) else None
            ),
            cache=CacheConfig.from_json(
                data.get("cache") if isinstance(data.get("cache"), Mapping) else None
            ),
            logging=LoggingConfig.from_json(
                data.get("logging") if isinstance(data.get("logging"), Mapping) else None
            ),
        )


@dataclass(frozen=True, slots=True)
class LoadConfigResult:
    """Result from reading a config file."""

    config: AppConfig
    recovered: bool
    source: str


def load_config(path: Path, *, defaults: AppConfig | None = None) -> LoadConfigResult:
    """
    Load config from disk with recovery on corruption.

    Returns recovered defaults on file corruption or schema mismatch.
    """
    base = defaults or AppConfig()
    if not path.exists():
        return LoadConfigResult(config=base, recovered=False, source="missing")

    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
        config = AppConfig.from_json(_expect_mapping(payload, "config file"))
        return LoadConfigResult(config=config, recovered=False, source="file")
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as error:
        _backup_corrupt_config(path)
        return LoadConfigResult(
            config=replace(base),
            recovered=True,
            source=f"corrupt:{type(error).__name__}",
        )


def save_config(path: Path, config: AppConfig) -> None:
    """Write config atomically without partial writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        config.to_json(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
    ) as handle:
        temp_path = Path(handle.name)
        handle.write(text)
        handle.flush()
    temp_path.replace(path)


def merge_and_save_config(
    path: Path, *,
    config: AppConfig | None = None,
    defaults: AppConfig | None = None,
) -> AppConfig:
    """
    Merge partial config payloads and save atomically.

    Unknown keys are intentionally not preserved in v1 and are validated by `AppConfig`.
    """
    current = load_config(path, defaults=defaults).config
    next_config = config or current
    save_config(path, next_config)
    return next_config


def config_to_json(config: AppConfig) -> dict[str, Any]:
    return config.to_json()


def _backup_corrupt_config(path: Path) -> None:
    backup = path.with_suffix(path.suffix + f".corrupt.{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}")
    try:
        shutil.copy2(path, backup)
    except OSError:
        pass
