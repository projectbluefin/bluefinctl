"""Updates screen — uupd strategy, focus mode, channel management.

Implemented as a GNOME HIG preferences page using AdwPreferencesGroup rows.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import Screen

from bluefinctl.screens._sidebar import Sidebar
from bluefinctl.widgets.adw import (
    AdwButtonRow,
    AdwComboRow,
    AdwPreferencesGroup,
    AdwPropertyRow,
    AdwSwitchRow,
)


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
    """

    def compose(self) -> ComposeResult:
        yield Sidebar(active="updates")
        with ScrollableContainer(id="adw-content"):
            yield AdwPreferencesGroup(
                "Update Strategy",
                AdwComboRow(
                    "Strategy",
                    subtitle="How and when updates are applied",
                    choices=["Automatic", "Notify", "Manual"],
                    value="Automatic",
                    id="strategy-row",
                ),
            )
            yield AdwPreferencesGroup(
                "Update Layers",
                AdwSwitchRow(
                    "OS Image",
                    subtitle="Include bootc system image",
                    id="layer-os",
                ),
                AdwSwitchRow(
                    "Flatpaks",
                    subtitle="Include Flatpak app updates",
                    id="layer-flatpak",
                ),
                AdwSwitchRow(
                    "Homebrew",
                    subtitle="Include Homebrew package updates",
                    id="layer-brew",
                ),
            )
            yield AdwPreferencesGroup(
                "Focus Mode",
                AdwSwitchRow(
                    "Focus Mode",
                    subtitle="Pause all updates (demos, deep work, training runs)",
                    id="focus-switch",
                ),
            )
            yield AdwPreferencesGroup(
                "Channel",
                AdwPropertyRow("Current", "Detecting…", id="channel-info"),
                AdwButtonRow("Switch to Testing", id="btn-testing"),
                AdwButtonRow("Switch to Stable", id="btn-stable"),
                AdwButtonRow("Update Now", variant="primary", id="btn-update-now"),
            )
            yield AdwPreferencesGroup(
                "Rollback",
                AdwPropertyRow("Previous", "Checking…", id="rollback-info"),
                AdwButtonRow(
                    "Roll Back to Previous", variant="destructive", id="btn-rollback"
                ),
            )

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        """Load all update state and populate the rows."""
        import asyncio
        import contextlib
        import json
        from pathlib import Path

        from bluefinctl.core.updates import UpdateStrategy, get_update_status

        status = await get_update_status()

        # Strategy
        strategy_label = {
            UpdateStrategy.AUTOMATIC: "Automatic",
            UpdateStrategy.NOTIFY: "Notify",
            UpdateStrategy.MANUAL: "Manual",
        }.get(status.strategy, "Automatic")
        self.query_one("#strategy-row", AdwComboRow).set_value(strategy_label)

        # Focus mode
        if status.focus_mode and status.focus_mode.active:
            self.query_one("#focus-switch", AdwSwitchRow).set_value(True)

        # Layer toggles
        uupd_config = Path("/etc/uupd/config.json")
        os_on = flatpak_on = brew_on = True
        if uupd_config.exists():
            with contextlib.suppress(Exception):
                cfg = json.loads(uupd_config.read_text())
                modules = cfg.get("modules", {})
                os_on = not modules.get("bootc", {}).get("disable", False)
                flatpak_on = not modules.get("flatpak", {}).get("disable", False)
                brew_on = not modules.get("brew", {}).get("disable", False)
        self.query_one("#layer-os", AdwSwitchRow).set_value(os_on)
        self.query_one("#layer-flatpak", AdwSwitchRow).set_value(flatpak_on)
        self.query_one("#layer-brew", AdwSwitchRow).set_value(brew_on)

        # Channel
        try:
            from bluefinctl.core.system import get_system_info
            info = await get_system_info()
            channel = info.image_tag or "unknown"
            self.query_one("#channel-info", AdwPropertyRow).update_value(channel)
            is_testing = "testing" in channel.lower()
            self.query_one("#btn-testing", AdwButtonRow).display = not is_testing
            self.query_one("#btn-stable", AdwButtonRow).display = is_testing
        except Exception:  # noqa: BLE001
            self.query_one("#channel-info", AdwPropertyRow).update_value("unavailable")

        # Rollback
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
                    image = (
                        rollback.get("image", {})
                        .get("image", {})
                        .get("image", "unknown")
                    )
                    self.query_one("#rollback-info", AdwPropertyRow).update_value(image)
                    return
            self.query_one("#rollback-info", AdwPropertyRow).update_value("none")
            self.query_one("#btn-rollback", AdwButtonRow).disabled = True
        except (FileNotFoundError, OSError):
            self.query_one("#rollback-info", AdwPropertyRow).update_value("unavailable")
            self.query_one("#btn-rollback", AdwButtonRow).disabled = True

    def on_adw_switch_row_changed(self, event: AdwSwitchRow.Changed) -> None:
        row_id = event.row.id
        if row_id == "focus-switch":
            self.run_worker(self._toggle_focus(event.value), exclusive=True)
        elif row_id in ("layer-os", "layer-flatpak", "layer-brew"):
            layer_map = {"layer-os": "bootc", "layer-flatpak": "flatpak", "layer-brew": "brew"}
            layer = layer_map[row_id]
            from bluefinctl.core.updates import set_layer_enabled
            self.run_worker(set_layer_enabled(layer, event.value), exclusive=True)
            self.notify(
                f"{layer.capitalize()} updates {'enabled' if event.value else 'disabled'}",
                title="Updates",
            )

    async def _toggle_focus(self, on: bool) -> None:
        from bluefinctl.core.updates import activate_focus_mode, deactivate_focus_mode
        if on:
            await activate_focus_mode()
            self.notify("Focus mode ON — updates paused", title="Focus Mode")
        else:
            await deactivate_focus_mode()
            self.notify("Focus mode OFF — updates resumed", title="Focus Mode")

    def on_adw_combo_row_changed(self, event: AdwComboRow.Changed) -> None:
        if event.row.id == "strategy-row":
            from bluefinctl.core.updates import UpdateStrategy, set_update_strategy
            strategy_map = {
                "Automatic": UpdateStrategy.AUTOMATIC,
                "Notify": UpdateStrategy.NOTIFY,
                "Manual": UpdateStrategy.MANUAL,
            }
            strategy = strategy_map.get(event.value, UpdateStrategy.AUTOMATIC)
            self.run_worker(set_update_strategy(strategy), exclusive=True)
            self.notify(f"Strategy: {strategy.value}", title="Updates")

    def on_adw_button_row_pressed(self, event: AdwButtonRow.Pressed) -> None:
        btn_id = event.row.id
        if btn_id == "btn-stable":
            self.run_worker(self._switch_channel("stable"))
        elif btn_id == "btn-testing":
            self.run_worker(self._switch_channel("testing"))
        elif btn_id == "btn-update-now":
            self.run_worker(self.action_update_now())
        elif btn_id == "btn-rollback":
            self.run_worker(self.action_rollback())

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
            self.run_worker(self._load(), exclusive=True)

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

