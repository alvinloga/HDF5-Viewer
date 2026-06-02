"""Theme — centralized theme color definitions for light and dark themes."""


_DARK_COLORS = {
    'bg_primary': '#1e1e1e',
    'bg_secondary': '#252526',
    'bg_tertiary': '#2d2d2d',
    'bg_activity_bar': '#333333',
    'bg_status_bar': '#007acc',
    'bg_hover': '#2a2d2e',
    'bg_selected': '#094771',
    'bg_input': '#3c3c3c',
    'bg_button': '#0e639c',
    'bg_button_hover': '#1177bb',
    'bg_tab': '#2d2d2d',
    'bg_tab_selected': '#1e1e1e',
    'bg_tab_hover': '#383838',
    'bg_alternate': '#252526',
    'bg_header': '#2d2d2d',
    'text_primary': '#cccccc',
    'text_secondary': '#969696',
    'text_header': '#bbbbbb',
    'text_selected': '#ffffff',
    'accent': '#0078d4',
    'border': '#333333',
    'border_input': '#555555',
    'border_header': '#1e1e1e',
}

_LIGHT_COLORS = {
    'bg_primary': '#ffffff',
    'bg_secondary': '#f3f3f3',
    'bg_tertiary': '#e8e8e8',
    'bg_activity_bar': '#f0f0f0',
    'bg_status_bar': '#007acc',
    'bg_hover': '#e0e0e0',
    'bg_selected': '#0060c0',
    'bg_input': '#ffffff',
    'bg_button': '#0078d4',
    'bg_button_hover': '#106ebe',
    'bg_tab': '#f3f3f3',
    'bg_tab_selected': '#ffffff',
    'bg_tab_hover': '#e8e8e8',
    'bg_alternate': '#f9f9f9',
    'bg_header': '#e8e8e8',
    'text_primary': '#333333',
    'text_secondary': '#666666',
    'text_header': '#555555',
    'text_selected': '#ffffff',
    'accent': '#0078d4',
    'border': '#e0e0e0',
    'border_input': '#cccccc',
    'border_header': '#e0e0e0',
}


def get_theme_colors(theme: str) -> dict:
    if theme == 'light':
        return _LIGHT_COLORS.copy()
    return _DARK_COLORS.copy()
