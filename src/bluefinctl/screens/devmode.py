"""Developer Mode screen — kits, tools, environments, devmode toggle.

Merged from toolkit.py + devmode.py.

Tabs:
  Kits         — Brewfile-backed kit bundles with individual package install
  Tools        — Developer tool list with per-tool install
  Environments — Podman Desktop, Distrobox, Lima VM
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bluefinctl.core.devmode import DevTool

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import (
    Button,
    Label,
    ListItem,
    ListView,
    Static,
    TabbedContent,
    TabPane,
)

from bluefinctl.screens._viewswitcher import ViewSwitcher
from bluefinctl.widgets.adw import (
    AdwButtonRow,
    AdwPreferencesGroup,
    AdwPropertyRow,
    AdwSwitchRow,
)
from bluefinctl.widgets.ops_bar import OpsBar

# ─────────────────────────────────────────────────────────────────────────────
# Kits tab
# ─────────────────────────────────────────────────────────────────────────────

class KitDetailPane(Vertical):
    """Right-side detail pane for Kits: description, per-package status, actions."""

    DEFAULT_CSS = """
    KitDetailPane {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
        border-left: solid $border;
    }
    #kit-detail-title   { text-style: bold; color: $accent; }
    #kit-detail-desc    { color: $text-muted; margin-bottom: 1; }
    #kit-pkg-scroll     { height: 1fr; }
    #kit-pkg-list       { height: 1fr; }
    #kit-action-bar     { height: 3; align: left middle; margin-top: 1; }
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
            yield ListView(id="kit-pkg-list")
        with Horizontal(id="kit-action-bar"):
            yield Button("Activate",   id="btn-kit-activate",   variant="primary", disabled=True)
            yield Button("Deactivate", id="btn-kit-deactivate", variant="warning",  disabled=True)

    def show_bundle(self, bundle: Any, installed: set[str]) -> None:
        """Render kit detail for the given bundle."""
        self._bundle   = bundle
        self._installed = installed

        self.query_one("#kit-detail-title", Label).update(f"{bundle.meta.icon}  {bundle.name}")
        self.query_one("#kit-detail-desc",  Label).update(
            f"  {bundle.meta.description}\n"
            f"  {bundle.installed_count}/{bundle.total_count} packages installed"
            f"  ·  {bundle.state.value}"
        )

        pkg_list = self.query_one("#kit-pkg-list", ListView)
        pkg_list.clear()
        for pkg in bundle.packages:
            icon  = "✓" if pkg in installed else "·"
            color = "green" if pkg in installed else "dim"
            pkg_list.append(
                ListItem(Label(f"  [{color}]{icon}[/{color}]  {pkg}"), name=pkg)
            )

        from bluefinctl.core.bundles import BundleState
        btn_activate   = self.query_one("#btn-kit-activate",   Button)
        btn_deactivate = self.query_one("#btn-kit-deactivate", Button)
        is_base    = bundle.state == BundleState.BASE
        is_active  = bundle.state in (BundleState.ACTIVE, BundleState.PARTIAL)
        btn_activate.disabled   = is_base or is_active
        btn_deactivate.disabled = is_base or not is_active

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("btn-kit-activate", "btn-kit-deactivate"):
            self.screen.action_activate_kit()  # type: ignore[attr-defined]


