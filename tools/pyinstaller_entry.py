"""PyInstaller entrypoint for the Data Viewer application."""

from __future__ import annotations

from data_viewer.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
