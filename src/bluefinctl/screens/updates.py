"""Updates screen — uupd strategy, focus mode, channel management."""

from __future__ import annotations

import contextlib

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, RadioButton, RadioSet, Static, Switch

from bluefinctl.screens._sidebar import Sidebar


class StrategyCard(Static):
    DEFAULT_CSS = "StrategyCard { height: auto; padding: 1 2; }"

    def compose(self) -> ComposeResult:
        yield Label("Update Strategy", classes="card--title")
        with RadioSet(id="strategy-radios"):
            yield RadioButton("Automatic — updates apply silently", value=True, id="strat-auto")
            yield RadioButton("Notify — download, ask before reboot", id="strat-notify")
            yield RadioButton("Manual — only when I say so", id="strat-manual")

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from bluefinctl.core.updates import UpdateStrategy, get_update_status
        status = await get_update_status()
        idx = {
            UpdateStrategy.AUTOMATIC: 0,
            UpdateStrategy.NOTIFY: 1,
            UpdateStrategy.MANUAL: 2,
        }.get(status.strategy, 0)
        buttons = list(self.query_one(RadioSet).query(RadioButton))
        if idx < len(buttons):
            with self.prevent(RadioSet.Changed):
                buttons[idx].value = True

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        from bluefinctl.core.updates import UpdateStrategy, set_update_strategy
        strategy = [UpdateStrategy.AUTOMATIC, UpdateStrategy.NOTIFY, UpdateStrategy.MANUAL][
            min(event.index, 2)
        ]
        self.run_worker(set_update_strategy(strategy), exclusive=True)
        self.app.notify(f"Strategy: {strategy.value}", title="Updates")


class FocusModeCard(Static):
    DEFAULT_CSS = "FocusModeCard { height: auto; padding: 1 2; }"

    def compose(self) -> ComposeResult:
        yield Label("Focus Mode", classes="card--title")
        with Horizontal():
            yield Switch(value=False, id="focus-switch")
            yield Label("  Pause all updates (demos, deep work, training runs)")

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from bluefinctl.core.updates import get_update_status
        status = await get_update_status()
        if status.focus_mode and status.focus_mode.active:
            with self.prevent(Switch.Changed):
                self.query_one("#focus-switch", Switch).value = True

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id != "focus-switch":
            return
        self.run_worker(self._toggle(event.value), exclusive=True)

    async def _toggle(self, on: bool) -> None:
        from bluefinctl.core.updates import activate_focus_mode, deactivate_focus_mode
        if on:
            await activate_focus_mode()
            self.app.notify("Focus mode ON — updates paused", title="Focus Mode")
        else:
            await deactivate_focus_mode()
            self.app.notify("Focus mode OFF — updates resumed", title="Focus Mode")


class LayerToggles(Static):
    DEFAULT_CSS = "LayerToggles { height: auto; padding: 1 2; }"

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
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        import json
        from pathlib import Path
        uupd_config = Path("/etc/uupd/config.json")
        os_on = flatpak_on = brew_on = True
        if uupd_config.exists():
            with contextlib.suppress(Exception):
                cfg = json.loads(uupd_config.read_text())
                modules = cfg.get("modules", {})
                os_on = not modules.get("bootc", {}).get("disable", False)
                flatpak_on = not modules.get("flatpak", {}).get("disable", False)
                brew_on = not modules.get("brew", {}).get("disable", False)
        with self.prevent(Switch.Changed):
            self.query_one("#layer-os", Switch).value = os_on
            self.query_one("#layer-flatpak", Switch).value = flatpak_on
            self.query_one("#layer-brew", Switch).value = brew_on

    def on_switch_changed(self, event: Switch.Changed) -> None:
        layer_map = {"layer-os": "bootc", "layer-flatpak": "flatpak", "layer-brew": "brew"}
        layer = layer_map.get(event.switch.id or "")
        if not layer:
            return
        from bluefinctl.core.updates import set_layer_enabled
        self.run_worker(set_layer_enabled(layer, event.value), exclusive=True)
        self.app.notify(
            f"{layer.capitalize()} updates {'enabled' if event.value else 'disabled'}",
            title="Updates",
        )


