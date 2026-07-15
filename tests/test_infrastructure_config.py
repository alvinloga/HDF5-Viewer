"""Contracts for versioned configuration loading, validation, and recovery."""

from __future__ import annotations

import json

from data_viewer.infrastructure.config import (
    CONFIG_SCHEMA_VERSION,
    AppConfig,
    CacheConfig,
    LoggingConfig,
    UIConfig,
    load_config,
    save_config,
)
from data_viewer.infrastructure.config_migration import (
    LegacyConfigDecision,
    apply_legacy_config_migration,
    preview_legacy_config,
)
from data_viewer.gui.app import prepare_runtime_configuration


def test_load_missing_config_returns_safe_defaults(tmp_path) -> None:
    path = tmp_path / "missing.json"

    loaded = load_config(path)

    assert isinstance(loaded.config, AppConfig)
    assert loaded.config.schema_version == CONFIG_SCHEMA_VERSION
    assert not loaded.recovered
    assert loaded.source == "missing"


def test_load_and_save_config_roundtrip(tmp_path) -> None:
    path = tmp_path / "config.json"
    config = AppConfig(
        ui=UIConfig(
            theme="dark",
            sidebar_width=320,
            secondary_panel_width=360,
            secondary_panel_visible=True,
        ),
        cache=CacheConfig(max_bytes=1234, max_entries=7, max_age_days=3),
        logging=LoggingConfig(
            level="DEBUG",
            console_level="INFO",
            file_backups=2,
            sensitive_paths=("/tmp/secret",),
        ),
    )

    save_config(path, config)
    loaded = load_config(path)

    assert loaded.source == "file"
    assert loaded.config.ui.theme == "dark"
    assert loaded.config.ui.sidebar_width == 320
    assert loaded.config.ui.secondary_panel_width == 360
    assert loaded.config.ui.secondary_panel_visible is True
    assert loaded.config.cache.max_bytes == 1234
    assert loaded.config.cache.max_entries == 7
    assert loaded.config.logging.level == "DEBUG"
    assert loaded.config.logging.sensitive_paths == ("/tmp/secret",)


