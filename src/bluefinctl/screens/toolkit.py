"""Toolkit screen — software kit management.

Two-column layout: bundle list on the left, detail pane on the right.
Kits are Brewfile bundles from /usr/share/ublue-os/homebrew/.
"""

from __future__ import annotations

from typing import Any

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button, Footer, Label, ListItem, ListView

from bluefinctl.screens._viewswitcher import ViewSwitcher
from bluefinctl.widgets.ops_bar import OpsBar


class ToolkitScreen(Screen[None]):
    """Toolkit — browse, activate, and deactivate software kits."""

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    ToolkitScreen { layout: vertical; overflow: hidden hidden; }
    #kit-layout { height: 1fr; }
    #kit-list-col {
        width: 36;
        border-right: solid $panel;
    }
    #kit-list { height: 1fr; }
    #kit-detail-col {
        width: 1fr;
        padding: 1 2;
    }
    #kit-name {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }
    #kit-description { margin-bottom: 1; color: $text-muted; }
    #kit-status { margin-bottom: 1; }
    #kit-packages { margin-bottom: 1; color: $text-muted; }
    #kit-action { height: auto; align: left middle; }
    ToolkitScreen Footer { dock: none; height: 1; background: $panel; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._bundles: list[Any] = []
        self._selected: int = -1

    def compose(self) -> ComposeResult:
        yield ViewSwitcher("toolkit")
        with Horizontal(id="kit-layout"):
            with ScrollableContainer(id="kit-list-col"):
                yield ListView(id="kit-list")
            with ScrollableContainer(id="kit-detail-col"):
                yield Label("Select a kit", id="kit-name")
                yield Label("", id="kit-description")
                yield Label("", id="kit-status")
                yield Label("", id="kit-packages")
                with Horizontal(id="kit-action"):
                    yield Button("Activate", id="btn-kit-action", variant="primary")
        yield Footer()
        yield OpsBar()

    def on_mount(self) -> None:
        self._load()

    @work(exclusive=True)
    async def _load(self) -> None:
        from bluefinctl.core.bundles import get_bundles
        self._bundles = await get_bundles()
        kit_list = self.query_one("#kit-list", ListView)
        kit_list.clear()
        for b in self._bundles:
            label = f" [{b.state_indicator}] {b.name:<26} {b.installed_count}/{b.total_count}"
            kit_list.append(ListItem(Label(label), name=b.meta.slug))
        if self._bundles and self._selected < 0:
            self._show_detail(0)

    def _show_detail(self, index: int) -> None:
        if index < 0 or index >= len(self._bundles):
            return
        self._selected = index
        from bluefinctl.core.bundles import BundleState
        b = self._bundles[index]

        self.query_one("#kit-name", Label).update(b.name)
        self.query_one("#kit-description", Label).update(b.meta.description)

        status_text = {
            BundleState.BASE:      "Base — always installed with Bluefin",
            BundleState.ACTIVE:    f"Active — all {b.total_count} packages installed",
            BundleState.PARTIAL:   (
                f"Partial — {b.installed_count} of {b.total_count} packages installed"
            ),
            BundleState.AVAILABLE: f"Available — {b.total_count} packages",
        }.get(b.state, b.state.value)
        self.query_one("#kit-status", Label).update(status_text)

        pkg_preview = ", ".join(b.packages[:8])
        if len(b.packages) > 8:
            pkg_preview += f" … +{len(b.packages) - 8} more"
        self.query_one("#kit-packages", Label).update(pkg_preview)

        btn = self.query_one("#btn-kit-action", Button)
        if b.state == BundleState.BASE:
            btn.label = "Base (cannot remove)"
            btn.variant = "default"
            btn.disabled = True
        elif b.state in (BundleState.ACTIVE, BundleState.PARTIAL):
            btn.label = "Deactivate"
            btn.variant = "warning"
            btn.disabled = False
        else:
            btn.label = "Activate"
            btn.variant = "primary"
            btn.disabled = False

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id == "kit-list" and event.item is not None:
            index = event.list_view.index
            if index is not None:
                self._show_detail(index)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-kit-action":
            self._toggle_kit()

    @work(exclusive=True)
    async def _toggle_kit(self) -> None:
        from bluefinctl.core.bundles import (
            BundleState,
            activate_bundle_steps,
            deactivate_bundle_steps,
        )
        if self._selected < 0 or self._selected >= len(self._bundles):
            return
        b = self._bundles[self._selected]
        ops = self.query_one(OpsBar)

        try:
            if b.state in (BundleState.ACTIVE, BundleState.PARTIAL):
                ops.set_running(f"Removing {b.name}…")
                async for update in deactivate_bundle_steps(b.meta.slug):
                    ops.set_running(
                        update.message,
                        step=update.step or 0,
                        total=update.total_steps or 0,
                    )
                ops.set_complete(f"Kit '{b.name}' deactivated")
            else:
                ops.set_running(f"Installing {b.name}…")
                async for update in activate_bundle_steps(b.meta.slug):
                    ops.set_running(
                        update.message,
                        step=update.step or 0,
                        total=update.total_steps or 0,
                    )
                ops.set_complete(f"Kit '{b.name}' activated")
        except (FileNotFoundError, RuntimeError) as e:
            ops.set_error(str(e))
            return

        # Reload kit list after change
        self._load()

    def action_refresh(self) -> None:
        """Reload kit list from disk."""
        self._selected = -1
        self._load()
