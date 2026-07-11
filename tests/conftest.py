"""Process-wide test configuration for the legacy and target suites."""

from __future__ import annotations

import json
import os

import pytest


# Set these before pytest imports any module that imports PyQt6 or Matplotlib.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")


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
