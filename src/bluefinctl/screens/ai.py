"""AI screen — GPU-accelerated AI stack management.

TabbedContent with 2 tabs:
  Stacks (default) — GPU detection + stack catalog with deploy/stop
  Tools            — AI CLI tools kit status
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Static, TabbedContent, TabPane

from bluefinctl.screens._sidebar import Sidebar


class GpuCard(Static):
    """GPU detection card shown at top of Stacks tab."""

    DEFAULT_CSS = """
    GpuCard { height: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Label("GPU", classes="card--title")
        yield Label("  Detecting...", id="gpu-info")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        import asyncio

        from bluefinctl.core.ai import detect_gpu

        loop = asyncio.get_running_loop()
        gpu = await loop.run_in_executor(None, detect_gpu)
        self.query_one("#gpu-info", Label).update(f"  {gpu.display}")


class StacksTab(Static):
    """Stacks tab — catalog with deploy/stop actions."""

    DEFAULT_CSS = """
    StacksTab { height: 1fr; padding: 1 0; }
    #stack-list-container {
        height: 1fr;
    }
    #stack-list {
        height: 1fr;
    }
    #stack-detail {
        width: 1fr;
        height: 1fr;
        padding: 0 2;
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
        with Static(classes="card"):
            yield GpuCard()
        yield Label("")
        with Horizontal(id="stack-list-container"):
            yield ListView(id="stack-list")
            with Vertical(id="stack-detail"):
                yield Label("Select a stack", id="stack-detail-title")
                yield Label("", id="stack-detail-body")

    def on_mount(self) -> None:
        self.run_worker(self._load())

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
            index = event.item.parent.children.index(event.item)  # type: ignore[union-attr]
            self._show_stack_detail(index)


class ToolsTab(Static):
    """AI Tools tab — CLI tools with install status."""

    DEFAULT_CSS = """
    ToolsTab { height: auto; padding: 1 0; }
    """

    AI_TOOLS = [
        ("-- Coding Agents --", ""),
        ("goose", "Block Protocol AI agent"),
        ("claude", "Claude coding agent"),
        ("copilot", "GitHub Copilot terminal"),
        ("-- Local AI --", ""),
        ("lemonade", "AMD-native LLM server"),
        ("whisper-cpp", "Speech-to-text"),
        ("llm", "CLI for language models"),
        ("-- Model Tools --", ""),
        ("docker", "Docker model management"),
    ]

    def compose(self) -> ComposeResult:
        with Static(classes="card"):
            yield Label("AI & ML Tools", classes="card--title")
            yield Label("  Loading...", id="ai-tools-list")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        import shutil

        lines: list[str] = []
        for name, desc in self.AI_TOOLS:
            if name.startswith("--"):
                lines.append(f"\n  {name}")
                continue
            installed = shutil.which(name) is not None
            status = "[ok]" if installed else "[--]"
            lines.append(f"  {status} {name:<20} {desc}")

        self.query_one("#ai-tools-list", Label).update("\n".join(lines))


class AIScreen(Screen[None]):
    """AI workstation management — stack catalog and tools."""

    BINDINGS = [
        Binding("enter", "deploy_stack", "Deploy"),
        Binding("s", "stop_stack", "Stop"),
        Binding("l", "stack_logs", "Logs"),
        Binding("f", "filter_category", "Filter"),
    ]

    DEFAULT_CSS = """
    AIScreen {
        layout: horizontal;
    }
    #ai-content {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Sidebar(active="ai")
        with ScrollableContainer(id="ai-content"), TabbedContent():
            with TabPane("Stacks", id="tab-stacks"):
                yield StacksTab()
            with TabPane("Tools", id="tab-tools"):
                yield ToolsTab()

    async def action_deploy_stack(self) -> None:
        """Deploy the selected stack."""
        from bluefinctl.core.ai import StackStatus
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
            from bluefinctl.core.progress import PodmanPullParser

            rc = await self.app.push_screen_wait(
                OperationModal(
                    f"Deploying {stack.name}",
                    command=[
                        "systemctl", "--user", "start", stack.slug,
                    ],
                    parser=PodmanPullParser(),
                ),
            )
            if rc == 0:
                self.notify(f"{stack.name} deployed", title="AI")
            else:
                self.notify(f"Failed to deploy {stack.name}", severity="error", title="AI")

    async def action_stop_stack(self) -> None:
        """Stop the selected running stack."""
        from bluefinctl.core.ai import StackStatus, stop_stack

        stacks_tab = self.query_one(StacksTab)
        stack_list = stacks_tab.query_one("#stack-list", ListView)
        if stack_list.index is None or stack_list.index >= len(stacks_tab._stacks):
            return

        stack = stacks_tab._stacks[stack_list.index]
        if stack.status != StackStatus.RUNNING:
            self.notify(f"{stack.name} is not running", severity="warning", title="AI")
            return

        success = await stop_stack(stack)
        if success:
            self.notify(f"{stack.name} stopped", title="AI")
            stacks_tab.run_worker(stacks_tab._load())
        else:
            self.notify(f"Failed to stop {stack.name}", severity="error", title="AI")

    async def action_stack_logs(self) -> None:
        """View logs for the selected stack."""
        from bluefinctl.screens._modals import OperationLogModal

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

    def action_filter_category(self) -> None:
        """Toggle category filter (placeholder)."""
        self.notify("Category filter coming soon", title="AI")
