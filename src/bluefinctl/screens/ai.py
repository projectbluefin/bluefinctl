"""AI screen — GPU-accelerated AI stack management.

TabbedContent with 2 tabs: Stacks (default), Tools.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Label, Static

from bluefinctl.screens._sidebar import Sidebar


class AIScreen(Screen[None]):
    """AI workstation management — stack catalog and tools."""

    DEFAULT_CSS = """
    AIScreen {
        layout: horizontal;
        height: 1fr;
    }
    #ai-content {
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
        yield Sidebar(active="ai")
        with ScrollableContainer(id="ai-content"):
            yield Label("AI Workstation", classes="card--title")
            yield Label("")
            with Static(classes="card"):
                yield Label("GPU Detection", classes="card--title")
                yield Label("  Detecting GPU...")
            yield Label("")
            with Static(classes="card"):
                yield Label("Stacks", classes="card--title")
                yield Label(
                    "  AI stack catalog coming soon.\n"
                    "  Stacks read from /usr/share/ublue-os/{nvidia,amd}-stacks/\n"
                    "\n"
                    "  Enter: deploy | s: stop | l: logs | f: filter",
                )
