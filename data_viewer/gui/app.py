"""Application bootstrap for the target Data Viewer shell."""

from __future__ import annotations

from dataclasses import dataclass
import sys
from pathlib import Path
from typing import Sequence

from PyQt6.QtWidgets import QApplication

from data_viewer import __version__
from data_viewer.gui.shell import launch_shell
from data_viewer.gui.theme import ThemeMode, apply_application_theme
from data_viewer.infrastructure.config import AppConfig, LoadConfigResult, load_config
from data_viewer.infrastructure.config_migration import (
    LegacyConfigDecision,
    LegacyConfigMigrationResult,
    apply_legacy_config_migration,
)
from data_viewer.infrastructure.paths import (
    AppConfigFiles,
    AppPaths,
    ensure_app_directories,
    platform_files,
    resolve_app_paths,
)


@dataclass(frozen=True, slots=True)
class RuntimeConfiguration:
    """Prepared platform paths and target application configuration."""

    paths: AppPaths
    files: AppConfigFiles
    loaded: LoadConfigResult
    config: AppConfig
    legacy_migration: LegacyConfigMigrationResult


def run_data_viewer(
    *,
    path: str | None = None,
    app_args: Sequence[str] | None = None,
) -> int:
    """Start the target Qt shell and enter the GUI event loop.

    Parameters
    ----------
    path:
        Optional file path opened on startup.
    app_args:
        Optional additional CLI args for the QApplication instance.

    Returns
    -------
    int
        Exit code from the GUI event loop.
    """

    runtime = prepare_runtime_configuration()
    qt_args = _build_qt_argv(sys.argv[0], app_args)
    app = QApplication(qt_args)
    app.setApplicationName("Data Viewer")
    app.setApplicationVersion(__version__)
    apply_application_theme(app, _theme_mode_from_config(runtime.config))

    startup = Path(path) if path else None
    launch_shell(startup_path=startup)
    return int(app.exec())


def prepare_runtime_configuration(
    *,
    config_dir_override: str | Path | None = None,
    cache_dir_override: str | Path | None = None,
    log_dir_override: str | Path | None = None,
    legacy_config_path: str | Path | None = None,
    legacy_decision: LegacyConfigDecision = LegacyConfigDecision.PREVIEW,
) -> RuntimeConfiguration:
    """Resolve platform directories and prepare target config before Qt startup."""

    paths = ensure_app_directories(
        resolve_app_paths(
            config_dir_override=config_dir_override,
            cache_dir_override=cache_dir_override,
            log_dir_override=log_dir_override,
        )
    )
    files = platform_files(paths)
    legacy_path = Path(legacy_config_path) if legacy_config_path is not None else _repository_legacy_config_path()
    migration = apply_legacy_config_migration(
        legacy_path=legacy_path,
        target_path=files.config_file,
        decision=legacy_decision,
    )
    loaded = load_config(files.config_file)
    return RuntimeConfiguration(
        paths=paths,
        files=files,
        loaded=loaded,
        config=loaded.config,
        legacy_migration=migration,
    )


def _build_qt_argv(program: str, app_args: Sequence[str] | None) -> list[str]:
    """Build the argument vector forwarded to QApplication."""

    args = [program]
    if app_args:
        args.extend(app_args)
    return args


def _repository_legacy_config_path() -> Path:
    """Return the historical repository-local config path for migration preview."""

    return Path(__file__).resolve().parents[2] / "config.json"


def _theme_mode_from_config(config: AppConfig) -> ThemeMode:
    """Map versioned config to the currently implemented theme modes."""

    if config.ui.theme == "dark":
        return ThemeMode.DARK
    return ThemeMode.LIGHT


__all__ = ["RuntimeConfiguration", "prepare_runtime_configuration", "run_data_viewer"]
