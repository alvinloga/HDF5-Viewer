"""Accessibility and high-DPI helpers for native Qt Data Viewer widgets."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class AccessibilityIssue:
    """One actionable accessibility audit problem."""

    object_name: str
    widget_class: str
    problem: str


_AUDITED_CLASSES = (QPushButton, QLineEdit, QPlainTextEdit, QTreeWidget, QTabWidget)


def set_accessible(
    widget: QWidget,
    *,
    name: str,
    description: str | None = None,
) -> None:
    """Set accessible metadata consistently on a widget."""

    widget.setAccessibleName(name)
    if description is not None:
        widget.setAccessibleDescription(description)


def focus_chain_names(widget: QWidget, *, start_name: str, limit: int) -> list[str]:
    """Return object names encountered from a named widget's focus chain."""

    start = widget.findChild(QWidget, start_name)
    if start is None or limit <= 0:
        return []
    names: list[str] = []
    current: QWidget | None = start
    seen: set[int] = set()
    while current is not None and len(names) < limit and id(current) not in seen:
        seen.add(id(current))
        name = current.objectName()
        if name:
            names.append(name)
        current = current.nextInFocusChain()
    return names


def audit_accessible_widgets(root: QWidget) -> list[AccessibilityIssue]:
    """Audit user-facing interactive widgets for accessible names."""

    widgets: list[QWidget] = []
    if isinstance(root, _AUDITED_CLASSES):
        widgets.append(root)
    widgets.extend(root.findChildren(_AUDITED_CLASSES))

    issues: list[AccessibilityIssue] = []
    for widget in widgets:
        object_name = widget.objectName()
        if not object_name:
            continue
        if object_name.startswith("qt_"):
            continue
        if not widget.accessibleName().strip():
            issues.append(
                AccessibilityIssue(
                    object_name=object_name,
                    widget_class=type(widget).__name__,
                    problem="missing accessible name",
                )
            )
    return issues


def scaled_metric(value: int, *, scale_factor: float = 1.0, grid: int = 4) -> int:
    """Scale a UI metric and snap positive values up to the compact grid."""

    if value <= 0:
        return 0
    scaled = value * max(scale_factor, 0.1)
    if grid <= 1:
        return int(round(scaled))
    return int(math.ceil(scaled / grid) * grid)


__all__ = [
    "AccessibilityIssue",
    "audit_accessible_widgets",
    "focus_chain_names",
    "scaled_metric",
    "set_accessible",
]
