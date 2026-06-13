"""AI screen — GPU-accelerated AI stack management.

TabbedContent with 2 tabs:
  Stacks (default) — GPU detection + stack catalog with deploy/stop
  Tools            — AI CLI tools kit status
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from bluefinctl.core.ai import AI_TOOLS_KIT_SLUG, BUNDLE_AI_TOOLS_SOURCE

if TYPE_CHECKING:
    from bluefinctl.core.ai import AITool

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Static, TabbedContent, TabPane

from bluefinctl.screens._viewswitcher import ViewSwitcher
from bluefinctl.widgets.adw import AdwPreferencesGroup, AdwPropertyRow


class GpuCard(AdwPreferencesGroup):
    """GPU detection card shown at top of Stacks tab."""

    def __init__(self) -> None:
        super().__init__(
            "GPU",
            AdwPropertyRow("Vendor", "Detecting…", id="gpu-vendor"),
            AdwPropertyRow("VRAM", "—", id="gpu-vram"),
            AdwPropertyRow("Driver", "—", id="gpu-driver"),
        )

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from bluefinctl.core.ai import GpuVendor, detect_gpu
        loop = asyncio.get_running_loop()
        gpu = await loop.run_in_executor(None, detect_gpu)
        if gpu.vendor == GpuVendor.NONE:
            self.query_one("#gpu-vendor", AdwPropertyRow).update_value("No discrete GPU")
        else:
            self.query_one("#gpu-vendor", AdwPropertyRow).update_value(
                f"{gpu.vendor.value.upper()} {gpu.model}"
            )
            self.query_one("#gpu-vram", AdwPropertyRow).update_value(
                f"{gpu.vram_gb} GB" if gpu.vram_gb else "—"
            )
            driver_info = gpu.driver_version if gpu.driver_version else "—"
            if gpu.cdi_active:
                driver_info += "  ·  CDI active"
            self.query_one("#gpu-driver", AdwPropertyRow).update_value(driver_info)


class StacksTab(Static):
    """Stacks tab — catalog with deploy/stop actions."""

    DEFAULT_CSS = """
    StacksTab { height: 1fr; }
    #stack-list-container {
        height: 1fr;
    }
    #stack-list {
        height: 1fr;
    }
    #stack-detail {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
        border-left: solid $border;
    }
    #stack-detail-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._stacks: list[Any] = []

    def compose(self) -> ComposeResult:
        yield GpuCard()
        with Horizontal(id="stack-list-container"):
            yield ListView(id="stack-list")
            with Vertical(id="stack-detail"):
                yield Label("Select a stack", id="stack-detail-title")
                yield Label("", id="stack-detail-body")

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    def refresh_stacks(self) -> None:
        """Reload the stack list from system directories."""
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from bluefinctl.core.ai import StackStatus, get_stacks

        gpu, stacks = await get_stacks()
        self._stacks = stacks

        stack_list = self.query_one("#stack-list", ListView)
        stack_list.clear()

        if not stacks:
            stack_list.append(
                ListItem(Label("  No stacks found in system directories")),
            )
            return

        for stack in stacks:
            status_icon = {
                StackStatus.RUNNING: "[*]",
                StackStatus.AVAILABLE: "[ ]",
                StackStatus.STOPPED: "[ ]",
                StackStatus.EXCEEDS_VRAM: "[-]",
            }.get(stack.status, "[ ]")

            label = (
                f"  {status_icon} {stack.name:<18} "
                f"{stack.vram_gb:>2} GB   {stack.category.value:<6}  "
                f"{stack.description[:40]}"
            )
            stack_list.append(ListItem(Label(label), name=stack.slug))

        if stacks:
            self._show_stack_detail(0)

    def _show_stack_detail(self, index: int) -> None:
        """Show details for a selected stack."""
        if index < 0 or index >= len(self._stacks):
            return
        stack = self._stacks[index]
        title = self.query_one("#stack-detail-title", Label)
        body = self.query_one("#stack-detail-body", Label)

        title.update(stack.name)

        port_lines = ""
        if stack.ports:
            port_lines = "\n  Ports:\n"
            for name, port in stack.ports.items():
                port_lines += f"    {name}: http://localhost:{port}\n"

        deps = []
        if stack.requires_ngc_auth:
            deps.append("NGC auth token")
        if stack.requires_hf_auth:
            deps.append("HuggingFace token")
        dep_line = f"\n  Requires: {', '.join(deps)}" if deps else ""

        status_line = f"  Status: {stack.status.value.upper()}"

        body.update(
            f"  {stack.description}\n"
            f"\n"
            f"  Category: {stack.category.value}\n"
            f"  VRAM: {stack.vram_gb} GB | Disk: ~{stack.disk_gb} GB\n"
            f"{status_line}"
            f"{port_lines}"
            f"{dep_line}\n"
            f"\n"
            f"  [Enter] Deploy  [s] Stop  [l] Logs",
        )

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update detail pane when selection changes."""
        if event.item is not None:
            index = event.list_view.index
            if index is not None:
                self._show_stack_detail(index)


class ToolsTab(Static):
    """AI Tools tab — interactive tool inventory."""

    DEFAULT_CSS = """
    ToolsTab { height: 1fr; }
    #ai-tools-list { height: 1fr; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._tools: list[AITool] = []

    def compose(self) -> ComposeResult:
        yield Label("AI & ML Tools", classes="card--title")
        yield ListView(id="ai-tools-list")

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from bluefinctl.core.ai import get_ai_tools_status

        loop = asyncio.get_running_loop()
        self._tools = await loop.run_in_executor(None, get_ai_tools_status)
        try:
            tools_list = self.query_one("#ai-tools-list", ListView)
        except NoMatches:
            return
        tools_list.clear()

        current_category = ""
        for tool in self._tools:
            if tool.category != current_category:
                current_category = tool.category
                tools_list.append(ListItem(Label(f"  -- {current_category} --"), disabled=True))
            status = "[ok]" if tool.installed else "[--]"
            description = tool.description
            is_bundled = tool.source == BUNDLE_AI_TOOLS_SOURCE and tool.slug != AI_TOOLS_KIT_SLUG
            if is_bundled and not tool.installed:
                description = f"{description} (installs AI Tools kit)"
            label = f"  {status} {tool.name:<20} {description}"
            tools_list.append(ListItem(Label(label), name=tool.slug))

    def selected_tool(self) -> AITool | None:
        """Return the selected AI tool, skipping disabled category rows."""
        try:
            tools_list = self.query_one("#ai-tools-list", ListView)
        except NoMatches:
            return None
        if tools_list.highlighted_child is None:
            return None
        slug = tools_list.highlighted_child.name
        if slug is None:
            return None
        return next((tool for tool in self._tools if tool.slug == slug), None)

    def refresh_tools(self) -> None:
        """Refresh AI tool status."""
        self.run_worker(self._load(), exclusive=True)


