"""Safe migration from legacy repository config into target platform config."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from .config import AppConfig, UIConfig, save_config


class LegacyConfigDecision(StrEnum):
    """Explicit user/application decision for a legacy config migration."""

    PREVIEW = "preview"
    MIGRATE = "migrate"
    DECLINE = "decline"


@dataclass(frozen=True, slots=True)
class LegacyConfigPreview:
    """Validated legacy config preview that can be shown before migration."""

    status: str
    config: AppConfig
    known_keys: tuple[str, ...] = ()
    unknown_keys: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LegacyConfigMigrationResult:
    """Result of applying or declining a legacy config migration."""

    preview: LegacyConfigPreview
    applied: bool
    reason: str
    target_path: Path
    legacy_path: Path


_KNOWN_ROOT_KEYS = {"ui"}
_KNOWN_UI_KEYS = {
    "theme",
    "sidebarWidth",
    "secondaryPanelWidth",
    "secondaryPanelVisible",
}


def preview_legacy_config(
    legacy_path: Path,
    *,
    defaults: AppConfig | None = None,
) -> LegacyConfigPreview:
    """Read and validate a legacy repository ``config.json`` without modifying it."""

    base = defaults or AppConfig()
    if not legacy_path.exists():
        return LegacyConfigPreview(
            status="missing",
            config=base,
            warnings=("Legacy config file was not found.",),
        )

    try:
        payload = json.loads(legacy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return LegacyConfigPreview(
            status="invalid",
            config=base,
            warnings=(f"Legacy config could not be parsed: {type(error).__name__}",),
        )

    if not isinstance(payload, Mapping):
        return LegacyConfigPreview(
            status="invalid",
            config=base,
            warnings=("Legacy config root must be a JSON object.",),
        )

    try:
        ui_config, known_ui_keys, unknown_ui_keys, warnings = _migrate_legacy_ui(
            payload.get("ui"),
            defaults=base.ui,
        )
    except (TypeError, ValueError) as error:
        return LegacyConfigPreview(
            status="invalid",
            config=base,
            warnings=(f"Legacy UI config is invalid: {error}",),
        )

    unknown_root_keys = tuple(sorted(str(key) for key in payload if key not in _KNOWN_ROOT_KEYS))
    unknown_keys = unknown_ui_keys + unknown_root_keys
    warning_values = tuple(warnings) + tuple(
        f"Unknown legacy config key ignored: {key}" for key in unknown_keys
    )
    return LegacyConfigPreview(
        status="valid",
        config=replace(base, ui=ui_config),
        known_keys=known_ui_keys,
        unknown_keys=unknown_keys,
        warnings=warning_values,
    )


def apply_legacy_config_migration(
    *,
    legacy_path: Path,
    target_path: Path,
    decision: LegacyConfigDecision,
    defaults: AppConfig | None = None,
) -> LegacyConfigMigrationResult:
    """
    Apply an explicit legacy migration decision.

    The legacy file is never modified or deleted. Existing target config wins so
    a stale repository config cannot downgrade current user preferences.
    """

    preview = preview_legacy_config(legacy_path, defaults=defaults)
    if decision is LegacyConfigDecision.DECLINE:
        return LegacyConfigMigrationResult(
            preview=preview,
            applied=False,
            reason="declined",
            target_path=target_path,
            legacy_path=legacy_path,
        )
    if decision is LegacyConfigDecision.PREVIEW:
        return LegacyConfigMigrationResult(
            preview=preview,
            applied=False,
            reason="preview_only",
            target_path=target_path,
            legacy_path=legacy_path,
        )
    if target_path.exists():
        return LegacyConfigMigrationResult(
            preview=preview,
            applied=False,
            reason="target_exists",
            target_path=target_path,
            legacy_path=legacy_path,
        )
    if preview.status != "valid":
        return LegacyConfigMigrationResult(
            preview=preview,
            applied=False,
            reason="invalid_legacy",
            target_path=target_path,
            legacy_path=legacy_path,
        )

    save_config(target_path, preview.config)
    return LegacyConfigMigrationResult(
        preview=preview,
        applied=True,
        reason="migrated",
        target_path=target_path,
        legacy_path=legacy_path,
    )


def _migrate_legacy_ui(
    value: Any,
    *,
    defaults: UIConfig,
) -> tuple[UIConfig, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if value is None:
        return defaults, (), (), ()
    if not isinstance(value, Mapping):
        raise ValueError("ui must be an object")

    unknown_keys = tuple(sorted(f"ui.{key}" for key in value if key not in _KNOWN_UI_KEYS))
    warnings: list[str] = []
    theme = str(value.get("theme", defaults.theme)).lower()
    if theme not in {"light", "dark", "system"}:
        warnings.append(f"Unsupported legacy theme {theme!r}; using safe default.")
        theme = defaults.theme

    sidebar_width = _legacy_non_negative_int(
        value.get("sidebarWidth", defaults.sidebar_width),
        "ui.sidebarWidth",
        warnings,
        defaults.sidebar_width,
    )
    secondary_panel_width = _legacy_non_negative_int(
        value.get("secondaryPanelWidth", defaults.secondary_panel_width),
        "ui.secondaryPanelWidth",
        warnings,
        defaults.secondary_panel_width,
    )
    secondary_panel_visible = bool(
        value.get("secondaryPanelVisible", defaults.secondary_panel_visible)
    )
    known_keys = tuple(
        f"ui.{key}" for key in sorted(value) if key in _KNOWN_UI_KEYS
    )
    return (
        UIConfig(
            theme=theme,
            sidebar_width=sidebar_width,
            secondary_panel_width=secondary_panel_width,
            secondary_panel_visible=secondary_panel_visible,
        ),
        known_keys,
        unknown_keys,
        tuple(warnings),
    )


def _legacy_non_negative_int(
    value: Any,
    label: str,
    warnings: list[str],
    default: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        warnings.append(f"Invalid legacy {label}; using safe default.")
        return default
    return value


__all__ = [
    "LegacyConfigDecision",
    "LegacyConfigMigrationResult",
    "LegacyConfigPreview",
    "apply_legacy_config_migration",
    "preview_legacy_config",
]