class KitsTab(Static):
    """Kits tab — Brewfile kit bundles."""

    DEFAULT_CSS = """
    KitsTab {
        height: 1fr;
        layout: horizontal;
    }
    #kit-list-container { width: 42; height: 1fr; }
    #kit-list-header    { padding: 0 1; text-style: bold; color: $accent; }
    #kit-list           { height: 1fr; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._bundles: list[Any]  = []
        self._installed: set[str] = set()

    def compose(self) -> ComposeResult:
        with Vertical(id="kit-list-container"):
            yield Label("Kits", id="kit-list-header")
            yield ListView(id="kit-list")
        yield KitDetailPane()

    def on_mount(self) -> None:
        self.run_worker(self._load_kits(), exclusive=True)

    async def _load_kits(self) -> None:
        from bluefinctl.core.bundles import (
            _get_installed_flatpaks,
            _get_installed_formulae,
            get_bundles,
        )
        loop            = asyncio.get_running_loop()
        self._bundles   = await get_bundles()
        formulae        = await loop.run_in_executor(None, _get_installed_formulae)
        flatpaks        = await loop.run_in_executor(None, _get_installed_flatpaks)
        self._installed = formulae | flatpaks

        kit_list = self.query_one("#kit-list", ListView)
        kit_list.clear()
        for bundle in self._bundles:
            state_badge = {
                "base":      " [base]",
                "active":    " [active]",
                "partial":   f" [{bundle.installed_count}/{bundle.total_count}]",
                "available": "",
            }.get(bundle.state.value, "")
            label = f"  {bundle.meta.icon}  {bundle.name:<24}{state_badge}"
            kit_list.append(ListItem(Label(label), name=bundle.meta.slug))

        if self._bundles:
            self._show_detail(0)

    def _show_detail(self, index: int) -> None:
        if 0 <= index < len(self._bundles):
            self.query_one(KitDetailPane).show_bundle(self._bundles[index], self._installed)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is not None and event.list_view.index is not None:
            self._show_detail(event.list_view.index)

    def selected_bundle(self) -> Any | None:
        kit_list = self.query_one("#kit-list", ListView)
        if kit_list.index is None or kit_list.index >= len(self._bundles):
            return None
        return self._bundles[kit_list.index]

    def refresh_kits(self) -> None:
        self.run_worker(self._load_kits(), exclusive=True)


# ─────────────────────────────────────────────────────────────────────────────
# Tools tab (from devmode.py ToolsTab)
# ─────────────────────────────────────────────────────────────────────────────

class ToolsTab(Static):
    """Developer Tools — list with per-tool install status and install button."""

    DEFAULT_CSS = """
    ToolsTab { height: 1fr; }
    #tools-cols   { height: 1fr; }
    #tools-list-container { width: 50; height: 1fr; }
    #tools-list   { height: 1fr; }
    #tool-detail  {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
        border-left: solid $border;
    }
    #tool-detail-name   { text-style: bold; color: $accent; }
    #tool-detail-desc   { color: $text-muted; margin-bottom: 1; }
    #tool-action-bar    { height: 3; align: left middle; margin-top: 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._tools: list[DevTool] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="tools-cols"):
            with Vertical(id="tools-list-container"):
                yield Label("Developer Tools", classes="card--title")
                yield ListView(id="tools-list")
            with Vertical(id="tool-detail"):
                yield Label("Select a tool →", id="tool-detail-name")
                yield Label("",                id="tool-detail-desc")
                with Horizontal(id="tool-action-bar"):
                    yield Button(
                        "Install",
                        id="btn-tool-install",
                        variant="primary",
                        disabled=True,
                    )

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from bluefinctl.core.devmode import get_dev_tools_status
        loop        = asyncio.get_running_loop()
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
                tool_list.append(
                    ListItem(Label(f"  — {current_category} —"), disabled=True)
                )
            status = "✓" if tool.installed else "·"
            tool_list.append(
                ListItem(
                    Label(f"  {status}  {tool.name:<22} {tool.description}"),
                    name=tool.slug,
                )
            )

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is None or event.item.name is None:
            return
        tool = next((t for t in self._tools if t.slug == event.item.name), None)
        if tool is None:
            return
        self.query_one("#tool-detail-name", Label).update(
            f"{tool.name}{'  [green]✓ installed[/green]' if tool.installed else ''}"
        )
        self.query_one("#tool-detail-desc", Label).update(
            f"  {tool.description}\n  Package: {tool.package}\n  Command: {tool.command}"
        )
        btn = self.query_one("#btn-tool-install", Button)
        btn.disabled = tool.installed

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-tool-install":
            self.screen.action_install_selected_tool()  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# Environments tab (from devmode.py EnvironmentsTab)
# ─────────────────────────────────────────────────────────────────────────────

class EnvironmentsTab(Static):
    """Environments — Podman Desktop, Distrobox, Lima."""

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
        self.query_one("#env-podman", AdwPropertyRow).update_value(
            "✓ installed" if shutil.which("podman-desktop") else "— not installed"
        )
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


# ─────────────────────────────────────────────────────────────────────────────
# Combined Developer Mode screen
# ─────────────────────────────────────────────────────────────────────────────

