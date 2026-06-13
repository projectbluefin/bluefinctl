"""Dashboard screen — system health overview and quick actions."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, Static


class SystemCard(Static):
    """System information card."""

    def compose(self) -> ComposeResult:
        yield Label("System", classes="card--title")
        yield Label("Loading...", id="system-info")

    def on_mount(self) -> None:
        self.run_worker(self._load_system_info())

    async def _load_system_info(self) -> None:
        from bluefinctl.core.system import get_system_info

        info = await get_system_info()
        label = self.query_one("#system-info", Label)
        label.update(info.render())


class UpdateCard(Static):
    """Update status card."""

    def compose(self) -> ComposeResult:
        yield Label("Updates", classes="card--title")
        yield Label("Loading...", id="update-info")

    def on_mount(self) -> None:
        self.run_worker(self._load_update_info())

    async def _load_update_info(self) -> None:
        from bluefinctl.core.updates import get_update_status

        status = await get_update_status()
        label = self.query_one("#update-info", Label)
        label.update(status.render())


class QuickActions(Static):
    """Quick action buttons."""

    def compose(self) -> ComposeResult:
        yield Label("Quick Actions", classes="card--title")
        yield Label("[u] Update All  [d] Devmode  [f] Focus Mode  [r] Report")


class DashboardScreen(Screen):
    """Main dashboard — system health at a glance."""

    BINDINGS = [
        ("u", "update_all", "Update All"),
        ("d", "toggle_devmode", "Devmode"),
        ("f", "toggle_focus", "Focus Mode"),
        ("r", "system_report", "Report"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal():
            # Sidebar
            with Vertical(classes="sidebar"):
                yield Label("● System", classes="sidebar--item -active")
                yield Label("  Brew", classes="sidebar--item")
                yield Label("  Updates", classes="sidebar--item")
                yield Label("  Pods", classes="sidebar--item")
                yield Label("  AI", classes="sidebar--item")
                yield Label("  Config", classes="sidebar--item")

            # Main content
            with Container(id="main-content"):
                yield SystemCard(classes="card")
                yield UpdateCard(classes="card")
                yield QuickActions(classes="card")

    async def action_update_all(self) -> None:
        """Trigger full system update."""
        self.notify("Starting update...", title="Update")

    async def action_toggle_devmode(self) -> None:
        """Toggle developer mode."""
        self.notify("Toggling devmode...", title="Developer Mode")

    async def action_toggle_focus(self) -> None:
        """Toggle focus mode (pause updates)."""
        self.notify("Focus mode toggled", title="Focus Mode")

    async def action_system_report(self) -> None:
        """Generate system report."""
        self.notify("Generating report...", title="System Report")
