"""System screen — identity, hardware, health, running services, quick actions.

This is the home screen (bootc systems only). Card-based layout showing:
- Identity (full OCI ref, boot status, hostname)
- Hardware (GPU + VRAM, CPU, RAM)
- Health (GPU driver, systemd, Homebrew status)
- Running Services (pod count, podman-tui launch)
- Active Kits (summary of installed kits)
- Quick Actions (update, devmode, report)
"""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, Static

from bluefinctl.screens._sidebar import Sidebar


class IdentityCard(Static):
    """System identity — full OCI image ref, boot status."""

    DEFAULT_CSS = """
    IdentityCard { height: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Identity", classes="card--title")
        yield Label("Loading...", id="identity-info")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        from bluefinctl.core.system import get_system_info

        info = await get_system_info()
        full_ref = f"ghcr.io/projectbluefin/{info.image_name}:{info.image_tag}"
        self.query_one("#identity-info", Label).update(
            f"  Image:    {full_ref}\n"
            f"  Boot:     {info.boot_status}\n"
            f"  Hostname: {info.hostname or 'unknown'}",
        )


class HardwareCard(Static):
    """Hardware summary — GPU with VRAM, mode."""

    DEFAULT_CSS = """
    HardwareCard { height: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Hardware", classes="card--title")
        yield Label("Loading...", id="hardware-info")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        from bluefinctl.core.system import get_system_info

        info = await get_system_info()
        gpu_line = f"{info.gpu.vendor.upper()} {info.gpu.model}"
        if info.gpu.vram_mb:
            gpu_line += f" ({info.gpu.vram_mb // 1024} GB VRAM)"

        self.query_one("#hardware-info", Label).update(
            f"  GPU:  {gpu_line}\n"
            f"  Mode: {'Developer' if info.devmode else 'Standard'}",
        )


class HealthCard(Static):
    """System health checks — GPU driver, systemd, Homebrew."""

    DEFAULT_CSS = """
    HealthCard { height: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Health", classes="card--title")
        yield Label("Loading...", id="health-info")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        checks: list[str] = []

        # GPU driver
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            checks.append("[ok] GPU driver" if proc.returncode == 0 else "[X] GPU driver")
        except FileNotFoundError:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "rocm-smi",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.communicate()
                checks.append("[ok] GPU driver" if proc.returncode == 0 else "[X] GPU driver")
            except FileNotFoundError:
                checks.append("[--] GPU (no discrete GPU)")

        # systemd
        try:
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "is-system-running",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            status = stdout.decode().strip()
            if status == "running":
                checks.append("[ok] System services")
            elif status == "degraded":
                checks.append("[!] System services (degraded)")
            else:
                checks.append(f"[X] System services ({status})")
        except FileNotFoundError:
            checks.append("[--] systemd unavailable")

        # Homebrew
        try:
            proc = await asyncio.create_subprocess_exec(
                "brew", "--prefix",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            checks.append("[ok] Homebrew" if proc.returncode == 0 else "[X] Homebrew")
        except FileNotFoundError:
            checks.append("[X] Homebrew not found")

        self.query_one("#health-info", Label).update(
            "  " + "  ".join(checks),
        )


class RunningServicesCard(Static):
    """Running pods/containers summary."""

    DEFAULT_CSS = """
    RunningServicesCard { height: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Running Services", classes="card--title")
        yield Label("Loading...", id="services-info")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "podman", "pod", "ls", "--format", "{{.Name}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            pods = [p for p in stdout.decode().strip().split("\n") if p]
            if pods:
                self.query_one("#services-info", Label).update(
                    f"  {len(pods)} pod(s) active\n"
                    f"  [c] Launch podman-tui for details",
                )
            else:
                self.query_one("#services-info", Label).update(
                    "  No pods running\n"
                    "  [c] Launch podman-tui",
                )
        except FileNotFoundError:
            self.query_one("#services-info", Label).update(
                "  podman not found",
            )


class ActiveKitsCard(Static):
    """Summary of active kits."""

    DEFAULT_CSS = """
    ActiveKitsCard { height: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Active Kits", classes="card--title")
        yield Label("Loading...", id="kits-summary")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        from bluefinctl.core.bundles import BundleState, get_bundles

        try:
            bundles = await get_bundles()
            active = [b for b in bundles if b.state in (BundleState.BASE, BundleState.ACTIVE)]
            available = [b for b in bundles if b.state == BundleState.AVAILABLE]

            if active:
                names = ", ".join(b.name for b in active[:5])
                suffix = f" +{len(active) - 5} more" if len(active) > 5 else ""
                self.query_one("#kits-summary", Label).update(
                    f"  {names}{suffix}\n"
                    f"  {len(active)} active / {len(available)} available",
                )
            else:
                self.query_one("#kits-summary", Label).update(
                    "  No kits active — press [3] for Toolkit",
                )
        except Exception:
            self.query_one("#kits-summary", Label).update(
                "  Could not load kit status",
            )


class QuickActionsCard(Static):
    """Quick action shortcuts shown as a card."""

    DEFAULT_CSS = """
    QuickActionsCard { height: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Quick Actions", classes="card--title")
        yield Label(
            "  [u] Update All    [d] Devmode    [r] System Report    [c] podman-tui",
        )


class SystemScreen(Screen[None]):
    """System overview — the home screen for bootc systems."""

    BINDINGS = [
        ("u", "update_all", "Update"),
        ("d", "toggle_devmode", "Devmode"),
        ("r", "system_report", "Report"),
        ("c", "launch_podman_tui", "podman-tui"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Sidebar("system")
            with Vertical(id="main-content"):
                with Container(classes="card"):
                    yield IdentityCard()
                with Container(classes="card"):
                    yield HardwareCard()
                with Container(classes="card"):
                    yield HealthCard()
                with Container(classes="card"):
                    yield RunningServicesCard()
                with Container(classes="card"):
                    yield ActiveKitsCard()
                with Container(classes="card"):
                    yield QuickActionsCard()

    async def action_update_all(self) -> None:
        """Trigger system update via unified progress modal."""
        import shutil

        from bluefinctl.core.progress import IndeterminateParser
        from bluefinctl.widgets.operation_modal import OperationModal

        if shutil.which("uupd"):
            rc = await self.app.push_screen_wait(
                OperationModal(
                    "Update All",
                    command=["pkexec", "uupd", "update", "--all"],
                    parser=IndeterminateParser(),
                ),
            )
            if rc == 0:
                self.notify("Update complete", title="Updates")
            else:
                self.notify("Update failed", severity="error", title="Updates")
        else:
            self.notify("uupd not found", severity="warning", title="Updates")

    async def action_toggle_devmode(self) -> None:
        """Toggle developer mode (add/remove groups)."""
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
                ),
            )
            if confirmed:
                cmds = " && ".join([
                    f"gpasswd -d {username} docker",
                    f"gpasswd -d {username} mock",
                    f"gpasswd -d {username} lxd",
                ])
                rc = await self.app.push_screen_wait(
                    OperationLogModal("Disable Developer Mode", ["pkexec", "bash", "-c", cmds]),
                )
                if rc == 0:
                    self.notify("Developer mode disabled. Log out to apply.", title="Devmode")
        else:
            confirmed = await self.app.push_screen_wait(
                ConfirmModal(
                    "Enable Developer Mode",
                    "Add groups: docker, mock, lxd and install dev tools?",
                ),
            )
            if confirmed:
                cmds = " && ".join([
                    f"usermod -aG docker {username} 2>/dev/null || true",
                    f"usermod -aG mock {username} 2>/dev/null || true",
                    f"usermod -aG lxd {username} 2>/dev/null || true",
                ])
                rc = await self.app.push_screen_wait(
                    OperationLogModal("Enable Developer Mode", ["pkexec", "bash", "-c", cmds]),
                )
                if rc == 0:
                    self.notify("Developer mode enabled. Log out to apply.", title="Devmode")

    async def action_system_report(self) -> None:
        """Generate system report via ujust."""
        import shutil

        from bluefinctl.screens._modals import OperationLogModal

        if shutil.which("ujust"):
            await self.app.push_screen_wait(
                OperationLogModal("System Report", ["ujust", "report"]),
            )
        else:
            self.notify("ujust not found", severity="warning", title="Report")

    def action_launch_podman_tui(self) -> None:
        """Launch podman-tui in a new terminal window."""
        import shutil

        from bluefinctl.util.terminal import launch_in_terminal

        if shutil.which("podman-tui"):
            launch_in_terminal(["podman-tui"], title="podman-tui")
        else:
            self.notify("podman-tui not installed", severity="warning", title="Containers")