class AIScreen(Screen[None]):
    """AI workstation management — stack catalog and tools."""

    BINDINGS = [
        Binding("enter", "deploy_stack", "Select"),
        Binding("s", "stop_stack", "Stop"),
        Binding("l", "stack_logs", "Logs"),
    ]

    DEFAULT_CSS = """
    AIScreen {
        layout: vertical;
    }
    #ai-content {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
    }
    """

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:  # noqa: ARG002
        """Hide stop/log footer hints when not on the Stacks tab."""
        if action in ("stop_stack", "stack_logs"):
            try:
                return self.query_one(TabbedContent).active == "tab-stacks"
            except NoMatches:  # widget not yet mounted
                return None
        return None

    def compose(self) -> ComposeResult:
        yield ViewSwitcher("ai")
        with ScrollableContainer(id="ai-content"), TabbedContent():
            with TabPane("Stacks", id="tab-stacks"):
                yield StacksTab()
            with TabPane("Tools", id="tab-tools"):
                yield ToolsTab()

    async def action_deploy_stack(self) -> None:
        """Deploy the selected stack or install selected AI tool on the Tools tab."""
        tabbed = self.query_one(TabbedContent)
        if tabbed.active == "tab-tools":
            await self._install_selected_ai_tool()
            return

        from bluefinctl.core.ai import StackStatus, deploy_stack_steps
        from bluefinctl.screens._modals import ConfirmModal
        from bluefinctl.widgets.operation_modal import OperationModal

        stacks_tab = self.query_one(StacksTab)
        stack_list = stacks_tab.query_one("#stack-list", ListView)
        if stack_list.index is None or stack_list.index >= len(stacks_tab._stacks):
            return

        stack = stacks_tab._stacks[stack_list.index]

        if stack.status == StackStatus.RUNNING:
            self.notify(f"{stack.name} is already running", title="AI")
            return

        # Confirmation
        vram_warning = ""
        if stack.status == StackStatus.EXCEEDS_VRAM:
            vram_warning = "\n\n[!] WARNING: Stack VRAM exceeds available GPU memory."

        confirmed = await self.app.push_screen_wait(
            ConfirmModal(
                f"Deploy {stack.name}?",
                f"VRAM: {stack.vram_gb} GB | Disk: ~{stack.disk_gb} GB\n"
                f"Category: {stack.category.value}{vram_warning}",
            ),
        )
        if confirmed:
            rc = await self.app.push_screen_wait(
                OperationModal(
                    f"Deploying {stack.name}",
                    steps=deploy_stack_steps(stack),
                ),
            )
            if rc == 0:
                self.notify(f"{stack.name} deployed", title="AI")
                stacks_tab.refresh_stacks()
            else:
                self.notify(f"Failed to deploy {stack.name}", severity="error", title="AI")

    async def _install_selected_ai_tool(self) -> None:
        """Install/update the AI tools kit for the selected Tools tab row."""
        from bluefinctl.core.ai import install_ai_tools_kit_steps
        from bluefinctl.screens._modals import ConfirmModal
        from bluefinctl.widgets.operation_modal import OperationModal

        tools_tab = self.query_one(ToolsTab)
        tool = tools_tab.selected_tool()
        if tool is None:
            self.notify("Select an AI tool first", severity="warning", title="AI")
            return
        if tool.installed:
            self.notify(f"{tool.name} is already installed", title="AI")
            return
        if tool.source != BUNDLE_AI_TOOLS_SOURCE:
            self.notify(
                f"{tool.name} is managed outside bluefinctl",
                severity="warning",
                title="AI",
            )
            return

        confirmed = await self.app.push_screen_wait(
            ConfirmModal(
                f"Install {tool.name}?",
                f"Installing {tool.name} uses the curated AI Tools kit bundle via Homebrew.",
            ),
        )
        if not confirmed:
            return

        rc = await self.app.push_screen_wait(
            OperationModal(
                "Installing AI Tools kit",
                steps=install_ai_tools_kit_steps(),
            ),
        )
        if rc == 0:
            self.notify("AI Tools kit installed", title="AI")
            tools_tab.refresh_tools()
        else:
            self.notify("Failed to install AI Tools kit", severity="error", title="AI")

    async def action_stop_stack(self) -> None:
        """Stop the selected running stack."""
        from bluefinctl.core.ai import StackStatus, stop_stack_steps
        from bluefinctl.widgets.operation_modal import OperationModal

        tabbed = self.query_one(TabbedContent)
        if tabbed.active != "tab-stacks":
            return

        stacks_tab = self.query_one(StacksTab)
        stack_list = stacks_tab.query_one("#stack-list", ListView)
        if stack_list.index is None or stack_list.index >= len(stacks_tab._stacks):
            return

        stack = stacks_tab._stacks[stack_list.index]
        if stack.status != StackStatus.RUNNING:
            self.notify(f"{stack.name} is not running", severity="warning", title="AI")
            return

        rc = await self.app.push_screen_wait(
            OperationModal(
                f"Stopping {stack.name}",
                steps=stop_stack_steps(stack),
            ),
        )
        if rc == 0:
            self.notify(f"{stack.name} stopped", title="AI")
            stacks_tab.refresh_stacks()
        else:
            self.notify(f"Failed to stop {stack.name}", severity="error", title="AI")

    async def action_stack_logs(self) -> None:
        """View logs for the selected stack."""
        from bluefinctl.screens._modals import OperationLogModal

        tabbed = self.query_one(TabbedContent)
        if tabbed.active != "tab-stacks":
            return

        stacks_tab = self.query_one(StacksTab)
        stack_list = stacks_tab.query_one("#stack-list", ListView)
        if stack_list.index is None or stack_list.index >= len(stacks_tab._stacks):
            return

        stack = stacks_tab._stacks[stack_list.index]
        await self.app.push_screen_wait(
            OperationLogModal(
                f"Logs: {stack.name}",
                ["journalctl", "--user", "-u", stack.slug, "--no-pager", "-n", "100"],
            ),
        )
