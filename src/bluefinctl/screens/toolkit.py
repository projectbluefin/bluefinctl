"""Toolkit screen — kit management.

TabbedContent with one tab: Kits.
Individual package installation lives in the Command Palette (Ctrl+P).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Label, Static

from bluefinctl.screens._sidebar import Sidebar


class ToolkitScreen(Screen[None]):
    """Kit management screen — two-column kit list with detail pane."""

    DEFAULT_CSS = """
    ToolkitScreen {
        layout: horizontal;
        height: 1fr;
    }
    #toolkit-content {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
    }
    .card {
        border: round $border;
        padding: 1 2;
        margin: 1 0;
        background: $surface;
    }
    .card--title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Sidebar(active="toolkit")
        with ScrollableContainer(id="toolkit-content"):
            yield Label("Toolkit", classes="card--title")
            yield Label("")
            with Static(classes="card"):
                yield Label("Kits", classes="card--title")
                yield Label(
                    "  Kit management coming soon.\n"
                    "  Kits are read from /usr/share/ublue-os/homebrew/*.Brewfile\n"
                    "\n"
                    "  Ctrl+P: install/search packages | Enter: activate kit | r: refresh",
                )
