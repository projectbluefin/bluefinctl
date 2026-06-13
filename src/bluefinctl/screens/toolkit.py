"""Toolkit screen — kit management.

Two-column layout: kit list (left) + detail pane (right).
Kits are curated Brewfile collections read from
/usr/share/ublue-os/homebrew/*.Brewfile.

Individual package installation lives in Command Palette (Ctrl+P).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Static

from bluefinctl.screens._sidebar import Sidebar


class KitDetailPane(Static):
    """Right-side detail pane showing selected kit info."""

    DEFAULT_CSS = """
    KitDetailPane {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
        border-left: solid $border;
    }
    #kit-detail-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Select a kit", id="kit-detail-title")
        yield Label("", id="kit-detail-body")

    def show_kit(
        self,
        name: str,
        description: str,
        packages: list[str],
        installed_count: int,
        total_count: int,
        state: str,
    ) -> None:
        """Update the detail pane with kit information."""
        self.query_one("#kit-detail-title", Label).update(name)

        # Build package list with install status
        pkg_lines: list[str] = []
        for pkg in packages[:20]:  # show first 20
            pkg_lines.append(f"    {pkg}")
        if len(packages) > 20:
            pkg_lines.append(f"    ... and {len(packages) - 20} more")

        body = (
            f"  {description}\n"
            f"\n"
            f"  Status: {state}\n"
            f"  Packages: {installed_count}/{total_count} installed\n"
            f"\n"
            f"  Packages:\n" + "\n".join(pkg_lines)
        )
        self.query_one("#kit-detail-body", Label).update(body)


class ToolkitScreen(Screen[None]):
    """Kit management screen — two-column kit list with detail pane."""

    BINDINGS = [
        Binding("enter", "activate_kit", "Activate"),
        Binding("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    ToolkitScreen {
        layout: horizontal;
    }
    #toolkit-main {
        width: 1fr;
        height: 1fr;
    }
    #toolkit-cols {
        height: 1fr;
    }
    #kit-list-container {
        width: 40;
        height: 1fr;
        padding: 1 0;
    }
    #kit-list {
        height: 1fr;
    }
    #kit-list-header {
        padding: 0 2;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._bundles: list = []

    def compose(self) -> ComposeResult:
        yield Sidebar(active="toolkit")
        with Vertical(id="toolkit-main"):
            yield Label(
                "  Ctrl+P: install/search packages | Enter: activate kit | r: refresh",
                id="toolkit-footer-hint",
            )
            with Horizontal(id="toolkit-cols"):
                with Vertical(id="kit-list-container"):
                    yield Label("Kits", id="kit-list-header")
                    yield ListView(id="kit-list")
                yield KitDetailPane()

    def on_mount(self) -> None:
        self.run_worker(self._load_kits())

    async def _load_kits(self) -> None:
        """Load kit data from system Brewfiles."""
        from bluefinctl.core.bundles import get_bundles

        self._bundles = await get_bundles()
        kit_list = self.query_one("#kit-list", ListView)
        kit_list.clear()

        for bundle in self._bundles:
            state_badge = {
                "base": "[base]",
                "active": "[active]",
                "partial": "[partial]",
                "available": "[available]",
            }.get(bundle.state.value, "")

            label = (
                f"  {bundle.meta.icon} {bundle.name:<22} "
                f"{bundle.total_count:>3} tools  {state_badge}"
            )
            kit_list.append(ListItem(Label(label), name=bundle.meta.slug))

        # Show first kit details
        if self._bundles:
            self._show_bundle_detail(0)

    def _show_bundle_detail(self, index: int) -> None:
        """Show details for the bundle at the given index."""
        if index < 0 or index >= len(self._bundles):
            return
        bundle = self._bundles[index]
        detail = self.query_one(KitDetailPane)
        detail.show_kit(
            name=bundle.name,
            description=bundle.meta.description,
            packages=bundle.packages,
            installed_count=bundle.installed_count,
            total_count=bundle.total_count,
            state=bundle.state.value.capitalize(),
        )

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update detail pane when list selection changes."""
        if event.item is not None:
            index = event.item.parent.children.index(event.item)  # type: ignore[union-attr]
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
            # Deactivate
            confirmed = await self.app.push_screen_wait(
                ConfirmModal(
                    f"Deactivate {bundle.name}?",
                    f"Remove packages unique to this kit "
                    f"({bundle.total_count} packages total).",
                ),
            )
            if confirmed:
                from bluefinctl.core.progress import BrewInstallParser

                rc = await self.app.push_screen_wait(
                    OperationModal(
                        f"Deactivating {bundle.name}",
                        command=[
                            "brew", "bundle", "cleanup",
                            f"--file=/usr/share/ublue-os/homebrew/{bundle.meta.slug}.Brewfile",
                            "--force",
                        ],
                        parser=BrewInstallParser(),
                    ),
                )
                if rc == 0:
                    self.notify(f"{bundle.name} deactivated", title="Toolkit")
                    self.run_worker(self._load_kits())
        else:
            # Activate
            confirmed = await self.app.push_screen_wait(
                ConfirmModal(
                    f"Activate {bundle.name}?",
                    f"Install {bundle.total_count} packages via Homebrew.",
                ),
            )
            if confirmed:
                from bluefinctl.core.progress import BrewInstallParser

                rc = await self.app.push_screen_wait(
                    OperationModal(
                        f"Activating {bundle.name}",
                        command=[
                            "brew", "bundle", "install",
                            f"--file=/usr/share/ublue-os/homebrew/{bundle.meta.slug}.Brewfile",
                        ],
                        parser=BrewInstallParser(total_packages=bundle.total_count),
                    ),
                )
                if rc == 0:
                    self.notify(f"{bundle.name} activated", title="Toolkit")
                    self.run_worker(self._load_kits())

    def action_refresh(self) -> None:
        """Reload kit state."""
        self.run_worker(self._load_kits())
        self.notify("Refreshing kits...", title="Toolkit")
