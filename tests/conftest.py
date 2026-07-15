"""Process-wide test configuration for the target Data Viewer suite."""

from __future__ import annotations

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
