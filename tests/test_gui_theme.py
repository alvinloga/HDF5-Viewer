"""Theme-token, metric, typography, and icon contract tests for DV-0601."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from data_viewer.gui.theme import (
    ColorRole,
    IconName,
    ThemeMode,
    build_application_stylesheet,
    contrast_ratio,
    default_metrics,
    default_palette,
    icon_definition,
    load_icon,
    scan_ui_token_violations,
    typography_tokens,
    validate_palette,
)


REQUIRED_COLOR_ROLES = {
    "canvas",
    "surface",
    "raised_surface",
    "input",
    "hover",
    "pressed",
    "selected",
    "border",
    "strong_border",
    "text_primary",
    "text_secondary",
    "text_disabled",
    "accent",
    "focus",
    "success",
    "warning",
    "error",
    "info",
    "dirty",
    "read_only",
    "comparison_a",
    "comparison_b",
}


def test_light_and_dark_palettes_cover_required_semantic_roles() -> None:
    """Every UI/UX required color role is centralized in both palettes."""

    for mode in ThemeMode:
        palette = default_palette(mode)

        assert {role.value for role in palette.colors} == REQUIRED_COLOR_ROLES
        assert validate_palette(palette) == []


def test_theme_text_and_focus_contrast_meet_desktop_accessibility_targets() -> None:
    """Text and focus tokens must be legible against ordinary shell surfaces."""

    for mode in ThemeMode:
        palette = default_palette(mode)
        for background in (
            ColorRole.CANVAS,
            ColorRole.SURFACE,
            ColorRole.RAISED_SURFACE,
            ColorRole.INPUT,
        ):
            assert (
                contrast_ratio(
                    palette[ColorRole.TEXT_PRIMARY],
                    palette[background],
                )
                >= 4.5
            )
            assert (
                contrast_ratio(
                    palette[ColorRole.TEXT_SECONDARY],
                    palette[background],
                )
                >= 4.5
            )
            assert contrast_ratio(palette[ColorRole.FOCUS], palette[background]) >= 3.0


def test_metrics_follow_four_pixel_compact_desktop_scale() -> None:
    """Metrics encode the compact Qt workbench scale from the UI specification."""

    metrics = default_metrics()

    assert metrics.base_unit_px == 4
    assert metrics.spacing_px == (4, 8, 12, 16, 24, 32)
    assert all(value % metrics.base_unit_px == 0 for value in metrics.spacing_px)
    assert metrics.control_height_compact_px == 28
    assert metrics.control_height_standard_px == 32
    assert metrics.control_height_prominent_px == 36
    assert metrics.control_radius_px == 4
    assert metrics.surface_radius_px == 6


def test_typography_uses_platform_ui_and_monospace_roles(qapp: QApplication) -> None:
    """Typography tokens come from Qt/platform font roles, not hard-coded web fonts."""

    typography = typography_tokens(qapp)

    assert typography.ui_family
    assert typography.monospace_family
    assert typography.body_point_size >= 9
    assert typography.small_point_size <= typography.body_point_size
    assert typography.monospace_family != typography.ui_family


def test_icon_family_is_monochrome_svg_with_accessible_names(
    qapp: QApplication,
) -> None:
    """Icons are bundled SVG definitions, not emoji or Unicode pseudo-icons."""

    seen_svg_names: set[str] = set()
    for name in IconName:
        definition = icon_definition(name)
        svg = definition.svg
        seen_svg_names.add(definition.svg_name)

        assert definition.accessible_name
        assert "<title " in svg
        assert "currentColor" in svg
        assert "fill=\"none\"" in svg
        assert "stroke=\"currentColor\"" in svg
        assert not any(ord(char) > 127 for char in definition.svg_name)
        assert not load_icon(name, color="#2563eb").isNull()

    assert len(seen_svg_names) == len(IconName)


def test_stylesheet_is_generated_from_theme_tokens_only() -> None:
    """The application stylesheet should be derived from the semantic theme map."""

    palette = default_palette(ThemeMode.LIGHT)
    stylesheet = build_application_stylesheet(palette, default_metrics())

    assert "#2563eb" in stylesheet
    assert "QPushButton:focus" in stylesheet
    assert "QTableView" in stylesheet
    assert "border-radius: 4px" in stylesheet


def test_gui_sources_do_not_scatter_palette_or_pseudo_icon_values() -> None:
    """Component files must use theme/icon APIs instead of hard-coded colors or emoji."""

    violations = scan_ui_token_violations(
        Path("data_viewer/gui"),
        exclude_names={"theme.py"},
    )

    assert violations == []