class ChannelCard(Static):
    """Channel switcher — stable / testing with real buttons."""

    DEFAULT_CSS = """
    ChannelCard { height: auto; padding: 1 2; }
    #channel-info { margin-bottom: 1; }
    #channel-buttons { height: 3; }
    #channel-buttons Button { margin-right: 1; }
    Button.-active-channel { background: $accent; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Channel", classes="card--title")
        yield Label("Detecting current channel...", id="channel-info")
        with Horizontal(id="channel-buttons"):
            yield Button("Stable", id="btn-stable", variant="primary")
            yield Button("Testing", id="btn-testing")
            yield Button("Update Now", id="btn-update-now", variant="success")

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from bluefinctl.core.system import get_system_info
        info = await get_system_info()
        channel = info.image_tag or "unknown"
        ref = info.image_ref or "unknown"
        self.query_one("#channel-info", Label).update(
            f"  Current: [bold]{channel}[/bold]\n  Ref: {ref}"
        )
        # Highlight active channel button
        is_testing = "testing" in channel.lower()
        if not is_testing:
            self.query_one("#btn-stable", Button).add_class("-active-channel")
        else:
            self.query_one("#btn-testing", Button).add_class("-active-channel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-stable":
            self.app.call_later(self.app.run_action, "channel_stable")
        elif event.button.id == "btn-testing":
            self.app.call_later(self.app.run_action, "channel_testing")
        elif event.button.id == "btn-update-now":
            self.app.call_later(self.app.run_action, "update_now")


class RollbackCard(Static):
    DEFAULT_CSS = "RollbackCard { height: auto; padding: 1 2; }"

    def compose(self) -> ComposeResult:
        yield Label("Rollback", classes="card--title")
        yield Label("Checking...", id="rollback-info")
        yield Button("Rollback to previous", id="btn-rollback", variant="warning")

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

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
                rollback = data.get("status", {}).get("rollback", {})
                if rollback:
                    image = rollback.get("image", {}).get("image", {}).get("image", "unknown")
                    self.query_one("#rollback-info", Label).update(f"  Previous: {image}")
                    return
        except (FileNotFoundError, OSError):
            pass
        self.query_one("#rollback-info", Label).update("  No rollback available")
        self.query_one("#btn-rollback", Button).disabled = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-rollback":
            self.app.call_later(self.app.run_action, "rollback")


class UpdatesScreen(Screen[None]):
    """Updates — strategy, focus mode, layers, channel, rollback."""

    BINDINGS = [
        Binding("u", "update_now", "Update Now"),
        Binding("s", "channel_stable", "Stable"),
        Binding("t", "channel_testing", "Testing"),
        Binding("R", "rollback", "Rollback"),
    ]

    DEFAULT_CSS = """
    UpdatesScreen { layout: horizontal; }
    #updates-scroll {
        width: 1fr;
        height: 1fr;
        overflow-y: auto;
        padding: 1 2;
    }
    .card {
        border: round $border;
        background: $surface;
        margin-bottom: 1;
        padding: 1 2;
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield Sidebar(active="updates")
        with ScrollableContainer(id="updates-scroll"):
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

    async def action_channel_stable(self) -> None:
        await self._switch_channel("stable")

    async def action_channel_testing(self) -> None:
        await self._switch_channel("testing")

    async def _switch_channel(self, channel: str) -> None:
        from bluefinctl.core.system import get_system_info
        from bluefinctl.screens._modals import ConfirmModal, OperationLogModal
        try:
            info = await get_system_info()
            if not info.image_ref or ":" not in info.image_ref:
                self.notify("Cannot determine current image ref", severity="error")
                return
            base = info.image_ref.rsplit(":", 1)[0]
            target = f"{base}:{'testing' if channel == 'testing' else 'latest'}"
        except Exception:  # noqa: BLE001
            self.notify("Cannot determine current image ref", severity="error")
            return
        confirmed = await self.app.push_screen_wait(
            ConfirmModal(
                f"Switch to {channel.capitalize()}",
                f"Target: {target}\n\nA reboot is required to apply.",
            )
        )
        if confirmed:
            await self.app.push_screen_wait(
                OperationLogModal(f"Switch to {channel}", ["pkexec", "bootc", "switch", target])
            )
            self.notify(f"Switched to {channel}. Reboot to apply.", title="Channel")
            self.query_one(ChannelCard).run_worker(
                self.query_one(ChannelCard)._load(), exclusive=True
            )

    async def action_update_now(self) -> None:
        from bluefinctl.screens._modals import ConfirmModal, OperationLogModal
        confirmed = await self.app.push_screen_wait(
            ConfirmModal("Run Update", "Trigger uupd system update now?")
        )
        if confirmed:
            rc = await self.app.push_screen_wait(
                OperationLogModal("Update", ["systemctl", "start", "--wait", "uupd.service"])
            )
            if rc == 0:
                self.notify("Update complete", title="Update")
            else:
                self.notify(f"Update failed (exit {rc})", severity="error", title="Update")

    async def action_rollback(self) -> None:
        from bluefinctl.screens._modals import ConfirmModal, OperationLogModal
        confirmed = await self.app.push_screen_wait(
            ConfirmModal("Rollback OS", "Roll back to previous image? Reboot required.")
        )
        if confirmed:
            await self.app.push_screen_wait(
                OperationLogModal("Rollback", ["pkexec", "bootc", "rollback"])
            )
