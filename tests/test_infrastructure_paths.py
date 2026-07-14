"""Contracts for platform path resolution and safe overrides."""

from __future__ import annotations

from data_viewer.infrastructure.paths import (
    APP_NAME,
    AppPaths,
    ensure_app_directories,
    platform_files,
    resolve_app_paths,
)


def test_resolve_app_paths_respects_environment_overrides(tmp_path, monkeypatch) -> None:
    """Overridden environment directories must win over platform defaults."""
    config_override = tmp_path / "config-root"
    cache_override = tmp_path / "cache-root"
    log_override = tmp_path / "log-root"

    monkeypatch.setenv("DATA_VIEWER_CONFIG_DIR", str(config_override))
    monkeypatch.setenv("DATA_VIEWER_CACHE_DIR", str(cache_override))
    monkeypatch.setenv("DATA_VIEWER_LOG_DIR", str(log_override))

    paths = resolve_app_paths(app_name=APP_NAME, app_author=APP_NAME)

    assert paths.config_dir == config_override.resolve()
    assert paths.cache_dir == cache_override.resolve()
    assert paths.log_dir == log_override.resolve()
    assert paths.logs_archive_dir == log_override.resolve() / "logs"


def test_ensure_directories_is_idempotent_and_absent_before_creation(tmp_path) -> None:
    """Directory creation must be explicit and safe to call repeatedly."""
    paths = AppPaths(
        config_dir=tmp_path / "config",
        cache_dir=tmp_path / "cache",
        log_dir=tmp_path / "log",
        logs_archive_dir=tmp_path / "log" / "logs",
    )

    assert not paths.config_dir.exists()
    assert not paths.cache_dir.exists()
    assert not paths.log_dir.exists()
    assert not paths.logs_archive_dir.exists()

    ensure_app_directories(paths)
    ensure_app_directories(paths)

    assert paths.config_dir.is_dir()
    assert paths.cache_dir.is_dir()
    assert paths.log_dir.is_dir()
    assert paths.logs_archive_dir.is_dir()


def test_platform_file_conventions_are_stable(tmp_path) -> None:
    """Platform file helpers should derive deterministic filenames."""
    paths = AppPaths(
        config_dir=tmp_path / "config",
        cache_dir=tmp_path / "cache",
        log_dir=tmp_path / "log",
        logs_archive_dir=tmp_path / "log" / "logs",
    )

    files = platform_files(paths)

    assert files.config_file.name == "config.json"
    assert files.log_file.name == "data-viewer.log"
    assert files.cache_index.name == "cache-index.json"
    assert files.cache_tombstone.name == "tombstone.json"
