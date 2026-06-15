"""System screen — identity, hardware, health, release stream, quick actions."""

from __future__ import annotations

import asyncio

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button

from bluefinctl.core.notify import system_notify
from bluefinctl.screens._viewswitcher import ViewSwitcher
from bluefinctl.widgets.adw import (
    AdwButtonRow,
    AdwButtonsRow,
    AdwPreferencesGroup,
    AdwPropertyRow,
    AdwSwitchRow,
)
from bluefinctl.widgets.ops_bar import OpsBar
from bluefinctl.widgets.rollback_calendar import RollbackCalendar


class SystemScreen(Screen[None]):
    """System overview — the home screen for bootc systems."""

    BINDINGS = [
        ("u", "update_all", "Update"),
    ]

    DEFAULT_CSS = """
    SystemScreen { layout: vertical; overflow: hidden hidden; }
    .adw-cols { height: auto; }
    .adw-col  { width: 1fr; height: auto; padding: 0 2; }
    #adw-content { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield ViewSwitcher("system")
        with ScrollableContainer(id="adw-content"):
            with Horizontal(classes="adw-cols"):
                # ── left column — image identity, hardware, health ────────────
                with Vertical(classes="adw-col"):
                    yield AdwPreferencesGroup(
                        "Image",
                        AdwPropertyRow("Image",   "Loading…", id="sys-image"),
                        AdwPropertyRow("Channel", "Loading…", id="sys-channel"),
                        AdwPropertyRow("Status",  "Loading…", id="sys-boot"),
                    )
                    yield AdwPreferencesGroup(
                        "System",
                        AdwPropertyRow("Hostname", "Loading…",   id="sys-hostname"),
                        AdwPropertyRow("GPU",      "Detecting…", id="sys-gpu"),
                    )
                    yield AdwPreferencesGroup(
                        "Health",
                        AdwPropertyRow("GPU Driver",      "Checking…", id="health-gpu"),
                        AdwPropertyRow("System Services", "Checking…", id="health-system"),
                        AdwPropertyRow("Homebrew",        "Checking…", id="health-brew"),
                    )

                # ── right column — updates, beta, rollback ────────────────────
                with Vertical(classes="adw-col"):
                    yield AdwPreferencesGroup(
                        "Updates",
                        AdwButtonsRow(
                            Button("Update All", variant="primary", id="btn-update-all"),
                        ),
                        AdwSwitchRow(
                            "Testing Stream",
                            subtitle="Switch to the testing image tag — reboot to apply",
                            id="channel-testing-switch",
                        ),
                    )
                    yield AdwPreferencesGroup(
                        "Rollback",
                        AdwButtonRow(
                            "Roll Back to Previous Build",
                            variant="destructive",
                            id="btn-rollback",
                        ),
                        RollbackCalendar(id="rollback-calendar"),
                    )
        yield OpsBar()

    def on_mount(self) -> None:
        self.run_worker(self._load_identity(), exclusive=False)
        self.run_worker(self._load_health(),   exclusive=False)
        self.run_worker(self._load_update_status(), exclusive=False)

    # ─────────────────────────────────────────────────────────────────────────
    # Data loading
    # ─────────────────────────────────────────────────────────────────────────

    async def _load_identity(self) -> None:
        from bluefinctl.core.system import get_system_info
        info = await get_system_info()
        self.query_one("#sys-image",    AdwPropertyRow).update_value(info.full_clean_ref)
        self.query_one("#sys-boot",     AdwPropertyRow).update_value(info.boot_status)
        self.query_one("#sys-hostname", AdwPropertyRow).update_value(info.hostname)

        tag = (info.image_tag or "").lower()
        channel = "testing ⚗" if "testing" in tag else "stable"
        self.query_one("#sys-channel", AdwPropertyRow).update_value(channel)

        gpu_line = f"{info.gpu.vendor.upper()} {info.gpu.model}".strip()
        if info.gpu.vram_mb:
            gpu_line += f"  ·  {info.gpu.vram_mb // 1024} GB VRAM"
        self.query_one("#sys-gpu", AdwPropertyRow).update_value(gpu_line)

        # Release Stream toggle reflects actual channel
        self.query_one("#channel-testing-switch", AdwSwitchRow).set_value("testing" in tag)

        # Rollback calendar
        import contextlib
        with contextlib.suppress(Exception):
            cal = self.query_one(RollbackCalendar)
            if info.image_ref:
                cal.configure(info.clean_image_ref, info.image_tag or "latest")

    async def _load_health(self) -> None:
        # GPU driver
        gpu_status = "— no discrete GPU"
        for cmd in ("nvidia-smi", "rocm-smi"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.communicate()
                gpu_status = "✓ ok" if proc.returncode == 0 else "✗ failed"
                break
            except FileNotFoundError:
                continue
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
            sys_status = (
                "✓ running" if status == "running" else
                "⚠ degraded" if status == "degraded" else
                f"✗ {status}"
            )
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


    async def _load_update_status(self) -> None:
        """Show last update check result in the OpsBar."""
        import contextlib
        ops = self.query_one(OpsBar)
        with contextlib.suppress(Exception):
            from bluefinctl.core.updates import get_update_status
            status = await get_update_status()
            if status.focus_mode and status.focus_mode.active:
                ops.set_idle("⏸  Updates paused — focus mode active")
            elif status.brew_updates > 0:
                ops.set_idle(f"↑  {status.brew_updates} Homebrew package(s) available")
            else:
                ops.set_idle("✓  System up to date")
            return
        ops.set_idle("Ready")

    # ─────────────────────────────────────────────────────────────────────────
    # Event handlers
    # ─────────────────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-update-all")
    def _on_update_all(self) -> None:
        self._do_update_all()

    @on(Button.Pressed, "#btn-op-confirm")
    def _on_op_confirm(self) -> None:
        op = self.query_one(OpsBar).pending_op or ""
        if op == "rollback":
            self._exec_rollback(None)
        elif op.startswith("rollback:"):
            self._exec_rollback(op.split(":", 1)[1])

    @on(Button.Pressed, "#btn-op-cancel")
    def _on_op_cancel(self) -> None:
        self.query_one(OpsBar).set_idle("Ready")

    @on(AdwButtonRow.Pressed)
    def _on_rollback_row(self, event: AdwButtonRow.Pressed) -> None:
        if event.row.id == "btn-rollback":
            self._do_rollback()

    def on_adw_switch_row_changed(self, event: AdwSwitchRow.Changed) -> None:
        if event.row.id == "channel-testing-switch":
            self._switch_channel("testing" if event.value else "stable")

    def on_rollback_calendar_date_selected(
        self, event: RollbackCalendar.DateSelected
    ) -> None:
        self._rollback_to(event.image_ref, label=str(event.date))

    # ─────────────────────────────────────────────────────────────────────────
    # Operations (all inline — no OperationModal)
    # ─────────────────────────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _do_update_all(self) -> None:
        import shutil
        ops = self.query_one(OpsBar)
        if not shutil.which("uupd"):
            ops.set_idle("✗  uupd not found")
            return
        ops.set_running("Updating system…")
        try:
            proc = await asyncio.create_subprocess_exec(
                "pkexec", "/usr/bin/uupd",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            if proc.returncode == 0:
                ops.set_idle("✓  Update complete")
            else:
                ops.set_idle(f"✗  Update failed (exit {proc.returncode})")
        except Exception as e:  # noqa: BLE001
            ops.set_idle(f"✗  {e}")

    @work(exclusive=True)
    async def _switch_channel(self, channel: str) -> None:
        ops = self.query_one(OpsBar)
        ops.set_running(f"Switching to {channel}…")
        try:
            from bluefinctl.core.system import get_system_info
            info   = await get_system_info()
            base   = info.clean_image_ref  # e.g. ghcr.io/projectbluefin/dakota
            if not base:
                raise RuntimeError("Cannot determine current image ref")
            target = f"{base}:{'testing' if channel == 'testing' else 'latest'}"
            proc   = await asyncio.create_subprocess_exec(
                "pkexec", "bootc", "switch", target,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            if proc.returncode == 0:
                ops.set_idle(f"✓  Switched to {channel} — reboot to apply")
                return
            raise RuntimeError(f"bootc switch exited {proc.returncode}")
        except Exception as e:  # noqa: BLE001
            ops.set_idle(f"✗  {e}")
            # Revert toggle to actual state
            self.run_worker(self._load_identity())

    @work(exclusive=True)
    async def _do_rollback(self) -> None:
        ops = self.query_one(OpsBar)
        ops.set_confirm("Roll back to previous build?", "rollback")

    @work(exclusive=True)
    async def _rollback_to(self, image_ref: str, label: str = "") -> None:
        ops = self.query_one(OpsBar)
        what = label or image_ref
        ops.set_confirm(f"Roll back to {what}?", f"rollback:{image_ref}")

    @work(exclusive=True)
    async def _exec_rollback(self, image_ref: str | None) -> None:
        ops = self.query_one(OpsBar)
        ops.set_running("Rolling back…")
        try:
            if image_ref:
                cmd = ["pkexec", "bootc", "switch", image_ref]
            else:
                cmd = ["pkexec", "bootc", "rollback"]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            if proc.returncode == 0:
                ops.set_idle("✓  Rollback staged — reboot to apply")
            else:
                ops.set_idle(f"✗  Rollback failed (exit {proc.returncode})")
        except Exception as e:  # noqa: BLE001
            ops.set_idle(f"✗  {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Keybinding actions
    # ─────────────────────────────────────────────────────────────────────────

    async def action_update_all(self) -> None:
        self._do_update_all()

    @work
    async def action_toggle_devmode(self) -> None:
        import os

        from bluefinctl.core.devmode import _check_devmode_active
        from bluefinctl.screens._modals import ConfirmModal, OperationLogModal
        state    = _check_devmode_active()
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
                    system_notify("DevMode", "Developer mode disabled. Log out to apply.")
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
                    system_notify("DevMode", "Developer mode enabled. Log out to apply.")

    @work(exclusive=True)
    async def action_system_report(self) -> None:
        import shutil
        ops = self.query_one(OpsBar)
        if not shutil.which("ujust"):
            ops.set_idle("✗  ujust not found")
            return
        ops.set_running("Generating system report…")
        try:
            proc = await asyncio.create_subprocess_exec(
                "ujust", "report",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            if proc.returncode == 0:
                ops.set_idle("✓  Report submitted")
            else:
                ops.set_idle(f"✗  Report failed (exit {proc.returncode})")
        except Exception as e:  # noqa: BLE001
            ops.set_idle(f"✗  {e}")

    def action_launch_podman_tui(self) -> None:
        import shutil

        from bluefinctl.util.terminal import launch_in_terminal
        if shutil.which("podman-tui"):
            launch_in_terminal(["podman-tui"], title="podman-tui")
        else:
            system_notify("Containers", "podman-tui not installed", urgency="low")
