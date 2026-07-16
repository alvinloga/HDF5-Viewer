"""Semantic Qt theme tokens, compact metrics, and bundled SVG icons.

DV-0601 intentionally creates a small design-system foundation before broad
screen restyling. Widgets should depend on these semantic tokens instead of
scattering palette values, pseudo-icons, or ad-hoc geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
import re
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication


class ThemeMode(StrEnum):
    """Supported first-release theme variants."""

    LIGHT = "light"
    DARK = "dark"


class ColorRole(StrEnum):
    """Semantic color roles required by the UI/UX specification."""

    CANVAS = "canvas"
    SURFACE = "surface"
    RAISED_SURFACE = "raised_surface"
    INPUT = "input"
    HOVER = "hover"
    PRESSED = "pressed"
    SELECTED = "selected"
    BORDER = "border"
    STRONG_BORDER = "strong_border"
    TEXT_PRIMARY = "text_primary"
    TEXT_SECONDARY = "text_secondary"
    TEXT_DISABLED = "text_disabled"
    ACCENT = "accent"
    FOCUS = "focus"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"
    DIRTY = "dirty"
    READ_ONLY = "read_only"
    COMPARISON_A = "comparison_a"
    COMPARISON_B = "comparison_b"


@dataclass(frozen=True, slots=True)
class ThemePalette:
    """One complete semantic palette for a theme mode."""

    mode: ThemeMode
    colors: dict[ColorRole, str]

    def __getitem__(self, role: ColorRole) -> str:
        return self.colors[role]


@dataclass(frozen=True, slots=True)
class MetricTokens:
    """Compact desktop geometry tokens for the Data Viewer shell."""

    base_unit_px: int
    spacing_px: tuple[int, ...]
    control_height_compact_px: int
    control_height_standard_px: int
    control_height_prominent_px: int
    row_height_min_px: int
    row_height_max_px: int
    control_radius_px: int
    surface_radius_px: int
    divider_px: int
    focus_ring_px: int


@dataclass(frozen=True, slots=True)
class TypographyTokens:
    """Qt/platform typography roles."""

    ui_family: str
    monospace_family: str
    body_point_size: int
    small_point_size: int
    heading_point_size: int


class IconName(StrEnum):
    """Bundled monochrome icon names."""

    OPEN = "open"
    SAVE = "save"
    SAVE_AS = "save_as"
    EXPORT = "export"
    CANCEL = "cancel"
    SEARCH = "search"
    STRUCTURE = "structure"
    WORKSPACE = "workspace"
    PLUGINS = "plugins"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    READ_ONLY = "read_only"
    DIRTY = "dirty"
    LOADING = "loading"


@dataclass(frozen=True, slots=True)
class IconDefinition:
    """Accessible SVG icon definition."""

    name: IconName
    svg_name: str
    accessible_name: str
    svg: str


_LIGHT_COLORS: dict[ColorRole, str] = {
    ColorRole.CANVAS: "#f8fafc",
    ColorRole.SURFACE: "#ffffff",
    ColorRole.RAISED_SURFACE: "#f1f5f9",
    ColorRole.INPUT: "#ffffff",
    ColorRole.HOVER: "#e2e8f0",
    ColorRole.PRESSED: "#cbd5e1",
    ColorRole.SELECTED: "#dbeafe",
    ColorRole.BORDER: "#cbd5e1",
    ColorRole.STRONG_BORDER: "#94a3b8",
    ColorRole.TEXT_PRIMARY: "#0f172a",
    ColorRole.TEXT_SECONDARY: "#334155",
    ColorRole.TEXT_DISABLED: "#64748b",
    ColorRole.ACCENT: "#2563eb",
    ColorRole.FOCUS: "#2563eb",
    ColorRole.SUCCESS: "#047857",
    ColorRole.WARNING: "#b45309",
    ColorRole.ERROR: "#b91c1c",
    ColorRole.INFO: "#0369a1",
    ColorRole.DIRTY: "#a16207",
    ColorRole.READ_ONLY: "#475569",
    ColorRole.COMPARISON_A: "#2563eb",
    ColorRole.COMPARISON_B: "#7c3aed",
}

_DARK_COLORS: dict[ColorRole, str] = {
    ColorRole.CANVAS: "#0b1120",
    ColorRole.SURFACE: "#111827",
    ColorRole.RAISED_SURFACE: "#1e293b",
    ColorRole.INPUT: "#0f172a",
    ColorRole.HOVER: "#1f2937",
    ColorRole.PRESSED: "#334155",
    ColorRole.SELECTED: "#1e3a8a",
    ColorRole.BORDER: "#334155",
    ColorRole.STRONG_BORDER: "#64748b",
    ColorRole.TEXT_PRIMARY: "#f8fafc",
    ColorRole.TEXT_SECONDARY: "#cbd5e1",
    ColorRole.TEXT_DISABLED: "#94a3b8",
    ColorRole.ACCENT: "#60a5fa",
    ColorRole.FOCUS: "#93c5fd",
    ColorRole.SUCCESS: "#34d399",
    ColorRole.WARNING: "#fbbf24",
    ColorRole.ERROR: "#f87171",
    ColorRole.INFO: "#38bdf8",
    ColorRole.DIRTY: "#facc15",
    ColorRole.READ_ONLY: "#cbd5e1",
    ColorRole.COMPARISON_A: "#60a5fa",
    ColorRole.COMPARISON_B: "#c084fc",
}


def default_palette(mode: ThemeMode) -> ThemePalette:
    """Return a complete built-in semantic palette."""

    colors = _LIGHT_COLORS if mode is ThemeMode.LIGHT else _DARK_COLORS
    return ThemePalette(mode=mode, colors=dict(colors))


def default_metrics() -> MetricTokens:
    """Return the compact 4 px scale from the UI/UX contract."""

    return MetricTokens(
        base_unit_px=4,
        spacing_px=(4, 8, 12, 16, 24, 32),
        control_height_compact_px=28,
        control_height_standard_px=32,
        control_height_prominent_px=36,
        row_height_min_px=26,
        row_height_max_px=30,
        control_radius_px=4,
        surface_radius_px=6,
        divider_px=1,
        focus_ring_px=2,
    )


def typography_tokens(app: QApplication | None = None) -> TypographyTokens:
    """Resolve platform UI and monospace font roles through Qt."""

    instance = app or QApplication.instance()
    ui_font = instance.font() if isinstance(instance, QApplication) else None
    ui_family = ui_font.family() if ui_font is not None else "system-ui"
    body_size = ui_font.pointSize() if ui_font is not None else 9
    if body_size <= 0:
        body_size = 9
    monospace = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    mono_family = monospace.family() or "monospace"
    if mono_family == ui_family:
        mono_family = "monospace"
    return TypographyTokens(
        ui_family=ui_family,
        monospace_family=mono_family,
        body_point_size=max(9, body_size),
        small_point_size=max(8, body_size - 1),
        heading_point_size=max(11, body_size + 2),
    )


def contrast_ratio(foreground: str, background: str) -> float:
    """Calculate WCAG contrast ratio between two hex colors."""

    fg = _relative_luminance(_hex_to_rgb(foreground))
    bg = _relative_luminance(_hex_to_rgb(background))
    lighter = max(fg, bg)
    darker = min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def validate_palette(palette: ThemePalette) -> list[str]:
    """Return human-readable palette contract violations."""

    violations: list[str] = []
    missing = set(ColorRole) - set(palette.colors)
    if missing:
        violations.append(
            "missing color roles: " + ", ".join(sorted(role.value for role in missing))
        )
    for role, value in palette.colors.items():
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            violations.append(f"{role.value} must be a 6-digit hex color")
    for background in (
        ColorRole.CANVAS,
        ColorRole.SURFACE,
        ColorRole.RAISED_SURFACE,
        ColorRole.INPUT,
    ):
        for foreground in (ColorRole.TEXT_PRIMARY, ColorRole.TEXT_SECONDARY):
            if contrast_ratio(palette[foreground], palette[background]) < 4.5:
                violations.append(
                    f"{foreground.value} contrast is too low on {background.value}"
                )
        if contrast_ratio(palette[ColorRole.FOCUS], palette[background]) < 3.0:
            violations.append(f"focus contrast is too low on {background.value}")
    return violations


def build_application_stylesheet(
    palette: ThemePalette,
    metrics: MetricTokens | None = None,
) -> str:
    """Build a compact Qt stylesheet from semantic theme tokens."""

    metrics = metrics or default_metrics()
    return f"""
