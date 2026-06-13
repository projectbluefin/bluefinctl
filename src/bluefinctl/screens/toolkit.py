"""Toolkit screen — kit management.

Two-column layout: kit list (left) + detail pane (right).
Kits are curated Brewfile collections read from
/usr/share/ublue-os/homebrew/*.Brewfile.

Individual package installation lives in Command Palette (Ctrl+P).
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Static

from bluefinctl.screens._sidebar import Sidebar


class KitDetailPane(Vertical):
    """Right-side detail pane: description, per-package install status, action button."""

    DEFAULT_CSS = """
    KitDetailPane {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
        border-left: solid $border;
    }
    #kit-detail-title { text-style: bold; color: $accent; }
    #kit-detail-desc  { color: $text-muted; margin-bottom: 1; }
    #kit-pkg-scroll   { height: 1fr; }
    #kit-pkg-list     { height: auto; }
    #kit-action-bar   { height: 3; align: left middle; margin-top: 1; }
    #kit-action-bar Button { margin-right: 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._bundle: Any = None
        self._installed: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Label("Select a kit →", id="kit-detail-title")
        yield Label("", id="kit-detail-desc")
        with ScrollableContainer(id="kit-pkg-scroll"):
            yield Static("", id="kit-pkg-list")
        with Horizontal(id="kit-action-bar"):
            yield Button("Activate", id="btn-kit-activate", variant="primary", disabled=True)
            yield Button("Deactivate", id="btn-kit-deactivate", variant="warning", disabled=True)

    def show_bundle(self, bundle: Any, installed: set[str]) -> None:
        """Render kit detail for the given bundle."""
        self._bundle = bundle
        self._installed = installed

        self.query_one("#kit-detail-title", Label).update(
            f"{bundle.meta.icon}  {bundle.name}"
        )
        self.query_one("#kit-detail-desc", Label).update(
            f"  {bundle.meta.description}\n"
            f"  {bundle.installed_count}/{bundle.total_count} installed"
            f"  ·  {bundle.state.value}"
        )

        lines = []
        for pkg in bundle.packages:
            indicator = "[green]✓[/green]" if pkg in installed else "[dim]·[/dim]"
            lines.append(f"  {indicator}  {pkg}")
        body = "\n".join(lines) if lines else "  No packages"
        self.query_one("#kit-pkg-list", Static).update(body)

        from bluefinctl.core.bundles import BundleState
        btn_activate = self.query_one("#btn-kit-activate", Button)
        btn_deactivate = self.query_one("#btn-kit-deactivate", Button)

        is_base = bundle.state == BundleState.BASE
        is_active = bundle.state in (BundleState.ACTIVE, BundleState.PARTIAL)
        is_available = bundle.state == BundleState.AVAILABLE

        btn_activate.disabled = is_base or is_active
        btn_deactivate.disabled = is_base or is_available

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("btn-kit-activate", "btn-kit-deactivate"):
            self.screen.action_activate_kit()  # type: ignore[attr-defined]


