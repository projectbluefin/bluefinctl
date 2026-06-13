"""System screen — identity, hardware, health, running services, quick actions."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.screen import Screen

from bluefinctl.screens._viewswitcher import ViewSwitcher
from bluefinctl.widgets.adw import (
    AdwButtonRow,
    AdwPreferencesGroup,
    AdwPropertyRow,
)


class SystemScreen(Screen[None]):
    """System overview — the home screen for bootc systems."""

    BINDINGS = [
        ("u", "update_all", "Update"),
        ("d", "toggle_devmode", "Devmode"),
        ("r", "system_report", "Report"),
        ("c", "launch_podman_tui", "podman-tui"),
    ]

    DEFAULT_CSS = "SystemScreen { layout: vertical; }"

    def compose(self) -> ComposeResult:
        yield ViewSwitcher("system")
        with ScrollableContainer(id="adw-content"):
            yield AdwPreferencesGroup(
                "System",
                AdwPropertyRow("Image", "Loading…", id="sys-image"),
                AdwPropertyRow("Boot", "Loading…", id="sys-boot"),
                AdwPropertyRow("Hostname", "Loading…", id="sys-hostname"),
            )
            yield AdwPreferencesGroup(
                "Hardware",
                AdwPropertyRow("GPU", "Detecting…", id="sys-gpu"),
                AdwPropertyRow("Mode", "Loading…", id="sys-mode"),
            )
            yield AdwPreferencesGroup(
                "Health",
                AdwPropertyRow("GPU Driver", "Checking…", id="health-gpu"),
                AdwPropertyRow("System Services", "Checking…", id="health-system"),
                AdwPropertyRow("Homebrew", "Checking…", id="health-brew"),
            )
            yield AdwPreferencesGroup(
                "Active Kits",
                AdwPropertyRow("Kits", "Loading…", id="sys-kits"),
            )
            yield AdwPreferencesGroup(
                "Quick Actions",
                AdwButtonRow("Update All", variant="primary", id="btn-update-all"),
                AdwButtonRow("Toggle Developer Mode", id="btn-devmode"),
                AdwButtonRow("System Report", id="btn-report"),
                AdwButtonRow("Launch podman-tui", id="btn-podman-tui"),
            )

    def on_mount(self) -> None:
        self.run_worker(self._load_identity())
        self.run_worker(self._load_health())
        self.run_worker(self._load_kits())

    async def _load_identity(self) -> None:
        import socket

        from bluefinctl.core.system import get_system_info
        info = await get_system_info()
        full_ref = f"ghcr.io/projectbluefin/{info.image_name}:{info.image_tag}"
        self.query_one("#sys-image", AdwPropertyRow).update_value(full_ref)
        self.query_one("#sys-boot", AdwPropertyRow).update_value(info.boot_status)
        self.query_one("#sys-hostname", AdwPropertyRow).update_value(
            info.hostname or socket.gethostname()
        )
        gpu_line = f"{info.gpu.vendor.upper()} {info.gpu.model}"
        if info.gpu.vram_mb:
            gpu_line += f"  ·  {info.gpu.vram_mb // 1024} GB VRAM"
        self.query_one("#sys-gpu", AdwPropertyRow).update_value(gpu_line)
        self.query_one("#sys-mode", AdwPropertyRow).update_value(
            "Developer" if info.devmode else "Standard"
        )

    async def _load_health(self) -> None:
        # GPU driver
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            gpu_status = "✓ ok" if proc.returncode == 0 else "✗ failed"
        except FileNotFoundError:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "rocm-smi",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.communicate()
                gpu_status = "✓ ok" if proc.returncode == 0 else "✗ failed"
            except FileNotFoundError:
                gpu_status = "— no discrete GPU"
        self.query_one("#health-gpu", AdwPropertyRow).update_value(gpu_status)

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
                sys_status = "✓ running"
            elif status == "degraded":
                sys_status = "⚠ degraded"
            else:
                sys_status = f"✗ {status}"
        except FileNotFoundError:
            sys_status = "— unavailable"
        self.query_one("#health-system", AdwPropertyRow).update_value(sys_status)

        # Homebrew
        try:
            proc = await asyncio.create_subprocess_exec(
                "brew", "--prefix",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            brew_status = "✓ ok" if proc.returncode == 0 else "✗ not found"
        except FileNotFoundError:
            brew_status = "✗ not installed"
        self.query_one("#health-brew", AdwPropertyRow).update_value(brew_status)

    async def _load_kits(self) -> None:
        from bluefinctl.core.bundles import BundleState, get_bundles
        try:
            bundles = await get_bundles()
            active = [b for b in bundles if b.state in (BundleState.BASE, BundleState.ACTIVE)]
            if active:
                names = ", ".join(b.name for b in active[:4])
                suffix = f" +{len(active) - 4} more" if len(active) > 4 else ""
                self.query_one("#sys-kits", AdwPropertyRow).update_value(
                    f"{names}{suffix}"
                )
            else:
                self.query_one("#sys-kits", AdwPropertyRow).update_value("None active")
        except Exception:  # noqa: BLE001
            self.query_one("#sys-kits", AdwPropertyRow).update_value("unavailable")

    def on_adw_button_row_pressed(self, event: AdwButtonRow.Pressed) -> None:
        btn_id = event.row.id
        if btn_id == "btn-update-all":
            self.run_worker(self.action_update_all())
        elif btn_id == "btn-devmode":
            self.run_worker(self.action_toggle_devmode())
        elif btn_id == "btn-report":
            self.run_worker(self.action_system_report())
        elif btn_id == "btn-podman-tui":
            self.action_launch_podman_tui()

    async def action_update_all(self) -> None:
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
                    self.notify("Developer mode disabled. Log out to apply.", title="Devmode")
        else:
            confirmed = await self.app.push_screen_wait(
                ConfirmModal("Enable Developer Mode", "Add groups: docker, mock, lxd?")
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
                    self.notify("Developer mode enabled. Log out to apply.", title="Devmode")

    async def action_system_report(self) -> None:
        import shutil

        from bluefinctl.screens._modals import OperationLogModal
        if shutil.which("ujust"):
            await self.app.push_screen_wait(
                OperationLogModal("System Report", ["ujust", "report"])
            )
        else:
            self.notify("ujust not found", severity="warning", title="Report")

    def action_launch_podman_tui(self) -> None:
        import shutil

        from bluefinctl.util.terminal import launch_in_terminal
        if shutil.which("podman-tui"):
            launch_in_terminal(["podman-tui"], title="podman-tui")
        else:
            self.notify("podman-tui not installed", severity="warning", title="Containers")

