"""DevMode screen — developer experience panel.

TabbedContent with 3 tabs: Overview, Tools, Environments.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Label, Static

from bluefinctl.screens._sidebar import Sidebar


class DevModeScreen(Screen[None]):
    """Developer mode screen — tools, environments, Lima."""

    DEFAULT_CSS = """
    DevModeScreen {
        layout: horizontal;
        height: 1fr;
    }
    #devmode-content {
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
        yield Sidebar(active="devmode")
        with ScrollableContainer(id="devmode-content"):
            yield Label("Developer Mode", classes="card--title")
            yield Label("")
            with Static(classes="card"):
                yield Label("Overview", classes="card--title")
                yield Label(
                    "  Developer Mode: checking status...\n"
                    "\n"
                    "  Runtime Health:\n"
                    "    [--] Docker    [--] Podman    [--] Lima\n"
                    "\n"
                    "  Quick Actions:\n"
                    "    [c] podman-tui    [v] VSCode    [l] Lima shell",
                )
