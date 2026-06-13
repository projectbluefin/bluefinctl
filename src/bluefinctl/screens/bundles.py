"""Bundles screen — the loadout selector.

Shows all available bundles grouped by category.
Two-column layout: bundle list (left) + detail pane (right).
Users opt into bundles to shape their system's personality.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Static

from bluefinctl.screens._sidebar import Sidebar


class BundleDetail(Static):
    """Right pane — shows selected bundle's contents and status."""

    DEFAULT_CSS = """
    BundleDetail {
        width: 1fr;
        padding: 1 2;
        background: $surface;
        border-left: thick $border;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Select a bundle to see details", id="bundle-detail-content")

    def show_bundle(self, bundle) -> None:
        """Update detail pane with bundle info."""
        from bluefinctl.core.bundles import BundleState

        state_label = {
            BundleState.BASE: "[# Base Layer — always active]",
            BundleState.ACTIVE: "[* Active]",
            BundleState.PARTIAL: "[~ Partially installed]",
            BundleState.AVAILABLE: "[. Available]",
        }

        lines = [
            f"{bundle.icon}  {bundle.name}",
            "",
            f"  {bundle.meta.description}",
            "",
            f"  Status:   {state_label.get(bundle.state, 'Unknown')}",
            f"  Packages: {bundle.installed_count}/{bundle.total_count} installed",
            f"  Category: {bundle.meta.category.value}",
            "",
            "  ---- Contents ----",
        ]

        # Show package list (first 20, then "and N more...")
        display_pkgs = bundle.packages[:20]
        for pkg in display_pkgs:
            lines.append(f"    - {pkg}")
        if len(bundle.packages) > 20:
            lines.append(f"    ... and {len(bundle.packages) - 20} more")

        lines.append("")
        if bundle.state == BundleState.BASE:
            lines.append("  This is the base layer and cannot be removed.")
        elif bundle.state == BundleState.ACTIVE:
            lines.append("  Press [Enter] to deactivate this bundle.")
        elif bundle.state in (BundleState.AVAILABLE, BundleState.PARTIAL):
            lines.append("  Press [Enter] to activate this bundle.")

        self.query_one("#bundle-detail-content", Label).update("\n".join(lines))


class BundleList(Static):
    """Left pane — list of all bundles grouped by category."""

    DEFAULT_CSS = """
    BundleList {
        width: 40;
        padding: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield ListView(id="bundle-listview")

    def on_mount(self) -> None:
        self.run_worker(self._load_bundles())

    async def _load_bundles(self) -> None:
        from bluefinctl.core.bundles import get_bundles, get_bundles_by_category

        bundles = await get_bundles()
        grouped = get_bundles_by_category(bundles)
        listview = self.query_one("#bundle-listview", ListView)

        for category, cat_bundles in grouped.items():
            if not cat_bundles:
                continue
            # Category header
            listview.append(ListItem(
                Label(f"  ------ {category.value} ------"),
            ))
            for bundle in cat_bundles:
                indicator = bundle.state_indicator
                count_str = f"{bundle.installed_count}/{bundle.total_count}"
                listview.append(ListItem(
                    Label(f"  {indicator} {bundle.icon} {bundle.name}  ({count_str})"),
                    name=bundle.meta.slug,
                ))

        # Store bundles for detail lookup
        self._bundles = {b.meta.slug: b for b in bundles}

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """When a bundle is selected, show its details."""
        slug = event.item.name
        if slug and slug in self._bundles:
            detail = self.screen.query_one(BundleDetail)
            detail.show_bundle(self._bundles[slug])


class BundlesScreen(Screen):
    """Bundle management — choose your loadout."""

    BINDINGS = [
        ("enter", "activate_bundle", "Activate/Deactivate"),
        ("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Sidebar("bundles")
            yield BundleList()
            yield BundleDetail()

    async def action_activate_bundle(self) -> None:
        self.notify("Toggle bundle activation...", title="Bundles")

    async def action_refresh(self) -> None:
        self.notify("Refreshing bundle state...", title="Bundles")
