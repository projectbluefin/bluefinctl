"""AdwViewSwitcher — horizontal top-navigation bar.

Replaces the vertical sidebar with a compact horizontal tab strip that
matches the libadwaita AdwViewSwitcher pattern: all top-level views sit
in a single row, the active view is highlighted with an accent tint, and
clicking any tab switches the screen instantly.

Number-key bindings and the Command Palette still work as before.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

NAV_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("system",  "System",  "1"),
    ("updates", "Updates", "2"),
    ("toolkit", "Toolkit", "3"),
    ("devmode", "DevMode", "4"),
    ("ai",      "AI",      "5"),
)


class ViewSwitcherTab(Static):
    """A single tab in the ViewSwitcher."""

    DEFAULT_CSS = """
    ViewSwitcherTab {
        width: 1fr;
        height: 3;
        content-align: center middle;
        color: $text-muted;
    }
    ViewSwitcherTab:hover {
        background: $panel;
        color: $text;
    }
    ViewSwitcherTab.-active {
        color: $accent;
        text-style: bold;
        background: $accent 12%;
    }
    """

    def __init__(self, slug: str, name: str, key: str, active: bool = False) -> None:
        super().__init__()
        self._slug = slug
        self._tab_name = name
        self._key = key
        if active:
            self.add_class("-active")

    def render(self) -> str:
        return self._tab_name

    def on_click(self) -> None:
        self.app.action_goto(self._slug)  # type: ignore[attr-defined]


class ViewSwitcher(Horizontal):
    """Full-width horizontal navigation bar (libadwaita AdwViewSwitcher).

    Place as the first child of a Screen with ``layout: vertical`` (default).
    Active tab is accent-tinted; clicking any tab calls ``app.action_goto``.
    """

    DEFAULT_CSS = """
    ViewSwitcher {
        height: 3;
        width: 1fr;
        background: $surface;
        border-bottom: solid $panel;
    }
    """

    def __init__(self, active: str = "system") -> None:
        super().__init__()
        self._active = active

    def compose(self) -> ComposeResult:
        for slug, name, key in NAV_ITEMS:
            yield ViewSwitcherTab(slug, name, key, active=(slug == self._active))