def test_corrupt_config_is_recovered_to_defaults_and_backed_up(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{not-json")

    loaded = load_config(path)

    assert loaded.config.schema_version == CONFIG_SCHEMA_VERSION
    assert loaded.recovered
    assert loaded.source.startswith("corrupt:")
    backups = list(tmp_path.glob("config.json.corrupt.*"))
    assert len(backups) == 1


def test_unsupported_schema_version_returns_defaults(tmp_path) -> None:
    path = tmp_path / "config.json"
    payload = (
        '{"schema_version": 99, "cache": {"max_bytes": 123}, "logging": {"level": "INFO"}}'
    )
    path.write_text(payload)

    loaded = load_config(path)

    assert loaded.recovered
    assert loaded.config.schema_version == CONFIG_SCHEMA_VERSION


def test_preview_legacy_config_maps_known_ui_values_and_warns_unknown_keys(tmp_path) -> None:
    legacy_path = tmp_path / "config.json"
    legacy_path.write_text(
        json.dumps(
            {
                "ui": {
                    "theme": "dark",
                    "sidebarWidth": 333,
                    "secondaryPanelWidth": 444,
                    "secondaryPanelVisible": True,
                    "surprise": "ignored",
                },
                "plugins": {"old": True},
            }
        ),
        encoding="utf-8",
    )

    preview = preview_legacy_config(legacy_path)

    assert preview.status == "valid"
    assert preview.config.ui.theme == "dark"
    assert preview.config.ui.sidebar_width == 333
    assert preview.config.ui.secondary_panel_width == 444
    assert preview.config.ui.secondary_panel_visible is True
    assert "ui.surprise" in preview.unknown_keys
    assert "plugins" in preview.unknown_keys
    assert preview.warnings


def test_apply_legacy_migration_writes_target_without_modifying_legacy(tmp_path) -> None:
    legacy_path = tmp_path / "legacy" / "config.json"
    target_path = tmp_path / "target" / "config.json"
    legacy_path.parent.mkdir()
    legacy_payload = {"ui": {"theme": "dark", "sidebarWidth": 301}}
    legacy_text = json.dumps(legacy_payload, sort_keys=True)
    legacy_path.write_text(legacy_text, encoding="utf-8")

    result = apply_legacy_config_migration(
        legacy_path=legacy_path,
        target_path=target_path,
        decision=LegacyConfigDecision.MIGRATE,
    )

    assert result.applied is True
    assert target_path.exists()
    assert legacy_path.read_text(encoding="utf-8") == legacy_text
    loaded = load_config(target_path)
    assert loaded.config.ui.theme == "dark"
    assert loaded.config.ui.sidebar_width == 301


def test_decline_legacy_migration_leaves_target_missing_and_legacy_unchanged(tmp_path) -> None:
    legacy_path = tmp_path / "legacy-config.json"
    target_path = tmp_path / "target-config.json"
    legacy_text = json.dumps({"ui": {"theme": "dark"}})
    legacy_path.write_text(legacy_text, encoding="utf-8")

    result = apply_legacy_config_migration(
        legacy_path=legacy_path,
        target_path=target_path,
        decision=LegacyConfigDecision.DECLINE,
    )

    assert result.applied is False
    assert result.reason == "declined"
    assert not target_path.exists()
    assert legacy_path.read_text(encoding="utf-8") == legacy_text


def test_corrupt_legacy_config_preview_is_safe_and_migration_does_not_write(tmp_path) -> None:
    legacy_path = tmp_path / "config.json"
    target_path = tmp_path / "target" / "config.json"
    legacy_path.write_text("{not-json", encoding="utf-8")

    preview = preview_legacy_config(legacy_path)
    result = apply_legacy_config_migration(
        legacy_path=legacy_path,
        target_path=target_path,
        decision=LegacyConfigDecision.MIGRATE,
    )

    assert preview.status == "invalid"
    assert preview.config == AppConfig()
    assert result.applied is False
    assert result.reason == "invalid_legacy"
    assert not target_path.exists()


def test_existing_target_config_blocks_legacy_downgrade_overwrite(tmp_path) -> None:
    legacy_path = tmp_path / "legacy-config.json"
    target_path = tmp_path / "target-config.json"
    legacy_path.write_text(json.dumps({"ui": {"theme": "dark"}}), encoding="utf-8")
    save_config(target_path, AppConfig(ui=UIConfig(theme="light", sidebar_width=222)))

    result = apply_legacy_config_migration(
        legacy_path=legacy_path,
        target_path=target_path,
        decision=LegacyConfigDecision.MIGRATE,
    )

    loaded = load_config(target_path)
    assert result.applied is False
    assert result.reason == "target_exists"
    assert loaded.config.ui.theme == "light"
    assert loaded.config.ui.sidebar_width == 222


def test_prepare_runtime_configuration_previews_legacy_without_writing(tmp_path) -> None:
    legacy_path = tmp_path / "repo" / "config.json"
    legacy_path.parent.mkdir()
    legacy_path.write_text(json.dumps({"ui": {"theme": "dark"}}), encoding="utf-8")
    config_dir = tmp_path / "platform-config"

    runtime = prepare_runtime_configuration(
        config_dir_override=config_dir,
        cache_dir_override=tmp_path / "cache",
        log_dir_override=tmp_path / "log",
        legacy_config_path=legacy_path,
        legacy_decision=LegacyConfigDecision.PREVIEW,
    )

    assert runtime.paths.config_dir == config_dir.resolve()
    assert runtime.config.ui.theme == "light"
    assert runtime.legacy_migration.reason == "preview_only"
    assert runtime.legacy_migration.preview.config.ui.theme == "dark"
    assert not runtime.files.config_file.exists()
    assert legacy_path.exists()


def test_prepare_runtime_configuration_can_apply_explicit_legacy_migration(tmp_path) -> None:
    legacy_path = tmp_path / "repo" / "config.json"
    legacy_path.parent.mkdir()
    legacy_path.write_text(
        json.dumps({"ui": {"theme": "dark", "secondaryPanelVisible": True}}),
        encoding="utf-8",
    )

    runtime = prepare_runtime_configuration(
        config_dir_override=tmp_path / "platform-config",
        cache_dir_override=tmp_path / "cache",
        log_dir_override=tmp_path / "log",
        legacy_config_path=legacy_path,
        legacy_decision=LegacyConfigDecision.MIGRATE,
    )

    assert runtime.legacy_migration.applied is True
    assert runtime.config.ui.theme == "dark"
    assert runtime.config.ui.secondary_panel_visible is True
    assert runtime.files.config_file.exists()
