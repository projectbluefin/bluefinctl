"""DevMode screen — developer experience panel.

TabbedContent with 3 tabs:
  Overview  — status, runtime health, quick actions
  Tools     — developer tool list with install status
  Environments — Podman, Distrobox, Lima
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bluefinctl.core.devmode import DevTool

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Static, TabbedContent, TabPane

from bluefinctl.screens._sidebar import Sidebar


class OverviewTab(Static):
    """DevMode Overview — status card, runtime health, quick actions."""

    DEFAULT_CSS = """
    OverviewTab { height: auto; padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        with Static(classes="card"):
            yield Label("Developer Mode", classes="card--title")
            yield Label("  Checking...", id="devmode-status")
            yield Button("Enable Developer Mode", id="btn-toggle-devmode", variant="primary")
        yield Label("")
        with Static(classes="card"):
            yield Label("Runtime Health", classes="card--title")
            yield Label("  Checking...", id="runtime-health")
        yield Label("")
        with Static(classes="card"):
            yield Label("Quick Actions", classes="card--title")
            yield Label(
                "  [c] podman-tui    [v] VSCode    [l] Lima shell",
            )

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from bluefinctl.core.devmode import _check_devmode_active

        loop = asyncio.get_running_loop()
        state = await loop.run_in_executor(None, _check_devmode_active)

        if state.active:
            groups = ", ".join(state.groups or [])
            self.query_one("#devmode-status", Label).update(
                f"  Status: ACTIVE\n  Groups: {groups}"
            )
            self.query_one("#btn-toggle-devmode", Button).label = "Disable Developer Mode"
            self.query_one("#btn-toggle-devmode", Button).variant = "error"
        else:
            self.query_one("#devmode-status", Label).update(
                "  Status: INACTIVE\n  Not in docker/mock/lxd groups"
            )
            self.query_one("#btn-toggle-devmode", Button).label = "Enable Developer Mode"
            self.query_one("#btn-toggle-devmode", Button).variant = "primary"

        # Check runtime health
        health_lines: list[str] = []

        # Docker socket
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            health_lines.append(
                "[ok] Docker" if proc.returncode == 0 else "[X] Docker",
            )
        except FileNotFoundError:
            health_lines.append("[--] Docker (not installed)")

        # Podman socket
        try:
            proc = await asyncio.create_subprocess_exec(
                "podman", "info",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            health_lines.append(
                "[ok] Podman" if proc.returncode == 0 else "[X] Podman",
            )
        except FileNotFoundError:
            health_lines.append("[--] Podman (not installed)")

        # Lima
        try:
            proc = await asyncio.create_subprocess_exec(
                "lima", "list", "--format", "{{.Name}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0 and stdout.strip():
                vms = stdout.decode().strip().split("\n")
                health_lines.append(f"[ok] Lima ({len(vms)} VM(s))")
            else:
                health_lines.append("[--] Lima (no VMs)")
        except FileNotFoundError:
            health_lines.append("[--] Lima (not installed)")

        self.query_one("#runtime-health", Label).update(
            "  " + "    ".join(health_lines),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-toggle-devmode":
            self.app.call_later(self.app.run_action, "toggle_devmode")


class ToolsTab(Static):
    """DevMode Tools — interactive dev tool list with install status."""

    DEFAULT_CSS = """
    ToolsTab { height: 1fr; padding: 1 0; }
    #tools-list { height: 1fr; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._tools: list[DevTool] = []

    def compose(self) -> ComposeResult:
        yield Label("Developer Tools", classes="card--title")
        yield ListView(id="tools-list")

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from bluefinctl.core.devmode import get_dev_tools_status

        loop = asyncio.get_running_loop()
        self._tools = await loop.run_in_executor(None, get_dev_tools_status)
        try:
            tool_list = self.query_one("#tools-list", ListView)
        except NoMatches:
            return
        tool_list.clear()

        current_category = ""
        for tool in self._tools:
            if tool.category != current_category:
                current_category = tool.category
                tool_list.append(ListItem(Label(f"  -- {current_category} --"), disabled=True))
            status = "[ok]" if tool.installed else "[--]"
            label = f"  {status} {tool.name:<22} {tool.description}"
            tool_list.append(ListItem(Label(label), name=tool.slug))

    def selected_tool(self) -> DevTool | None:
        """Return the selected DevTool, skipping disabled category rows."""
        try:
            tool_list = self.query_one("#tools-list", ListView)
        except NoMatches:
            return None
        if tool_list.highlighted_child is None:
            return None
        slug = tool_list.highlighted_child.name
        if slug is None:
            return None
        return next((tool for tool in self._tools if tool.slug == slug), None)

    def refresh_tools(self) -> None:
        """Refresh tool status."""
        self.run_worker(self._load(), exclusive=True)


class EnvironmentsTab(Static):
    """DevMode Environments — Podman, Distrobox, Lima."""

    DEFAULT_CSS = """
    EnvironmentsTab { height: auto; padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        with Static(classes="card"):
            yield Label("Tier 1: Podman Desktop", classes="card--title")
            yield Label("  Checking...", id="env-podman")
        yield Label("")
        with Static(classes="card"):
            yield Label("Tier 2: Distrobox", classes="card--title")
            yield Label("  Checking...", id="env-distrobox")
        yield Label("")
        with Static(classes="card"):
            yield Label("Tier 3: Lima", classes="card--title")
            yield Label("  Checking...", id="env-lima")

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        # Podman Desktop
        import shutil

        if shutil.which("podman-desktop"):
            self.query_one("#env-podman", Label).update(
                "  [ok] Installed\n"
                "  Action: [open] Podman Desktop",
            )
        else:
            self.query_one("#env-podman", Label).update(
                "  Docker-compatible, zero VM tax\n"
                "  [--] Not installed",
            )

        # Distrobox containers
        try:
            proc = await asyncio.create_subprocess_exec(
                "distrobox", "list", "--no-color",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                lines = stdout.decode().strip().split("\n")
                # Skip header line
                containers = [ln for ln in lines[1:] if ln.strip()]
                if containers:
                    display_lines = []
                    for c in containers[:5]:
                        parts = c.split("|")
                        if len(parts) >= 3:
                            name = parts[1].strip()
                            status = parts[2].strip()
                            display_lines.append(f"    {name:<20} [{status}]")
                    self.query_one("#env-distrobox", Label).update(
                        f"  {len(containers)} container(s)\n"
                        + "\n".join(display_lines)
                        + "\n  Action: [n]ew container  [e]nter selected",
                    )
                else:
                    self.query_one("#env-distrobox", Label).update(
                        "  No containers\n"
                        "  Action: [n]ew container",
                    )
            else:
                self.query_one("#env-distrobox", Label).update(
                    "  [--] distrobox not available",
                )
        except FileNotFoundError:
            self.query_one("#env-distrobox", Label).update(
                "  [--] distrobox not installed",
            )

        # Lima
        try:
            proc = await asyncio.create_subprocess_exec(
                "lima", "list", "--format",
                "{{.Name}} {{.Status}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0 and stdout.strip():
                vms = stdout.decode().strip().split("\n")
                display_lines = []
                for vm in vms[:5]:
                    display_lines.append(f"    {vm}")
                self.query_one("#env-lima", Label).update(
                    "  WSL-equivalent Ubuntu VM\n"
                    + "\n".join(display_lines)
                    + "\n  Action: manage from Lima tooling",
                )
            else:
                self.query_one("#env-lima", Label).update(
                    "  WSL-equivalent Ubuntu VM — persistent, $HOME mounted\n"
                    "  [--] Not set up\n"
                    "  Action: guided setup coming soon",
                )
        except FileNotFoundError:
            self.query_one("#env-lima", Label).update(
                "  WSL-equivalent Ubuntu VM\n"
                "  [--] Lima not installed\n"
                "  Install via: brew install lima",
            )


class DevModeScreen(Screen[None]):
    """Developer mode screen — tools, environments, Lima."""

    BINDINGS = [
        Binding("enter", "install_selected_tool", "Install"),
        Binding("c", "launch_podman_tui", "podman-tui"),
        Binding("a", "install_all", "Install All"),
    ]

    DEFAULT_CSS = """
    DevModeScreen {
        layout: horizontal;
    }
    #devmode-content {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
    }
    """

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:  # noqa: ARG002
        """Disable Install footer hint when not on the Tools tab."""
        if action == "install_selected_tool":
            try:
                return self.query_one(TabbedContent).active == "tab-tools"
            except NoMatches:  # widget not yet mounted
                return None
        return None

    def compose(self) -> ComposeResult:
        yield Sidebar(active="devmode")
        with ScrollableContainer(id="devmode-content"), TabbedContent():
            with TabPane("Overview", id="tab-overview"):
                yield OverviewTab()
            with TabPane("Tools", id="tab-tools"):
                yield ToolsTab()
            with TabPane("Environments", id="tab-envs"):
                yield EnvironmentsTab()

    async def action_toggle_devmode(self) -> None:
        """Enable or disable developer mode."""
        import os

        from bluefinctl.core.devmode import _check_devmode_active
        from bluefinctl.screens._modals import ConfirmModal, OperationLogModal

        state = _check_devmode_active()
        username = os.environ.get("USER", "")
        if state.active:
            confirmed = await self.app.push_screen_wait(
                ConfirmModal(
                    "Disable Developer Mode",
                    f"Remove docker/mock/lxd groups from {username}?",
                )
            )
            if confirmed:
                cmds = " && ".join([
                    f"gpasswd -d {username} docker",
                    f"gpasswd -d {username} mock",
                    f"gpasswd -d {username} lxd",
                ])
                rc = await self.app.push_screen_wait(
                    OperationLogModal("Disable Developer Mode", ["pkexec", "bash", "-c", cmds])
                )
                if rc == 0:
                    self.notify("Developer mode disabled. Log out to apply.", title="DevMode")
                    self.query_one(OverviewTab).run_worker(
                        self.query_one(OverviewTab)._load(), exclusive=True
                    )
        else:
            confirmed = await self.app.push_screen_wait(
                ConfirmModal(
                    "Enable Developer Mode",
                    f"Add {username} to docker, mock, lxd groups?",
                )
            )
            if confirmed:
                cmds = " && ".join([
                    f"usermod -aG docker {username} 2>/dev/null || true",
                    f"usermod -aG mock {username} 2>/dev/null || true",
                    f"usermod -aG lxd {username} 2>/dev/null || true",
                ])
                rc = await self.app.push_screen_wait(
                    OperationLogModal("Enable Developer Mode", ["pkexec", "bash", "-c", cmds])
                )
                if rc == 0:
                    self.notify("Developer mode enabled. Log out to apply.", title="DevMode")
                    self.query_one(OverviewTab).run_worker(
                        self.query_one(OverviewTab)._load(), exclusive=True
                    )

    def action_launch_podman_tui(self) -> None:
        """Launch podman-tui in a new terminal."""
        import shutil

        from bluefinctl.util.terminal import launch_in_terminal

        if shutil.which("podman-tui"):
            launch_in_terminal(["podman-tui"], title="podman-tui")
        else:
            self.notify("podman-tui not installed", severity="warning")

    async def action_install_selected_tool(self) -> None:
        """Install the selected missing developer tool from the Tools tab."""
        from bluefinctl.core.devmode import install_dev_tool_steps
        from bluefinctl.screens._modals import ConfirmModal
        from bluefinctl.widgets.operation_modal import OperationModal

        # Only act when the Tools tab is active to avoid accidental installs
        tabbed = self.query_one(TabbedContent)
        if tabbed.active != "tab-tools":
            return

        tools_tab = self.query_one(ToolsTab)
        tool = tools_tab.selected_tool()
        if tool is None:
            self.notify("Select a developer tool first", severity="warning", title="DevMode")
            return
        if tool.installed:
            self.notify(f"{tool.name} is already installed", title="DevMode")
            return

        confirmed = await self.app.push_screen_wait(
            ConfirmModal(
                f"Install {tool.name}?",
                f"Install {tool.name} via Homebrew?",
            ),
        )
        if not confirmed:
            return

        rc = await self.app.push_screen_wait(
            OperationModal(
                f"Installing {tool.name}",
                steps=install_dev_tool_steps(tool),
            ),
        )
        if rc == 0:
            self.notify(f"{tool.name} installed", title="DevMode")
            tools_tab.refresh_tools()
        else:
            self.notify(f"Failed to install {tool.name}", severity="error", title="DevMode")

    async def action_install_all(self) -> None:
        """Install all missing dev tools."""
        from bluefinctl.core.devmode import install_missing_dev_tools_steps
        from bluefinctl.screens._modals import ConfirmModal
        from bluefinctl.widgets.operation_modal import OperationModal

        confirmed = await self.app.push_screen_wait(
            ConfirmModal(
                "Install All Dev Tools",
                "Install all missing developer tools via Homebrew?",
            ),
        )
        if confirmed:
            rc = await self.app.push_screen_wait(
                OperationModal(
                    "Installing Dev Tools",
                    steps=install_missing_dev_tools_steps(),
                ),
            )
            if rc == 0:
                self.notify("All dev tools installed", title="DevMode")
                self.query_one(ToolsTab).refresh_tools()
            else:
                self.notify("Failed to install dev tools", severity="error", title="DevMode")
