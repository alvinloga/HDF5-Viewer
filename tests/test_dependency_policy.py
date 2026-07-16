"""Dependency and license policy contracts."""

from __future__ import annotations

from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_qt_binding_dependency_is_pyside6_not_pyqt6() -> None:
    """Data Viewer keeps MIT licensing by using the LGPL-compatible Qt binding."""

    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = {dependency.casefold() for dependency in pyproject["project"]["dependencies"]}

    assert "pyside6" in dependencies
    assert "pyqt6" not in dependencies
    assert pyproject["project"]["license"] == "MIT"


def test_ci_direct_import_smoke_uses_pyside6() -> None:
    """CI must prove the release binding imports on both supported platforms."""

    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "import PySide6.QtCore" in workflow
    assert "import PyQt6.QtCore" not in workflow


def test_pytest_qt_uses_pyside6_backend() -> None:
    """Offscreen GUI tests must exercise the same Qt binding as the product."""

    pytest_ini = (PROJECT_ROOT / "pytest.ini").read_text(encoding="utf-8")

    assert "qt_api = pyside6" in pytest_ini
    assert "qt_api = pyqt6" not in pytest_ini
