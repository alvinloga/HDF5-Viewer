"""Contracts for versioned configuration loading, validation, and recovery."""

from __future__ import annotations

from pathlib import Path

from data_viewer.infrastructure.config import (
    CONFIG_SCHEMA_VERSION,
    AppConfig,
    CacheConfig,
    LoggingConfig,
    load_config,
    save_config,
)


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