class ToolkitScreen(Screen[None]):
    """Kit management screen — two-column kit list with detail pane."""

    BINDINGS = [
        Binding("enter", "activate_kit", "Activate/Deactivate"),
        Binding("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    ToolkitScreen { layout: horizontal; }
    #toolkit-main  { width: 1fr; height: 1fr; padding: 1 1; }
    #toolkit-cols  { height: 1fr; }
    #kit-list-container { width: 42; height: 1fr; }
    #kit-list-header {
        padding: 0 1;
        text-style: bold;
        color: $accent;
    }
    #kit-list { height: 1fr; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._bundles: list[Any] = []
        self._installed: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Sidebar(active="toolkit")
        with Vertical(id="toolkit-main"):
            with Horizontal(id="toolkit-cols"):
                with Vertical(id="kit-list-container"):
                    yield Label("Kits", id="kit-list-header")
                    yield ListView(id="kit-list")
                yield KitDetailPane()

    def on_mount(self) -> None:
        self.run_worker(self._load_kits())

    async def _load_kits(self) -> None:
        """Load kit data from system Brewfiles."""
        import asyncio  # noqa: I001
        from bluefinctl.core.bundles import (
            _get_installed_flatpaks,
            _get_installed_formulae,
            get_bundles,
        )

        loop = asyncio.get_running_loop()
        self._bundles = await get_bundles()
        formulae = await loop.run_in_executor(None, _get_installed_formulae)
        flatpaks = await loop.run_in_executor(None, _get_installed_flatpaks)
        self._installed = formulae | flatpaks

        kit_list = self.query_one("#kit-list", ListView)
        kit_list.clear()

        for bundle in self._bundles:
            state_badge = {
                "base": " [base]",
                "active": " [active]",
                "partial": f" [{bundle.installed_count}/{bundle.total_count}]",
                "available": "",
            }.get(bundle.state.value, "")
            label = f"  {bundle.meta.icon}  {bundle.name:<24}{state_badge}"
            kit_list.append(ListItem(Label(label), name=bundle.meta.slug))

        if self._bundles:
            self._show_bundle_detail(0)

    def _show_bundle_detail(self, index: int) -> None:
        if index < 0 or index >= len(self._bundles):
            return
        self.query_one(KitDetailPane).show_bundle(self._bundles[index], self._installed)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is not None:
            index = event.list_view.index
            if index is not None:
                self._show_bundle_detail(index)

    async def action_activate_kit(self) -> None:
        """Activate or deactivate the selected kit."""
        from bluefinctl.core.bundles import BundleState
        from bluefinctl.screens._modals import ConfirmModal
        from bluefinctl.widgets.operation_modal import OperationModal

        kit_list = self.query_one("#kit-list", ListView)
        if kit_list.index is None or kit_list.index >= len(self._bundles):
            return

        bundle = self._bundles[kit_list.index]

        if bundle.state == BundleState.BASE:
            self.notify("Base kit cannot be deactivated", severity="warning")
            return

        if bundle.state in (BundleState.ACTIVE, BundleState.PARTIAL):
            from bluefinctl.core.bundles import deactivate_bundle_steps, preview_bundle_deactivation
            preview = await preview_bundle_deactivation(bundle.meta.slug)
            removable = ", ".join(preview.removable_packages[:12]) or "none"
            if len(preview.removable_packages) > 12:
                removable += f" +{len(preview.removable_packages) - 12} more"
            confirmed = await self.app.push_screen_wait(
                ConfirmModal(
                    f"Deactivate {bundle.name}?",
                    f"Will remove ({len(preview.removable_packages)}): {removable}",
                ),
            )
            if confirmed:
                rc = await self.app.push_screen_wait(
                    OperationModal(
                        f"Deactivating {bundle.name}",
                        steps=deactivate_bundle_steps(bundle.meta.slug),
                    ),
                )
                if rc == 0:
                    self.notify(f"{bundle.name} deactivated", title="Toolkit")
                    self.run_worker(self._load_kits())
        else:
            confirmed = await self.app.push_screen_wait(
                ConfirmModal(
                    f"Activate {bundle.name}?",
                    f"Install {bundle.total_count} packages via Homebrew.",
                ),
            )
            if confirmed:
                from bluefinctl.core.bundles import activate_bundle_steps
                rc = await self.app.push_screen_wait(
                    OperationModal(
                        f"Activating {bundle.name}",
                        steps=activate_bundle_steps(bundle.meta.slug),
                    ),
                )
                if rc == 0:
                    self.notify(f"{bundle.name} activated", title="Toolkit")
                    self.run_worker(self._load_kits())

    def action_refresh(self) -> None:
        self.run_worker(self._load_kits())
        self.notify("Refreshing kits...", title="Toolkit")

