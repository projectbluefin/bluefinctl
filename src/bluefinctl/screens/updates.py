"""Updates screen - uupd strategy, focus mode, channel management.

Controls:
- Update strategy (automatic/notify/manual/scheduled)
- Per-layer toggles (OS image, flatpaks, brew)
- Focus mode (pause everything)
- Channel (stable/testing/pinned)
- Rollback info
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, RadioButton, RadioSet, Static, Switch

from bluefinctl.screens._sidebar import Sidebar


class StrategyCard(Static):
    """Update strategy selector."""

    DEFAULT_CSS = """
    StrategyCard { height: auto; padding: 1 2; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Update Strategy", classes="card--title")
        with RadioSet(id="strategy-radios"):
            yield RadioButton("Automatic - updates apply silently", value=True, id="strat-auto")
            yield RadioButton("Notify - download, ask before reboot", id="strat-notify")
            yield RadioButton("Manual - only when I say so", id="strat-manual")
            yield RadioButton("Scheduled - pick a maintenance window", id="strat-sched")

    def on_mount(self) -> None:
        self.run_worker(self._load_strategy())

    async def _load_strategy(self) -> None:
        from bluefinctl.core.updates import UpdateStrategy, get_update_status

        status = await get_update_status()
        strategy_to_id = {
            UpdateStrategy.AUTOMATIC: 0,
            UpdateStrategy.NOTIFY: 1,
            UpdateStrategy.MANUAL: 2,
            UpdateStrategy.SCHEDULED: 3,
        }
        idx = strategy_to_id.get(status.strategy, 0)
        radio_set = self.query_one("#strategy-radios", RadioSet)
        radio_set.action_select_button(idx)


class FocusModeCard(Static):
    """Focus mode toggle - pause all updates."""

    DEFAULT_CSS = """
    FocusModeCard { height: auto; padding: 1 2; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Focus Mode", classes="card--title")
        with Horizontal():
            yield Switch(value=False, id="focus-switch")
            yield Label(
                "  Pause all updates until you're ready.\n"
                "  Use during training runs, demos, or deep work.",
                id="focus-description",
            )

    def on_mount(self) -> None:
        self.run_worker(self._load_state())

    async def _load_state(self) -> None:
        from bluefinctl.core.updates import get_update_status

        status = await get_update_status()
        switch = self.query_one("#focus-switch", Switch)
        if status.focus_mode and status.focus_mode.active:
            switch.value = True


class LayerToggles(Static):
    """Per-layer update control."""

    DEFAULT_CSS = """
    LayerToggles { height: auto; padding: 1 2; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Per-Layer Control", classes="card--title")
        with Horizontal():
            yield Switch(value=True, id="layer-os")
            yield Label("  OS Image (bootc)")
        with Horizontal():
            yield Switch(value=True, id="layer-flatpak")
            yield Label("  Flatpaks")
        with Horizontal():
            yield Switch(value=True, id="layer-brew")
            yield Label("  Homebrew")

    def on_mount(self) -> None:
        self.run_worker(self._load_layers())

    async def _load_layers(self) -> None:
        import json
        from pathlib import Path

        UUPD = Path("/etc/uupd/config.json")
        os_on = flatpak_on = brew_on = True
        if UUPD.exists():
            try:
                cfg = json.loads(UUPD.read_text())
                modules = cfg.get("modules", {})
                os_on = not modules.get("bootc", {}).get("disable", False)
                flatpak_on = not modules.get("flatpak", {}).get("disable", False)
                brew_on = not modules.get("brew", {}).get("disable", False)
            except Exception:  # noqa: BLE001
                pass
        self.query_one("#layer-os", Switch).value = os_on
        self.query_one("#layer-flatpak", Switch).value = flatpak_on
        self.query_one("#layer-brew", Switch).value = brew_on


class ChannelCard(Static):
    """Update channel (stable/testing)."""

    DEFAULT_CSS = """
    ChannelCard { height: auto; padding: 1 2; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Channel", classes="card--title")
        yield Label("Loading...", id="channel-info")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        from bluefinctl.core.system import get_system_info

        info = await get_system_info()
        channel = info.image_tag or "unknown"
        ref = info.image_ref or "-"

        self.query_one("#channel-info", Label).update(
            f"  Current: {channel}\n"
            f"  Ref:     {ref}\n"
            f"\n"
            f"  [s]table  [t]esting  [p]in version"
        )


class RollbackCard(Static):
    """Rollback information."""

    DEFAULT_CSS = """
    RollbackCard { height: auto; padding: 1 2; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Rollback", classes="card--title")
        yield Label("Loading...", id="rollback-info")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        import asyncio
        import json

        try:
            proc = await asyncio.create_subprocess_exec(
                "bootc", "status", "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                data = json.loads(stdout)
                status = data.get("status", {})
                rollback = status.get("rollback", {})
                if rollback:
                    image = rollback.get("image", {}).get("image", {}).get("image", "unknown")
                    self.query_one("#rollback-info", Label).update(
                        f"  Previous: {image}\n"
                        f"  Press [R] to rollback to previous deployment"
                    )
                else:
                    self.query_one("#rollback-info", Label).update(
                        "  No previous deployment available"
                    )
        except (FileNotFoundError, OSError):
            self.query_one("#rollback-info", Label).update(
                "  bootc not available"
            )


class UpdatesScreen(Screen):
    """Update management - strategy, focus mode, channel."""

    BINDINGS = [
        ("f", "toggle_focus", "Focus Mode"),
        ("u", "update_now", "Update Now"),
        ("R", "rollback", "Rollback"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Sidebar("updates")
            with Vertical(id="main-content"):
                with Vertical(classes="card"):
                    yield StrategyCard()
                with Vertical(classes="card"):
                    yield FocusModeCard()
                with Vertical(classes="card"):
                    yield LayerToggles()
                with Vertical(classes="card"):
                    yield ChannelCard()
                with Vertical(classes="card"):
                    yield RollbackCard()

    async def action_toggle_focus(self) -> None:
        from bluefinctl.core.updates import (
            activate_focus_mode,
            deactivate_focus_mode,
            get_update_status,
        )
        from bluefinctl.screens._modals import ConfirmModal, InputModal

        status = await get_update_status()
        if status.focus_mode and status.focus_mode.active:
            confirmed = await self.app.push_screen_wait(
                ConfirmModal("Disable Focus Mode", "Resume automatic updates now?")
            )
            if confirmed:
                await deactivate_focus_mode()
                self.notify("Focus mode disabled - updates resumed", title="Focus Mode")
                self.query_one("#focus-switch", Switch).value = False
        else:
            hours_str = await self.app.push_screen_wait(
                InputModal(
                    "Enable Focus Mode",
                    "Hours until auto-resume (blank = indefinite)",
                )
            )
            if hours_str is not None:
                hours = int(hours_str) if hours_str.strip().isdigit() else None
                await activate_focus_mode(duration_hours=hours)
                self.notify("Focus mode enabled - updates paused", title="Focus Mode")
                self.query_one("#focus-switch", Switch).value = True

    async def action_update_now(self) -> None:
        from bluefinctl.screens._modals import OperationLogModal

        rc = await self.app.push_screen_wait(
            OperationLogModal("Run Update", ["systemctl", "start", "--wait", "uupd.service"])
        )
        if rc == 0:
            self.notify("Update complete", title="Update")
        else:
            self.notify(f"Update failed (exit {rc})", severity="error", title="Update")

    async def action_rollback(self) -> None:
        from bluefinctl.screens._modals import ConfirmModal, OperationLogModal

        confirmed = await self.app.push_screen_wait(
            ConfirmModal(
                "Rollback OS",
                "Roll back to previous image? System will reboot after.",
            )
        )
        if confirmed:
            await self.app.push_screen_wait(
                OperationLogModal("Rollback", ["pkexec", "bootc", "rollback"])
            )
