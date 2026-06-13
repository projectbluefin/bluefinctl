"""Shared sidebar navigation widget.

Supports the new 5-screen architecture with visual separators between
screen groups. On non-bootc systems, System and Updates are hidden and
keys renumber accordingly.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, Static

# Full navigation for bootc systems
NAV_ITEMS_BOOTC = [
    ('1', 'system', 'System'),
    ('2', 'updates', 'Updates'),
    ('---',),  # separator after system group
    ('3', 'toolkit', 'Toolkit'),
    ('---',),  # separator after toolkit
    ('4', 'devmode', 'DevMode'),
    ('5', 'ai', 'AI'),
]

# Non-bootc systems: no System/Updates screens
NAV_ITEMS_GENERIC = [
    ('1', 'toolkit', 'Toolkit'),
    ('---',),  # separator after toolkit
    ('2', 'devmode', 'DevMode'),
    ('3', 'ai', 'AI'),
]


class NavItem(Static):
    """A clickable sidebar navigation item."""

    DEFAULT_CSS = """
    NavItem {
        height: 3;
        padding: 0 2;
        content-align: left middle;
    }
    NavItem:hover { background: $panel; }
    NavItem.-active {
        background: $accent 20%;
        border-left: thick $accent;
        text-style: bold;
    }
    """

    def __init__(self, key: str, slug: str, name: str, active: bool = False) -> None:
        super().__init__()
        self._key = key
        self._slug = slug
        self._name = name
        self._active = active
        if active:
            self.add_class('-active')

    def render(self) -> str:
        indicator = '*' if self._active else ' '
        return f' {indicator} [{self._key}] {self._name}'

    def on_click(self) -> None:
        self.app.action_goto(self._slug)  # type: ignore[attr-defined]


class NavSeparator(Static):
    """A visual separator between navigation groups."""

    DEFAULT_CSS = """
    NavSeparator {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    """

    def render(self) -> str:
        return "  ──────────────"


class Sidebar(Static):
    """Left navigation sidebar with visual group separators.

    Automatically adapts to bootc vs generic systems based on
    the app's `is_bootc` property.
    """

    DEFAULT_CSS = """
    Sidebar {
        width: 22;
        background: $surface;
        border-right: thick $panel;
        padding: 1 0;
    }
    #sidebar-title {
        padding: 1 2;
        color: $accent;
        text-style: bold;
    }
    """

    def __init__(self, active: str = 'system') -> None:
        super().__init__()
        self._active = active

    def compose(self) -> ComposeResult:
        # Determine which nav items to show
        try:
            is_bootc = self.app.is_bootc  # type: ignore[attr-defined]
        except (AttributeError, TypeError):
            is_bootc = True  # default to full nav

        nav_items = NAV_ITEMS_BOOTC if is_bootc else NAV_ITEMS_GENERIC

        with Vertical():
            yield Label(' bluefinctl', id='sidebar-title')
            yield Label('', id='sidebar-spacer')
            for item in nav_items:
                if item[0] == '---':
                    yield NavSeparator()
                else:
                    key, slug, name = item[0], item[1], item[2]
                    yield NavItem(key, slug, name, active=(slug == self._active))
