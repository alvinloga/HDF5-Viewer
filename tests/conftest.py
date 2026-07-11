"""Process-wide test configuration for the legacy and target suites."""

from __future__ import annotations

import json
import locale
import os
import time

import pytest


# Set these before pytest imports any module that imports PyQt6 or Matplotlib.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")


@pytest.fixture(autouse=True)
def stabilize_locale_and_timezone():
    """Give every test deterministic locale and timezone process state."""
    original_locale = locale.setlocale(locale.LC_ALL)
    original_timezone = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    locale.setlocale(locale.LC_ALL, "C")
    if hasattr(time, "tzset"):
        time.tzset()

    try:
        yield
    finally:
        locale.setlocale(locale.LC_ALL, original_locale)
        if original_timezone is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_timezone
        if hasattr(time, "tzset"):
            time.tzset()


@pytest.fixture(autouse=True)
def isolate_legacy_config_writes(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Keep legacy MainWindow persistence inside pytest's temporary directory."""
    from gui.main_window import MainWindow

    test_config_path = tmp_path / "config.json"

    def save_config_to_test_path(window: MainWindow) -> None:
        test_config_path.write_text(
            json.dumps(window._config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    monkeypatch.setattr(MainWindow, "_save_config", save_config_to_test_path)


@pytest.fixture(autouse=True)
def reset_legacy_process_state():
    """Release legacy global state before it can escape an individual test."""
    from core.event_bus import EventBus
    from core.registry import DataSourceRegistry

    DataSourceRegistry.close_all()
    EventBus.get_instance().clear()
    yield
    DataSourceRegistry.close_all()
    EventBus.get_instance().clear()