QWidget {{
    background-color: {palette[ColorRole.CANVAS]};
    color: {palette[ColorRole.TEXT_PRIMARY]};
    selection-background-color: {palette[ColorRole.SELECTED]};
    selection-color: {palette[ColorRole.TEXT_PRIMARY]};
}}
QLineEdit, QPlainTextEdit, QTreeWidget, QTableView, QSpinBox {{
    background-color: {palette[ColorRole.INPUT]};
    color: {palette[ColorRole.TEXT_PRIMARY]};
    border: {metrics.divider_px}px solid {palette[ColorRole.BORDER]};
    border-radius: {metrics.control_radius_px}px;
}}
QPushButton {{
    min-height: {metrics.control_height_compact_px}px;
    padding: 0 {metrics.spacing_px[2]}px;
    background-color: {palette[ColorRole.SURFACE]};
    color: {palette[ColorRole.TEXT_PRIMARY]};
    border: {metrics.divider_px}px solid {palette[ColorRole.BORDER]};
    border-radius: {metrics.control_radius_px}px;
}}
QPushButton:hover {{
    background-color: {palette[ColorRole.HOVER]};
    border-color: {palette[ColorRole.STRONG_BORDER]};
}}
QPushButton:pressed {{
    background-color: {palette[ColorRole.PRESSED]};
}}
QPushButton:focus, QLineEdit:focus, QPlainTextEdit:focus, QTreeWidget:focus,
QTableView:focus, QSpinBox:focus {{
    border: {metrics.focus_ring_px}px solid {palette[ColorRole.FOCUS]};
}}
QPushButton:disabled {{
    color: {palette[ColorRole.TEXT_DISABLED]};
    background-color: {palette[ColorRole.RAISED_SURFACE]};
}}
QHeaderView::section {{
    background-color: {palette[ColorRole.RAISED_SURFACE]};
    color: {palette[ColorRole.TEXT_SECONDARY]};
    border: {metrics.divider_px}px solid {palette[ColorRole.BORDER]};
    min-height: {metrics.row_height_min_px}px;
}}
QStatusBar, QGroupBox {{
    background-color: {palette[ColorRole.SURFACE]};
}}
QSplitter::handle {{
    background-color: {palette[ColorRole.BORDER]};
}}
""".strip()


def apply_application_theme(
    app: QApplication,
    mode: ThemeMode = ThemeMode.LIGHT,
) -> ThemePalette:
    """Apply the built-in stylesheet to a QApplication and return its palette."""

    palette = default_palette(mode)
    app.setStyleSheet(build_application_stylesheet(palette, default_metrics()))
    return palette


def icon_definition(name: IconName) -> IconDefinition:
    """Return one bundled SVG definition."""

    accessible_name, body = _ICON_BODIES[name]
    svg_name = f"dv-line-{name.value}"
    return IconDefinition(
        name=name,
        svg_name=svg_name,
        accessible_name=accessible_name,
        svg=_svg(svg_name, accessible_name, body),
    )


def icon_svg(name: IconName, *, color: str = "currentColor") -> str:
    """Return SVG text for the requested icon."""

    return icon_definition(name).svg.replace("currentColor", color)


def load_icon(name: IconName, *, color: str) -> QIcon:
    """Load a bundled SVG icon into a Qt icon."""

    renderer = QSvgRenderer(QByteArray(icon_svg(name, color=color).encode("utf-8")))
    if not renderer.isValid():
        return QIcon()
    pixmap = QPixmap(20, 20)
    pixmap.fill(QColor(Qt.GlobalColor.transparent))
    painter = QPainter(pixmap)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    return QIcon(pixmap)


@dataclass(frozen=True, slots=True)
class UiTokenViolation:
    """Repository scan finding for scattered UI styling primitives."""

    path: Path
    line: int
    reason: str
    text: str


def scan_ui_token_violations(
    root: Path,
    *,
    exclude_names: set[str] | None = None,
) -> list[UiTokenViolation]:
    """Scan Python GUI sources for hard-coded colors or emoji-like pseudo-icons."""

    exclude_names = exclude_names or set()
    violations: list[UiTokenViolation] = []
    for path in sorted(root.rglob("*.py")):
        if path.name in exclude_names:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _RAW_COLOR_PATTERN.search(line):
                violations.append(
                    UiTokenViolation(path, line_number, "hard-coded color", line.strip())
                )
            if _EMOJI_PATTERN.search(line):
                violations.append(
                    UiTokenViolation(path, line_number, "emoji or pseudo-icon", line.strip())
                )
    return violations


def _svg(svg_name: str, title: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" '
        f'viewBox="0 0 20 20" role="img" aria-labelledby="{svg_name}-title" '
        f'fill="none" stroke="currentColor" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        f'<title id="{svg_name}-title">{title}</title>{body}</svg>'
    )


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"Expected #RRGGBB color, got {value!r}")
    return (
        int(value[1:3], 16) / 255,
        int(value[3:5], 16) / 255,
        int(value[5:7], 16) / 255,
    )


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    values = []
    for channel in rgb:
        if channel <= 0.03928:
            values.append(channel / 12.92)
        else:
            values.append(math.pow((channel + 0.055) / 1.055, 2.4))
    red, green, blue = values
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


_RAW_COLOR_PATTERN = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|QColor\s*\(|Qt\.GlobalColor|"
    r"\b(?:background-color|color|border-color)\s*:"
)
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f"
    "\U0001f780-\U0001f7ff"
    "\U0001f800-\U0001f8ff"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001faff"
    "\u2600-\u27bf"
    "]"
)


_ICON_BODIES: dict[IconName, tuple[str, str]] = {
    IconName.OPEN: (
        "Open file",
        '<path d="M3.5 6.5h5l1.5 2h6.5v7h-13z"/><path d="M3.5 6.5v-2h5l1.5 2"/>',
    ),
    IconName.SAVE: (
        "Save",
        '<path d="M4.5 3.5h9l2 2v11h-11z"/><path d="M7 3.5v5h6"/><path d="M7 16v-4h6v4"/>',
    ),
    IconName.SAVE_AS: (
        "Save as",
        '<path d="M4.5 3.5h8l2 2v4"/><path d="M7 3.5v5h5"/><path d="M5 16.5h5"/><path d="M13 12.5l3 3"/><path d="M16 12.5l-3 3"/>',
    ),
    IconName.EXPORT: (
        "Export",
        '<path d="M4 14.5v2h12v-2"/><path d="M10 3.5v9"/><path d="M6.5 9l3.5 3.5 3.5-3.5"/>',
    ),
    IconName.CANCEL: (
        "Cancel",
        '<circle cx="10" cy="10" r="6.5"/><path d="M7.5 7.5l5 5"/><path d="M12.5 7.5l-5 5"/>',
    ),
    IconName.SEARCH: (
        "Search",
        '<circle cx="8.5" cy="8.5" r="5"/><path d="M12.2 12.2l4 4"/>',
    ),
    IconName.STRUCTURE: (
        "Structure",
        '<path d="M5 4.5h4v4H5z"/><path d="M11 11.5h4v4h-4z"/><path d="M7 8.5v3h4"/><path d="M9 6.5h4v3"/>',
    ),
    IconName.WORKSPACE: (
        "Workspace",
        '<path d="M3.5 4.5h13v11h-13z"/><path d="M8 4.5v11"/><path d="M8 9h8.5"/>',
    ),
    IconName.PLUGINS: (
        "Plugins",
        '<path d="M7 3.5v4"/><path d="M13 3.5v4"/><path d="M5.5 7.5h9v3a4.5 4.5 0 0 1-9 0z"/><path d="M10 15v2"/>',
    ),
    IconName.INFO: (
        "Information",
        '<circle cx="10" cy="10" r="6.5"/><path d="M10 9v4"/><path d="M10 6.8v.2"/>',
    ),
    IconName.WARNING: (
        "Warning",
        '<path d="M10 3.5l7 12h-14z"/><path d="M10 8v3.5"/><path d="M10 14v.1"/>',
    ),
    IconName.ERROR: (
        "Error",
        '<circle cx="10" cy="10" r="6.5"/><path d="M10 6.5v5"/><path d="M10 14v.1"/>',
    ),
    IconName.READ_ONLY: (
        "Read-only",
        '<path d="M5 8.5v-2a5 5 0 0 1 10 0v2"/><path d="M4.5 8.5h11v7h-11z"/>',
    ),
    IconName.DIRTY: (
        "Unsaved changes",
        '<path d="M4 14.5l1.5-4.5 7-7 4.5 4.5-7 7z"/><path d="M11.5 4l4.5 4.5"/>',
    ),
    IconName.LOADING: (
        "Loading",
        '<path d="M10 3.5a6.5 6.5 0 1 1-6.1 4.3"/><path d="M3.5 4v4h4"/>',
    ),
}


__all__ = [
    "ColorRole",
    "IconDefinition",
    "IconName",
    "MetricTokens",
    "ThemeMode",
    "ThemePalette",
    "TypographyTokens",
    "UiTokenViolation",
    "apply_application_theme",
    "build_application_stylesheet",
    "contrast_ratio",
    "default_metrics",
    "default_palette",
    "icon_definition",
    "icon_svg",
    "load_icon",
    "scan_ui_token_violations",
    "typography_tokens",
    "validate_palette",
]
