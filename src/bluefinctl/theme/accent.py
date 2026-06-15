"""GNOME accent color reader and theme builder.

Reads the current GNOME accent color and color-scheme from gsettings and
constructs Textual Theme objects that match the GNOME libadwaita palette.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from textual.theme import Theme

# GNOME 47+ accent color name → (dark_hex, light_hex) mapping
# Dark mode: Blue 3 family; Light mode: Blue 4 family (darker for WCAG contrast)
ACCENT_COLORS: dict[str, tuple[str, str]] = {
    "blue":   ("#3584e4", "#1c71d8"),
    "teal":   ("#2190a4", "#0f7282"),
    "green":  ("#3a944a", "#2a7a3b"),
    "yellow": ("#c88800", "#b07400"),
    "orange": ("#ed5b00", "#c84e00"),
    "red":    ("#e62d42", "#c01c28"),
    "pink":   ("#d56199", "#b34d80"),
    "purple": ("#9141ac", "#7a2f94"),
    "slate":  ("#6f8396", "#5a6f80"),
}

# Default if gsettings is unavailable
DEFAULT_ACCENT = "blue"

# GNOME dark palette (exact GNOME HIG Dark 4/3/2)
_DARK = {
    "background": "#241f31",   # Dark 4
    "surface":    "#3d3846",   # Dark 3
    "panel":      "#5e5c64",   # Dark 2
    "boost":      "#ffffff",
    "success":    "#33d17a",   # Green 3
    "warning":    "#e5a50a",   # Yellow 5
    "error":      "#ed333b",   # Red 2
}

# GNOME light palette (exact GNOME HIG Light 2/1/3)
_LIGHT = {
    "background": "#f6f5f4",   # Light 2
    "surface":    "#ffffff",   # Light 1
    "panel":      "#deddda",   # Light 3
    "boost":      "#241f31",   # Dark 4
    "success":    "#26a269",   # Green 5
    "warning":    "#c64600",   # Orange 5
    "error":      "#c01c28",   # Red 4
}


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
            color = result.stdout.strip().strip("'\"")
            if color in ACCENT_COLORS:
                return color
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return DEFAULT_ACCENT


def get_accent_hex() -> str:
    """Get the current accent color as a hex value (dark-mode shade)."""
    return ACCENT_COLORS[get_accent_color()][0]


@lru_cache(maxsize=1)
def get_color_scheme() -> Literal["dark", "light"]:
    """Read org.gnome.desktop.interface color-scheme.

    Returns 'dark' if prefer-dark, 'light' for default/prefer-light.
    Falls back to 'dark' if gsettings is unavailable.
    """
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            value = result.stdout.strip().strip("'\"")
            return "dark" if value == "prefer-dark" else "light"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return "dark"


def build_theme(
    scheme: Literal["dark", "light"],
    accent_name: str = DEFAULT_ACCENT,
) -> Theme:
    """Build a Textual Theme matching the GNOME libadwaita palette.

    Args:
        scheme: 'dark' or 'light' — maps to GNOME color-scheme preference.
        accent_name: GNOME accent color name (e.g. 'blue', 'purple').

    Returns:
        A Textual Theme ready for registration and use.
    """
    from textual.theme import Theme

    palette = _DARK if scheme == "dark" else _LIGHT
    shade_idx = 0 if scheme == "dark" else 1
    accent_hex = ACCENT_COLORS.get(accent_name, ACCENT_COLORS[DEFAULT_ACCENT])[shade_idx]

    return Theme(
        name=f"bluefin-{scheme}",
        primary=accent_hex,
        accent=accent_hex,
        background=palette["background"],
        surface=palette["surface"],
        panel=palette["panel"],
        boost=palette["boost"],
        success=palette["success"],
        warning=palette["warning"],
        error=palette["error"],
        dark=scheme == "dark",
    )


def get_accent_css_vars() -> str:
    """Generate CSS variable declarations for the accent color (legacy)."""
    color = get_accent_color()
    hex_val = ACCENT_COLORS[color][0]
    return f"""$accent: {hex_val};
$accent-name: {color};
"""
