"""Platform-specific standard directories for Data Viewer infrastructure files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from platformdirs import user_cache_dir, user_config_dir, user_log_dir

APP_NAME: Final = "Data Viewer"
APP_AUTHOR: Final = "Data Viewer"
APP_NAME_LEGACY_FALLBACK: Final = "HDF5-Viewer"

CONFIG_FILE_NAME: Final = "config.json"
LOG_FILE_NAME: Final = "data-viewer.log"
LOG_DIR_NAME: Final = "logs"
CACHE_DIR_NAME: Final = "cache"
CONFIG_ENV_VAR: Final = "DATA_VIEWER_CONFIG_DIR"
CACHE_ENV_VAR: Final = "DATA_VIEWER_CACHE_DIR"
LOG_ENV_VAR: Final = "DATA_VIEWER_LOG_DIR"


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Resolved platform-standard directories for application infrastructure."""

    config_dir: Path
    cache_dir: Path
    log_dir: Path
    logs_archive_dir: Path

    def to_dict(self) -> dict[str, str]:
        """Return the resolved paths as a plain JSON-safe mapping."""
        return {
            "config_dir": str(self.config_dir),
            "cache_dir": str(self.cache_dir),
            "log_dir": str(self.log_dir),
            "logs_archive_dir": str(self.logs_archive_dir),
        }


@dataclass(frozen=True, slots=True)
class AppConfigFiles:
    """Resolved file locations derived from :class:`AppPaths`."""

    config_file: Path
    cache_tombstone: Path
    cache_index: Path
    log_file: Path


def resolve_app_paths(
    *,
    app_name: str = APP_NAME,
    app_author: str = APP_AUTHOR,
    config_dir_override: str | Path | None = None,
    cache_dir_override: str | Path | None = None,
    log_dir_override: str | Path | None = None,
) -> AppPaths:
    """
    Resolve all application paths for the current platform.

    Args:
        app_name: application name for platform dir APIs;
        app_author: optional vendor/author tag for platform dirs;
        config_dir_override: explicit config directory override;
        cache_dir_override: explicit cache directory override;
        log_dir_override: explicit log directory override.

    Returns:
        Resolved absolute paths for config/cache/log directories.
    """

    resolved_config = (
        Path(config_dir_override)
        if config_dir_override is not None
        else _platform_config_dir_override(app_name, app_author)
    )
    resolved_cache = (
        Path(cache_dir_override)
        if cache_dir_override is not None
        else _platform_cache_dir_override(app_name, app_author)
    )
    resolved_log = (
        Path(log_dir_override)
        if log_dir_override is not None
        else _platform_log_dir_override(app_name, app_author)
    )

    resolved_config = resolved_config.expanduser().resolve()
    resolved_cache = resolved_cache.expanduser().resolve()
    resolved_log = resolved_log.expanduser().resolve()

    logs_archive = resolved_log / LOG_DIR_NAME
    return AppPaths(
        config_dir=resolved_config,
        cache_dir=resolved_cache,
        log_dir=resolved_log,
        logs_archive_dir=logs_archive,
    )


def platform_files(paths: AppPaths) -> AppConfigFiles:
    """Return canonical file locations derived from the resolved app paths."""
    return AppConfigFiles(
        config_file=paths.config_dir / CONFIG_FILE_NAME,
        cache_tombstone=paths.cache_dir / "tombstone.json",
        cache_index=paths.cache_dir / "cache-index.json",
        log_file=paths.logs_archive_dir / LOG_FILE_NAME,
    )


def ensure_app_directories(paths: AppPaths) -> AppPaths:
    """
    Create app directories needed for cache/log/config access.

    Creation is explicit and idempotent.
    """
    for candidate in (
        paths.config_dir,
        paths.cache_dir,
        paths.log_dir,
        paths.logs_archive_dir,
    ):
        candidate.mkdir(parents=True, exist_ok=True)
    return paths


def _platform_config_dir_override(app_name: str, app_author: str) -> Path:
    env_override = _read_env_path(CONFIG_ENV_VAR)
    if env_override is not None:
        return env_override
    return Path(user_config_dir(app_name, app_author))


def _platform_cache_dir_override(app_name: str, app_author: str) -> Path:
    env_override = _read_env_path(CACHE_ENV_VAR)
    if env_override is not None:
        return env_override
    return Path(user_cache_dir(app_name, app_author))


def _platform_log_dir_override(app_name: str, app_author: str) -> Path:
    env_override = _read_env_path(LOG_ENV_VAR)
    if env_override is not None:
        return env_override

    log_root = user_log_dir(app_name, app_author)
    if log_root:
        return Path(log_root)

    # Some legacy platforms expose no log directory; fall back to cache directory
    # so application startup stays deterministic.
    return Path(user_cache_dir(app_name, app_author)) / "logs"


def _read_env_path(name: str) -> Path | None:
    raw = __import__("os").environ.get(name)
    if not raw:
        return None
    return Path(raw)
