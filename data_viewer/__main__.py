"""Temporary command-line entry point while the target bootstrap is built."""

from __future__ import annotations

from . import __version__


def main() -> int:
    """Explain the migration state without starting the legacy application."""
    print(
        f"Data Viewer development shell {__version__}: "
        "the target application bootstrap is not available yet."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
