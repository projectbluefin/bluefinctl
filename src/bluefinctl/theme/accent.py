"""GNOME accent color reader.

Reads the current GNOME accent color from gsettings and maps it
to a hex color value for use in Textual CSS theming.
"""

import subprocess
from functools import lru_cache

# GNOME 47+ accent color name → hex mapping
# Matches the palette from gnome-desktop/libadwaita
ACCENT_COLORS: dict[str, str] = {
    "blue": "#3584e4",
    "teal": "#2190a4",
    "green": "#3a944a",
    "yellow": "#c88800",
    "orange": "#ed5b00",
    "red": "#e62d42",
    "pink": "#d56199",
    "purple": "#9141ac",
    "slate": "#6f8396",
}

# Default if we can't read gsettings
DEFAULT_ACCENT = "blue"


@lru_cache(maxsize=1)
def get_accent_color() -> str:
    """Get the current GNOME accent color name.

    Returns the color name (e.g., 'blue', 'purple') or DEFAULT_ACCENT
    if gsettings is unavailable.
    """
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "accent-color"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            # gsettings returns "'blue'" (with quotes)
            color = result.stdout.strip().strip("'\"")
            if color in ACCENT_COLORS:
                return color
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return DEFAULT_ACCENT


def get_accent_hex() -> str:
    """Get the current accent color as a hex value."""
    return ACCENT_COLORS[get_accent_color()]


def get_accent_css_vars() -> str:
    """Generate CSS variable declarations for the accent color."""
    color = get_accent_color()
    hex_val = ACCENT_COLORS[color]
    return f"""$accent: {hex_val};
$accent-name: {color};
"""