class DevModeScreen(Screen[None]):
    """Developer Mode — kits, tools, environments, devmode toggle."""

    BINDINGS = [
        Binding("enter", "install_selected_tool", "Install"),
        Binding("a",     "install_all",           "Install All"),
        Binding("c",     "launch_podman_tui",     "podman-tui"),
    ]

    DEFAULT_CSS = """
    DevModeScreen { layout: vertical; }
    #devmode-header { height: auto; padding: 0 2; }
    #devmode-tabs   { width: 1fr; height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield ViewSwitcher("devmode")
        # Devmode toggle always visible above the tabs
        with ScrollableContainer(id="devmode-header"):
            yield AdwPreferencesGroup(
                "Developer Mode",
                AdwPropertyRow("Status", "Checking…", id="devmode-status"),
                AdwPropertyRow("Groups", "",           id="devmode-groups"),
                AdwSwitchRow(
                    "Enable Developer Mode",
                    subtitle="Adds current user to docker, mock, and lxd groups",
                    id="devmode-switch",
                ),
            )
        with TabbedContent(id="devmode-tabs"):
            with TabPane("Kits",         id="tab-kits"):
                yield KitsTab()
            with TabPane("Tools",        id="tab-tools"):
                yield ToolsTab()
            with TabPane("Environments", id="tab-envs"):
                yield ScrollableContainer(EnvironmentsTab())
        yield OpsBar()

    def on_mount(self) -> None:
        self.run_worker(self._load_devmode_status(), exclusive=False)

    async def _load_devmode_status(self) -> None:
        from bluefinctl.core.devmode import _check_devmode_active
        loop  = asyncio.get_running_loop()
        state = await loop.run_in_executor(None, _check_devmode_active)

        self.query_one("#devmode-status", AdwPropertyRow).update_value(
            "[green]Active[/green]" if state.active else "[dim]Inactive[/dim]"
        )
        if state.groups:
            self.query_one("#devmode-groups", AdwPropertyRow).update_value(
                ", ".join(state.groups)
            )
        # Set switch without firing Changed event
        with self.prevent(AdwSwitchRow.Changed):
            self.query_one("#devmode-switch", AdwSwitchRow).set_value(state.active)

    # ─────────────────────────────────────────────────────────────────────────
    # Event handlers
    # ─────────────────────────────────────────────────────────────────────────

    def on_adw_switch_row_changed(self, event: AdwSwitchRow.Changed) -> None:
        if event.row.id == "devmode-switch":
            self.run_worker(self.action_toggle_devmode(event.value), exclusive=True)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:  # noqa: ARG002
        if action == "install_selected_tool":
            try:
                active = self.query_one(TabbedContent).active
                return active in ("tab-kits", "tab-tools")
            except NoMatches:
                return None
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Devmode toggle
    # ─────────────────────────────────────────────────────────────────────────

    async def action_toggle_devmode(self, desired: bool | None = None) -> None:
        import os

        from bluefinctl.core.devmode import _check_devmode_active
        from bluefinctl.screens._modals import ConfirmModal, OperationLogModal
        state    = _check_devmode_active()
        username = os.environ.get("USER", "")

        # Determine intent from argument or current state
        enable = (not state.active) if desired is None else desired

        if enable:
            confirmed = await self.app.push_screen_wait(
                ConfirmModal(
                    "Enable Developer Mode",
                    f"Add {username} to docker, mock, and lxd groups?\n"
                    "You must log out and back in for changes to take effect.",
                )
            )
            if confirmed:
                cmds = " && ".join([
                    f"usermod -aG docker {username} 2>/dev/null || true",
                    f"usermod -aG mock   {username} 2>/dev/null || true",
                    f"usermod -aG lxd    {username} 2>/dev/null || true",
                ])
                rc = await self.app.push_screen_wait(
                    OperationLogModal("Enable Developer Mode", ["pkexec", "bash", "-c", cmds])
                )
                if rc == 0:
                    self.notify("Developer mode enabled. Log out to apply.", title="DevMode")
            else:
                # User cancelled — revert switch
                self.query_one("#devmode-switch", AdwSwitchRow).set_value(False)
        else:
            confirmed = await self.app.push_screen_wait(
                ConfirmModal(
                    "Disable Developer Mode",
                    f"Remove {username} from docker, mock, and lxd groups?\n"
                    "You must log out and back in for changes to take effect.",
                )
            )
            if confirmed:
                cmds = " && ".join([
                    f"gpasswd -d {username} docker 2>/dev/null || true",
                    f"gpasswd -d {username} mock   2>/dev/null || true",
                    f"gpasswd -d {username} lxd    2>/dev/null || true",
                ])
                rc = await self.app.push_screen_wait(
                    OperationLogModal("Disable Developer Mode", ["pkexec", "bash", "-c", cmds])
                )
                if rc == 0:
                    self.notify("Developer mode disabled. Log out to apply.", title="DevMode")
            else:
                # User cancelled — revert switch
                self.query_one("#devmode-switch", AdwSwitchRow).set_value(True)

        # Always refresh status
        self.run_worker(self._load_devmode_status(), exclusive=False)

    # ─────────────────────────────────────────────────────────────────────────
    # Kit actions
    # ─────────────────────────────────────────────────────────────────────────

    async def action_activate_kit(self) -> None:
        """Activate or deactivate the currently selected kit."""
        from bluefinctl.core.bundles import BundleState
        from bluefinctl.screens._modals import ConfirmModal
        from bluefinctl.widgets.operation_modal import OperationModal

        try:
            kits_tab = self.query_one(KitsTab)
        except NoMatches:
            return
        bundle = kits_tab.selected_bundle()
        if bundle is None:
            return

        if bundle.state == BundleState.BASE:
            self.notify("Base kit cannot be deactivated", severity="warning")
            return

        if bundle.state in (BundleState.ACTIVE, BundleState.PARTIAL):
            from bluefinctl.core.bundles import deactivate_bundle_steps, preview_bundle_deactivation
            preview  = await preview_bundle_deactivation(bundle.meta.slug)
            removable = ", ".join(preview.removable_packages[:12]) or "none"
            if len(preview.removable_packages) > 12:
                removable += f" +{len(preview.removable_packages) - 12} more"
            confirmed = await self.app.push_screen_wait(
                ConfirmModal(
                    f"Deactivate {bundle.name}?",
                    f"Will remove ({len(preview.removable_packages)} packages): {removable}",
                )
            )
            if confirmed:
                rc = await self.app.push_screen_wait(
                    OperationModal(
                        f"Deactivating {bundle.name}",
                        steps=deactivate_bundle_steps(bundle.meta.slug),
                    )
                )
                if rc == 0:
                    self.notify(f"{bundle.name} deactivated", title="Developer Mode")
                    kits_tab.refresh_kits()
        else:
            confirmed = await self.app.push_screen_wait(
                ConfirmModal(
                    f"Activate {bundle.name}?",
                    f"Install {bundle.total_count} packages via Homebrew.",
                )
            )
            if confirmed:
                from bluefinctl.core.bundles import activate_bundle_steps
                rc = await self.app.push_screen_wait(
                    OperationModal(
                        f"Activating {bundle.name}",
                        steps=activate_bundle_steps(bundle.meta.slug),
                    )
                )
                if rc == 0:
                    self.notify(f"{bundle.name} activated", title="Developer Mode")
                    kits_tab.refresh_kits()

    # ─────────────────────────────────────────────────────────────────────────
    # Tool actions
    # ─────────────────────────────────────────────────────────────────────────

    async def action_install_selected_tool(self) -> None:
        """Install selected item depending on active tab (keybinding entry point)."""
        try:
            active = self.query_one(TabbedContent).active
        except NoMatches:
            return

        if active == "tab-kits":
            await self.action_activate_kit()
        elif active == "tab-tools":
            await self._install_selected_tool()

    async def action_install_selected(self) -> None:
        """Alias — same as action_install_selected_tool."""
        await self.action_install_selected_tool()

    async def _install_selected_tool(self) -> None:
        from bluefinctl.core.devmode import install_dev_tool_steps
        from bluefinctl.screens._modals import ConfirmModal
        from bluefinctl.widgets.operation_modal import OperationModal

        try:
            tools_tab = self.query_one(ToolsTab)
        except NoMatches:
            return
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
                f"Install '{tool.package}' via Homebrew?",
            )
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
                try:
                    self.query_one(ToolsTab).refresh_tools()
                except NoMatches:
                    pass
            else:
                self.notify("Failed to install dev tools", severity="error", title="DevMode")

    # ─────────────────────────────────────────────────────────────────────────
    # Other actions
    # ─────────────────────────────────────────────────────────────────────────

    def action_launch_podman_tui(self) -> None:
        import shutil

        from bluefinctl.util.terminal import launch_in_terminal
        if shutil.which("podman-tui"):
            launch_in_terminal(["podman-tui"], title="podman-tui")
        else:
            self.notify("podman-tui not installed", severity="warning")

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
        try:
            envs = self.query_one(EnvironmentsTab)
            envs.run_worker(envs._load(), exclusive=True)
        except NoMatches:
            pass
