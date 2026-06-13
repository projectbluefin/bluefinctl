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
from textual.widgets import Label, ListItem, ListView, Static, TabbedContent, TabPane

from bluefinctl.screens._viewswitcher import ViewSwitcher
from bluefinctl.widgets.adw import (
    AdwButtonRow,
    AdwPreferencesGroup,
    AdwPropertyRow,
)


class OverviewTab(Static):
    """DevMode Overview — status card, runtime health, quick actions."""

    DEFAULT_CSS = "OverviewTab { height: auto; }"

    def compose(self) -> ComposeResult:
        yield AdwPreferencesGroup(
            "Developer Mode",
            AdwPropertyRow("Status", "Checking…", id="devmode-status"),
            AdwPropertyRow("Groups", "", id="devmode-groups"),
            AdwButtonRow("Enable Developer Mode", variant="primary", id="btn-toggle-devmode"),
        )
        yield AdwPreferencesGroup(
            "Runtime Health",
            AdwPropertyRow("Docker", "Checking…", id="health-docker"),
            AdwPropertyRow("Podman", "Checking…", id="health-podman"),
            AdwPropertyRow("Lima", "Checking…", id="health-lima"),
        )
        yield AdwPreferencesGroup(
            "Quick Actions",
            AdwButtonRow("Launch podman-tui", id="btn-podman-tui"),
            AdwButtonRow("Open VSCode", id="btn-vscode"),
        )

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from bluefinctl.core.devmode import _check_devmode_active
        loop = asyncio.get_running_loop()
        state = await loop.run_in_executor(None, _check_devmode_active)

        if state.active:
            self.query_one("#devmode-status", AdwPropertyRow).update_value("Active")
            self.query_one("#devmode-groups", AdwPropertyRow).update_value(
                ", ".join(state.groups or [])
            )
            self.query_one("#btn-toggle-devmode", AdwButtonRow)._title = "Disable Developer Mode"
            self.query_one("#btn-toggle-devmode", AdwButtonRow)._variant = "destructive"
        else:
            self.query_one("#devmode-status", AdwPropertyRow).update_value("Inactive")

        # Runtime health
        for cmd, id_ in [("docker", "health-docker"), ("podman", "health-podman")]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    cmd, "info",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.communicate()
                status = "✓ ok" if proc.returncode == 0 else "✗ not running"
            except FileNotFoundError:
                status = "— not installed"
            self.query_one(f"#{id_}", AdwPropertyRow).update_value(status)

        try:
            proc = await asyncio.create_subprocess_exec(
                "lima", "list", "--format", "{{.Name}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0 and stdout.strip():
                vms = [v for v in stdout.decode().strip().split("\n") if v]
                lima_status = f"✓ {len(vms)} VM(s)"
            else:
                lima_status = "— no VMs"
        except FileNotFoundError:
            lima_status = "— not installed"
        self.query_one("#health-lima", AdwPropertyRow).update_value(lima_status)

    def on_adw_button_row_pressed(self, event: AdwButtonRow.Pressed) -> None:
        if event.row.id == "btn-toggle-devmode":
            self.app.call_later(self.screen.action_toggle_devmode)  # type: ignore[attr-defined]
        elif event.row.id == "btn-podman-tui":
            self.screen.action_launch_podman_tui()  # type: ignore[attr-defined]
        elif event.row.id == "btn-vscode":
            import shutil

            from bluefinctl.util.terminal import launch_in_terminal
            if shutil.which("code"):
                launch_in_terminal(["code", "--new-window"], title="VSCode")
            else:
                self.app.notify("VSCode not found", severity="warning")


class ToolsTab(Static):
    """DevMode Tools — interactive dev tool list with install status."""

    DEFAULT_CSS = """
    ToolsTab { height: 1fr; }
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
                tool_list.append(ListItem(Label(f"  — {current_category} —"), disabled=True))
            status = "✓" if tool.installed else "·"
            tool_list.append(
                ListItem(Label(f"  {status}  {tool.name:<22} {tool.description}"), name=tool.slug)
            )

    def selected_tool(self) -> DevTool | None:
        try:
            tool_list = self.query_one("#tools-list", ListView)
        except NoMatches:
            return None
        if tool_list.highlighted_child is None:
            return None
        slug = tool_list.highlighted_child.name
        return next((t for t in self._tools if t.slug == slug), None)

    def refresh_tools(self) -> None:
        self.run_worker(self._load(), exclusive=True)


class EnvironmentsTab(Static):
    """DevMode Environments — Podman, Distrobox, Lima."""

    DEFAULT_CSS = "EnvironmentsTab { height: auto; }"

    def compose(self) -> ComposeResult:
        yield AdwPreferencesGroup(
            "Tier 1 — Podman Desktop",
            AdwPropertyRow("Status", "Checking…", id="env-podman"),
        )
        yield AdwPreferencesGroup(
            "Tier 2 — Distrobox",
            AdwPropertyRow("Containers", "Checking…", id="env-distrobox"),
        )
        yield AdwPreferencesGroup(
            "Tier 3 — Lima",
            AdwPropertyRow("VMs", "Checking…", id="env-lima"),
            AdwButtonRow("Set Up Lima VM", id="btn-lima-setup"),
        )

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        import shutil
        if shutil.which("podman-desktop"):
            self.query_one("#env-podman", AdwPropertyRow).update_value("✓ installed")
        else:
            self.query_one("#env-podman", AdwPropertyRow).update_value("— not installed")

        try:
            proc = await asyncio.create_subprocess_exec(
                "distrobox", "list", "--no-color",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                lines = [ln for ln in stdout.decode().strip().split("\n")[1:] if ln.strip()]
                self.query_one("#env-distrobox", AdwPropertyRow).update_value(
                    f"{len(lines)} container(s)" if lines else "none"
                )
            else:
                self.query_one("#env-distrobox", AdwPropertyRow).update_value("— unavailable")
        except FileNotFoundError:
            self.query_one("#env-distrobox", AdwPropertyRow).update_value("— not installed")

        try:
            proc = await asyncio.create_subprocess_exec(
                "lima", "list", "--format", "{{.Name}} {{.Status}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0 and stdout.strip():
                vms = [v for v in stdout.decode().strip().split("\n") if v]
                self.query_one("#env-lima", AdwPropertyRow).update_value(
                    f"{len(vms)} VM(s) — {vms[0]}"
                )
            else:
                self.query_one("#env-lima", AdwPropertyRow).update_value("— not set up")
        except FileNotFoundError:
            self.query_one("#env-lima", AdwPropertyRow).update_value("— not installed")

    def on_adw_button_row_pressed(self, event: AdwButtonRow.Pressed) -> None:
        if event.row.id == "btn-lima-setup":
            self.app.call_later(self.screen.action_lima_setup)  # type: ignore[attr-defined]


class DevModeScreen(Screen[None]):
    """Developer mode screen — tools, environments, Lima."""

    BINDINGS = [
        Binding("enter", "install_selected_tool", "Install"),
        Binding("c", "launch_podman_tui", "podman-tui"),
        Binding("a", "install_all", "Install All"),
    ]

    DEFAULT_CSS = """
    DevModeScreen { layout: vertical; }
    #devmode-content { width: 1fr; height: 1fr; padding: 0 1; }
    """

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:  # noqa: ARG002
        if action == "install_selected_tool":
            try:
                return self.query_one(TabbedContent).active == "tab-tools"
            except NoMatches:
                return None
        return None

    def compose(self) -> ComposeResult:
        yield ViewSwitcher("devmode")
        with ScrollableContainer(id="devmode-content"):
            with TabbedContent():
                with TabPane("Overview", id="tab-overview"):
                    yield OverviewTab()
                with TabPane("Tools", id="tab-tools"):
                    yield ToolsTab()
                with TabPane("Environments", id="tab-envs"):
                    yield EnvironmentsTab()

    async def action_toggle_devmode(self) -> None:
        import os

        from bluefinctl.core.devmode import _check_devmode_active
        from bluefinctl.screens._modals import ConfirmModal, OperationLogModal
        state = _check_devmode_active()
        username = os.environ.get("USER", "")
        if state.active:
            confirmed = await self.app.push_screen_wait(
                ConfirmModal("Disable Developer Mode", f"Remove groups from {username}?")
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
                ConfirmModal("Enable Developer Mode", f"Add {username} to docker/mock/lxd groups?")
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
        import shutil

        from bluefinctl.util.terminal import launch_in_terminal
        if shutil.which("podman-tui"):
            launch_in_terminal(["podman-tui"], title="podman-tui")
        else:
            self.notify("podman-tui not installed", severity="warning")

    async def action_install_selected_tool(self) -> None:
        from bluefinctl.core.devmode import install_dev_tool_steps
        from bluefinctl.screens._modals import ConfirmModal
        from bluefinctl.widgets.operation_modal import OperationModal
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
            ConfirmModal(f"Install {tool.name}?", "Install via Homebrew?")
        )
        if not confirmed:
            return
        rc = await self.app.push_screen_wait(
            OperationModal(f"Installing {tool.name}", steps=install_dev_tool_steps(tool))
        )
        if rc == 0:
            self.notify(f"{tool.name} installed", title="DevMode")
            tools_tab.refresh_tools()
        else:
            self.notify(f"Failed to install {tool.name}", severity="error", title="DevMode")

    async def action_install_all(self) -> None:
        from bluefinctl.core.devmode import install_missing_dev_tools_steps
        from bluefinctl.screens._modals import ConfirmModal
        from bluefinctl.widgets.operation_modal import OperationModal
        confirmed = await self.app.push_screen_wait(
            ConfirmModal("Install All Dev Tools", "Install all missing developer tools?")
        )
        if confirmed:
            rc = await self.app.push_screen_wait(
                OperationModal("Installing Dev Tools", steps=install_missing_dev_tools_steps())
            )
            if rc == 0:
                self.notify("All dev tools installed", title="DevMode")
                self.query_one(ToolsTab).refresh_tools()
            else:
                self.notify("Failed to install dev tools", severity="error", title="DevMode")

    async def action_lima_setup(self) -> None:
        from bluefinctl.core.devmode import lima_setup_steps
        from bluefinctl.widgets.operation_modal import OperationModal
        rc = await self.app.push_screen_wait(
            OperationModal("Set Up Lima VM", steps=lima_setup_steps())
        )
        if rc == 0:
            self.notify("Lima VM is ready", title="Lima")
        else:
            self.notify("Lima setup failed — see log for details", severity="error", title="Lima")
        # Refresh the Environments tab either way
        envs = self.query_one(EnvironmentsTab)
        envs.run_worker(envs._load(), exclusive=True)

