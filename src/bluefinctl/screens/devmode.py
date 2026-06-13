"""DevMode screen — developer experience panel.

TabbedContent with 3 tabs:
  Overview  — status, runtime health, quick actions
  Tools     — developer tool list with install status
  Environments — Podman, Distrobox, Lima
"""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Label, Static, TabbedContent, TabPane

from bluefinctl.screens._sidebar import Sidebar


class OverviewTab(Static):
    """DevMode Overview — status card, runtime health, quick actions."""

    DEFAULT_CSS = """
    OverviewTab { height: auto; padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        with Static(classes="card"):
            yield Label("Status", classes="card--title")
            yield Label("  Checking...", id="devmode-status")
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
        self.run_worker(self._load())

    async def _load(self) -> None:
        from bluefinctl.core.devmode import _check_devmode_active

        loop = asyncio.get_running_loop()
        state = await loop.run_in_executor(None, _check_devmode_active)

        if state.active:
            groups = ", ".join(state.groups or [])
            self.query_one("#devmode-status", Label).update(
                f"  Developer Mode: ACTIVE\n"
                f"  Groups: {groups}",
            )
        else:
            self.query_one("#devmode-status", Label).update(
                "  Developer Mode: INACTIVE\n"
                "  Press Enter to enable developer mode",
            )

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


class ToolsTab(Static):
    """DevMode Tools — list of dev tools with install status."""

    DEFAULT_CSS = """
    ToolsTab { height: auto; padding: 1 0; }
    """

    # Tool categories with (name, description) tuples
    DEV_TOOLS = [
        ("-- Dev Tools --", ""),
        ("podman-compose", "Container orchestration"),
        ("dive", "Container layer explorer"),
        ("kind", "Local Kubernetes"),
        ("devcontainer", "Devcontainer CLI"),
    ]

    PERF_TOOLS = [
        ("-- Performance --", ""),
        ("sysprof", "System profiler"),
        ("bcc", "BPF compiler collection"),
        ("bpftrace", "BPF tracing"),
    ]

    VIRT_TOOLS = [
        ("-- Virtualization --", ""),
        ("qemu-system-x86_64", "QEMU/KVM"),
        ("incus", "Container/VM manager"),
    ]

    def compose(self) -> ComposeResult:
        yield Label("Developer Tools", classes="card--title")
        yield Label("  Loading...", id="tools-list")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        import shutil

        all_tools = self.DEV_TOOLS + self.PERF_TOOLS + self.VIRT_TOOLS
        lines: list[str] = []

        for name, desc in all_tools:
            if name.startswith("--"):
                lines.append(f"\n  {name}")
                continue
            installed = shutil.which(name) is not None
            status = "[ok]" if installed else "[--]"
            lines.append(f"  {status} {name:<20} {desc}")

        self.query_one("#tools-list", Label).update("\n".join(lines))


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
        self.run_worker(self._load())

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
                    + "\n  Action: [Enter] to manage",
                )
            else:
                self.query_one("#env-lima", Label).update(
                    "  WSL-equivalent Ubuntu VM — persistent, $HOME mounted\n"
                    "  [--] Not set up\n"
                    "  Action: [Enter] to run guided setup",
                )
        except FileNotFoundError:
            self.query_one("#env-lima", Label).update(
                "  WSL-equivalent Ubuntu VM\n"
                "  [--] Lima not installed\n"
                "  Action: [Enter] to install and set up",
            )


class DevModeScreen(Screen[None]):
    """Developer mode screen — tools, environments, Lima."""

    BINDINGS = [
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

    def compose(self) -> ComposeResult:
        yield Sidebar(active="devmode")
        with ScrollableContainer(id="devmode-content"):
            with TabbedContent():
                with TabPane("Overview", id="tab-overview"):
                    yield OverviewTab()
                with TabPane("Tools", id="tab-tools"):
                    yield ToolsTab()
                with TabPane("Environments", id="tab-envs"):
                    yield EnvironmentsTab()

    def action_launch_podman_tui(self) -> None:
        """Launch podman-tui in a new terminal."""
        import shutil

        from bluefinctl.util.terminal import launch_in_terminal

        if shutil.which("podman-tui"):
            launch_in_terminal(["podman-tui"], title="podman-tui")
        else:
            self.notify("podman-tui not installed", severity="warning")

    async def action_install_all(self) -> None:
        """Install all missing dev tools."""
        from bluefinctl.screens._modals import ConfirmModal
        from bluefinctl.widgets.operation_modal import OperationModal

        confirmed = await self.app.push_screen_wait(
            ConfirmModal(
                "Install All Dev Tools",
                "Install all missing developer tools via Homebrew?",
            ),
        )
        if confirmed:
            from bluefinctl.core.progress import BrewInstallParser

            rc = await self.app.push_screen_wait(
                OperationModal(
                    "Installing Dev Tools",
                    command=["brew", "install"] + [
                        "podman-compose", "dive", "kind",
                        "devcontainer", "sysprof", "bcc", "bpftrace",
                    ],
                    parser=BrewInstallParser(total_packages=7),
                ),
            )
            if rc == 0:
                self.notify("All dev tools installed", title="DevMode")
