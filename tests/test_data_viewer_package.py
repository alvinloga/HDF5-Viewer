"""Contract tests for the target Data Viewer package entrypoint."""

from __future__ import annotations

from unittest.mock import Mock
import sys

import data_viewer
from data_viewer import __version__
import data_viewer.__main__ as entrypoint


def test_package_exports_its_canonical_development_version() -> None:
    """The target package exposes the single version used by build metadata."""
    assert data_viewer.__version__ == __version__


def _run_with_argv(
    argv: list[str],
    *,
    run_data_viewer,
    run_legacy,
) -> int:
    """Run parser+dispatch with injectable handlers for testability."""

    old_argv = list(sys.argv)
    sys.argv = argv
    try:
        return entrypoint.main_with_handlers(
            run_data_viewer=run_data_viewer,
            run_legacy=run_legacy,
        )
    finally:
        sys.argv = old_argv


def test_package_cli_version() -> None:
    """`--version` exits without launching any bootstrap."""
    called_bootstrap = False

    def fake_bootstrap(*, path: str | None = None, app_args=None) -> int:
        nonlocal called_bootstrap
        called_bootstrap = True
        return 0

    exit_code = _run_with_argv(
        ["data-viewer", "--version"],
        run_data_viewer=fake_bootstrap,
        run_legacy=Mock(return_value=0),
    )
    assert exit_code == 0
    assert not called_bootstrap


def test_cli_defaults_to_target_bootstrap() -> None:
    """The default CLI path starts the target bootstrap."""
    fake_bootstrap = Mock(return_value=123)
    exit_code = _run_with_argv(
        ["data-viewer", "file.h5"],
        run_data_viewer=fake_bootstrap,
        run_legacy=Mock(return_value=0),
    )
    assert exit_code == 123
    fake_bootstrap.assert_called_once_with(path="file.h5")


def test_cli_legacy_is_explicit() -> None:
    """`--legacy` routes to legacy fallback without touching target bootstrap."""
    fake_legacy = Mock(return_value=7)
    exit_code = _run_with_argv(
        ["data-viewer", "--legacy", "legacy.h5"],
        run_data_viewer=Mock(return_value=0),
        run_legacy=fake_legacy,
    )
    assert exit_code == 7
    fake_legacy.assert_called_once_with("legacy.h5")
