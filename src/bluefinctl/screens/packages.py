"""Packages screen - individual package management.

This is the "escape hatch" for packages not in any bundle.
Shows user-added packages and allows search/add/remove.
Does NOT show packages that came from system bundles.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Input, Label, Static

from bluefinctl.screens._sidebar import Sidebar


class PackageSearch(Static):
    """Search bar for finding packages to add."""

    DEFAULT_CSS = """
    PackageSearch {
        height: 3;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search packages... (brew search)", id="pkg-search")


class PackageTable(Static):
    """DataTable showing user-installed packages."""

    DEFAULT_CSS = """
    PackageTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield DataTable(id="pkg-table")

    def on_mount(self) -> None:
        table = self.query_one("#pkg-table", DataTable)
        table.add_columns("Name", "Type", "Version", "Status")
        table.cursor_type = "row"
        self.run_worker(self._load_packages())

    async def _load_packages(self) -> None:
        """Load user-installed packages (not from system bundles)."""
        from bluefinctl.core.brew import PackageSource, get_brew_state

        state = await get_brew_state()
        table = self.query_one("#pkg-table", DataTable)

        # Show user packages and outdated system packages
        for pkg in state.packages:
            if pkg.source == PackageSource.USER:
                status = "~ outdated" if pkg.outdated else "ok"
                table.add_row(pkg.name, pkg.type.value, pkg.version or "-", status)

        if not state.user_packages:
            table.add_row("(no user packages)", "-", "-", "-")


class PackagesScreen(Screen):
    """Individual package management."""

    BINDINGS = [
        ("a", "add_package", "Add"),
        ("r", "remove_package", "Remove"),
        ("u", "upgrade_all", "Upgrade All"),
        ("/", "focus_search", "Search"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Sidebar("packages")
            with Vertical(id="main-content"):
                yield PackageSearch()
                yield PackageTable()
                yield Label(
                    "  [a]dd  [r]emove  [u]pgrade all  [/]search  |  "
                    "User packages only - bundle packages shown in [2] Bundles",
                    id="pkg-footer",
                )

    async def action_add_package(self) -> None:
        self.notify("Enter package name to add...", title="Add Package")

    async def action_remove_package(self) -> None:
        self.notify("Select a package to remove", title="Remove Package")

    async def action_upgrade_all(self) -> None:
        self.notify("Upgrading all packages...", title="Upgrade")

    def action_focus_search(self) -> None:
        self.query_one("#pkg-search", Input).focus()
