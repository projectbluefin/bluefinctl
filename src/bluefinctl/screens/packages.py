"""Packages screen - individual package management.

This is the "escape hatch" for packages not in any bundle.
Shows user-added packages and allows search/add/remove.
Does NOT show packages that came from system bundles.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.coordinate import Coordinate
from textual.screen import Screen
from textual.widgets import DataTable, Input, Label, Static

from bluefinctl.screens._sidebar import Sidebar
from bluefinctl.screens._modals import ConfirmModal, InputModal, OperationLogModal


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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._all_rows: list[tuple] = []

    def compose(self) -> ComposeResult:
        yield DataTable(id="pkg-table")

    def on_mount(self) -> None:
        table = self.query_one("#pkg-table", DataTable)
        table.add_columns("Name", "Type", "Version", "Status")
        table.cursor_type = "row"
        self.run_worker(self._load_packages(), exclusive=True)

    async def _load_packages(self) -> None:
        """Load user-installed packages (not from system bundles)."""
        from bluefinctl.core.brew import PackageSource, get_brew_state

        self._all_rows = []
        state = await get_brew_state()
        table = self.query_one("#pkg-table", DataTable)
        table.clear()

        # Show user packages and outdated system packages
        for pkg in state.packages:
            if pkg.source == PackageSource.USER:
                status = "~ outdated" if pkg.outdated else "ok"
                row = (pkg.name, pkg.type.value, pkg.version or "-", status)
                self._all_rows.append(row)
                table.add_row(*row)

        if not state.user_packages:
            table.add_row("(no user packages)", "-", "-", "-")

    def filter(self, text: str) -> None:
        """Filter the visible rows by name or status."""
        if not self._all_rows:
            return  # still loading, don't clear the table
        table = self.query_one("#pkg-table", DataTable)
        table.clear()
        if not text:
            for row in self._all_rows:
                table.add_row(*row)
            return
        needle = text.casefold()
        matched = [
            row for row in self._all_rows
            if needle in str(row[0]).casefold() or needle in str(row[3]).casefold()
        ]
        if matched:
            for row in matched:
                table.add_row(*row)
        else:
            table.add_row("(no results)", "-", "-", "-")


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
        name = await self.app.push_screen_wait(InputModal('Add Package', 'Package name (prefix --cask for cask)'))
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        is_cask = name.startswith('--cask ')
        pkg_name = name.removeprefix('--cask ').strip()
        cmd = ['brew', 'install']
        if is_cask:
            cmd.append('--cask')
        cmd.append(pkg_name)
        rc = await self.app.push_screen_wait(OperationLogModal(f'Add {pkg_name}', cmd))
        if rc == 0:
            from pathlib import Path
            brewfile = Path.home() / '.config' / 'bluefin' / 'Brewfile'
            brewfile.parent.mkdir(parents=True, exist_ok=True)
            entry = f'{"cask" if is_cask else "brew"} "{pkg_name}"\n'
            with brewfile.open('a') as f:
                f.write(entry)
            self.notify(f'Added {pkg_name}', title='Packages')
            self.query_one(PackageTable).run_worker(self.query_one(PackageTable)._load_packages(), exclusive=True)
        else:
            self.notify(f'Failed to install {pkg_name}', severity='error', title='Packages')

    async def action_remove_package(self) -> None:
        table = self.query_one('#pkg-table', DataTable)
        if table.cursor_row < 0:
            self.notify('Select a package first', title='Remove')
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        cell = table.get_cell_at(Coordinate(table.cursor_row, 0))
        name = str(cell)
        if name.startswith('('):
            return
        confirmed = await self.app.push_screen_wait(ConfirmModal('Remove Package', f'Uninstall {name}?'))
        if confirmed:
            rc = await self.app.push_screen_wait(OperationLogModal(f'Remove {name}', ['brew', 'uninstall', name]))
            if rc == 0:
                self.notify(f'Removed {name}', title='Packages')
                self.query_one(PackageTable).run_worker(self.query_one(PackageTable)._load_packages(), exclusive=True)

    async def action_upgrade_all(self) -> None:
        rc = await self.app.push_screen_wait(OperationLogModal('Upgrade All Packages', ['brew', 'upgrade']))
        if rc == 0:
            self.notify('All packages up to date', title='Upgrade')
            self.query_one(PackageTable).run_worker(self.query_one(PackageTable)._load_packages(), exclusive=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "pkg-search":
            self.query_one(PackageTable).filter(event.value)

    def action_focus_search(self) -> None:
        self.query_one("#pkg-search", Input).focus()
