"""Shared sidebar navigation widget."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, Static


NAV_ITEMS = [
    ("1", "system", "System"),
    ("2", "bundles", "Bundles"),
    ("3", "packages", "Packages"),
    ("4", "updates", "Updates"),
    ("5", "containers", "Containers"),
]


class Sidebar(Static):
    """Left navigation sidebar — shared across all screens."""

    DEFAULT_CSS = """
    Sidebar {
        width: 22;
        background: $surface;
        border-right: thick $border;
        padding: 1 0;
    }
    """

    def __init__(self, active: str = "system") -> None:
        super().__init__()
        self._active = active

    def compose(self) -> ComposeResult:
        with Vertical():
            # App title
            yield Label(" 🐟 bluefinctl", id="sidebar-title")
            yield Label("", classes="sidebar--spacer")

            for key, slug, name in NAV_ITEMS:
                is_active = slug == self._active
                indicator = "●" if is_active else " "
                css_class = "sidebar--item -active" if is_active else "sidebar--item"
                yield Label(f" {indicator} [{key}] {name}", classes=css_class)
