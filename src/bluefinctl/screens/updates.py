"""Updates screen — image info, update schedule, components, focus mode, rollback.

Design:
  • Full-width monospace image banner at the top (always visible, never truncated)
  • Staged-update alert bar beneath the banner when a reboot is pending
  • Two-column layout for all controls
  • Update Now + Check for Updates pinned to the bottom-right above the OpsBar
  • All operations run inline — no modal dialogs
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label

from bluefinctl.screens._viewswitcher import ViewSwitcher
from bluefinctl.widgets.adw import (
    AdwButtonRow,
    AdwPreferencesGroup,
    AdwPropertyRow,
    AdwSwitchRow,
)
from bluefinctl.widgets.ops_bar import OpsBar


class UpdatesScreen(Screen[None]):
    """Updates — image info, schedule, components, focus mode, rollback."""

    BINDINGS = [
        Binding("u", "update_now", "Update Now"),
        Binding("s", "channel_stable",  "Stable",  show=False),
        Binding("t", "channel_testing", "Testing", show=False),
        Binding("R", "rollback",        "Rollback",show=False),
    ]

    DEFAULT_CSS = """
    UpdatesScreen { layout: vertical; }

    /* Full-width image banner */
    #image-banner {
        width: 1fr;
        height: 2;
        padding: 0 2;
        content-align: left middle;
        background: $boost 5%;
        color: $accent;
        border-bottom: solid $panel;
    }

    /* Staged update warning bar — hidden until needed */
    #staged-banner {
        width: 1fr;
        height: 2;
        padding: 0 2;
        content-align: left middle;
        background: $warning 15%;
        color: $warning;
        display: none;
    }
    #staged-banner.visible { display: block; }

    /* Two-column layout */
    .adw-cols  { height: auto; }
    .adw-col   { width: 1fr; padding: 0 2; }

    /* Schedule radio rows — active selection highlighted */
    .sched-row          { color: $text-muted; }
    .sched-row.-active  { color: $accent; text-style: bold; }

    /* Footer action bar — pinned above OpsBar */
    #update-footer {
        height: 3;
        align: right middle;
        padding: 0 2;
        background: $surface;
        border-top: solid $panel;
        dock: bottom;
    }
    #update-footer Button { margin-left: 1; }
    """

    # ── schedule labels & descriptions ───────────────────────────────────────
    _SCHED_ROWS = [
        ("sched-auto",   "● Automatic",   "Downloads and installs in the background automatically"),
        ("sched-notify", "○ Notify only", "Downloads automatically, then waits for you to install"),
        ("sched-manual", "○ Manual",      "Nothing runs until you press Update Now"),
    ]

    def compose(self) -> ComposeResult:
        yield ViewSwitcher("updates")

        # Full-width image banner
        yield Label("Loading image…", id="image-banner")

        # Staged-update alert (hidden by default)
        yield Label("⬆  Update staged — reboot to apply", id="staged-banner")

        with ScrollableContainer(id="adw-content"):
            with Horizontal(classes="adw-cols"):

                # ── left column ───────────────────────────────────────────────
                with Vertical(classes="adw-col"):
                    yield AdwPreferencesGroup(
                        "Image",
                        AdwPropertyRow("Signed",      "Checking…", id="img-signed"),
                        AdwPropertyRow("Compression", "Checking…", id="img-compression"),
                        AdwPropertyRow("Stream",      "Checking…", id="img-channel"),
                        AdwPropertyRow("Last Updated","Checking…", id="img-last-updated"),
                    )
                    yield AdwPreferencesGroup(
                        "Update Components",
                        AdwSwitchRow("OS Image",  subtitle="bootc system image", id="layer-os"),
                        AdwSwitchRow(
                            "Flatpaks",
                            subtitle="Flatpak app updates",
                            id="layer-flatpak",
                        ),
                        AdwSwitchRow("Homebrew",  subtitle="Homebrew packages",  id="layer-brew"),
                    )

                # ── right column ──────────────────────────────────────────────
                with Vertical(classes="adw-col"):
                    yield AdwPreferencesGroup(
                        "Update Schedule",
                        *[
                            AdwButtonRow(title, subtitle=desc, id=row_id, classes="sched-row")
                            for row_id, title, desc in self._SCHED_ROWS
                        ],
                    )
                    yield AdwPreferencesGroup(
                        "Pause Updates",
                        AdwSwitchRow(
                            "Pause",
                            subtitle="Suspend automatic updates (focus mode / deep work)",
                            id="focus-switch",
                        ),
                        AdwButtonRow("Snooze 1 hour",        id="btn-snooze-1h"),
                        AdwButtonRow("Snooze until tonight",  id="btn-snooze-tonight"),
                        AdwButtonRow("Snooze until tomorrow", id="btn-snooze-tomorrow"),
                    )
                    yield AdwPreferencesGroup(
                        "Release Stream",
                        AdwPropertyRow("Stream", "Detecting…", id="channel-info"),
                        AdwButtonRow("Switch to Testing", id="btn-testing"),
                        AdwButtonRow("Switch to Stable",  id="btn-stable"),
                    )
                    yield AdwPreferencesGroup(
                        "Rollback",
                        AdwPropertyRow("Previous", "Checking…", id="rollback-info"),
                        AdwButtonRow(
                            "Roll Back to Previous Build",
                            variant="destructive",
                            id="btn-rollback",
                        ),
                    )

        # Pinned footer — Update Now + Check for Updates (bottom-right)
        with Horizontal(id="update-footer"):
            yield Button("Check for Updates",                id="btn-check")
            yield Button("Update Now", variant="primary",    id="btn-update-now")

        yield OpsBar()

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Data loading
    # ─────────────────────────────────────────────────────────────────────────

    async def _load(self) -> None:
        """Populate all fields from system state."""
        from bluefinctl.core.system import get_system_info
        from bluefinctl.core.updates import UpdateStrategy, get_update_status

        # ── image info ────────────────────────────────────────────────────────
        try:
            info = await get_system_info()

            # Banner — full ref with tag, stripped of transport prefix
            self.query_one("#image-banner", Label).update(info.full_clean_ref)

            # Staged update alert
            if info.image_staged:
                self.query_one("#staged-banner", Label).add_class("visible")

            # Signed
            signed_txt = "🔒 Yes — cosign verified" if info.image_signed else "🔓 No"
            self.query_one("#img-signed",  AdwPropertyRow).update_value(signed_txt)

            # Channel / stream
            stream = info.image_tag or "unknown"
            self.query_one("#img-channel", AdwPropertyRow).update_value(stream)
            self.query_one("#channel-info",AdwPropertyRow).update_value(stream)
            is_testing = "testing" in stream.lower()
            self.query_one("#btn-testing", AdwButtonRow).display = not is_testing
            self.query_one("#btn-stable",  AdwButtonRow).display = is_testing

            # Compression — async network call; start as separate worker
            if info.clean_image_ref:
                # Use full_clean_ref for accurate manifest lookup
                self.run_worker(self._load_compression(info.full_clean_ref), exclusive=False)

        except Exception:  # noqa: BLE001
            self.query_one("#image-banner", Label).update("Image info unavailable")
            self.query_one("#img-signed",   AdwPropertyRow).update_value("unavailable")

        # ── last updated from bootc status ────────────────────────────────────
        with contextlib.suppress(Exception):
            proc = await asyncio.create_subprocess_exec(
                "bootc", "status", "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                data = json.loads(stdout)
                ts = (
                    data.get("status", {})
                        .get("booted", {})
                        .get("image", {})
                        .get("timestamp", "")
                )
                ts_display = ts[:10] if len(ts) >= 10 else (ts or "unknown")
                self.query_one("#img-last-updated", AdwPropertyRow).update_value(ts_display)

                # Rollback info
                rollback = data.get("status", {}).get("rollback")
                if rollback:
                    prev_ref = (
                        rollback.get("image", {})
                                .get("image", {})
                                .get("image", "")
                    )
                    # Strip transport prefix
                    for pfx in ("ostree-image-signed:docker://", "docker://",
                                "ostree-image-signed:"):
                        if prev_ref.startswith(pfx):
                            prev_ref = prev_ref[len(pfx):]
                            break
                    self.query_one("#rollback-info", AdwPropertyRow).update_value(
                        prev_ref or "unavailable"
                    )
                else:
                    self.query_one("#rollback-info", AdwPropertyRow).update_value("none")
                    self.query_one("#btn-rollback", AdwButtonRow).disabled = True

        # ── update strategy ───────────────────────────────────────────────────
        try:
            status = await get_update_status()

            label = {
                UpdateStrategy.AUTOMATIC: "sched-auto",
                UpdateStrategy.NOTIFY:    "sched-notify",
                UpdateStrategy.MANUAL:    "sched-manual",
            }.get(status.strategy, "sched-auto")
            self._set_schedule_selection(label)

            # Focus mode
            if status.focus_mode and status.focus_mode.active:
                self.query_one("#focus-switch", AdwSwitchRow).set_value(True)
                self._set_idle("⏸  Updates paused — focus mode active")
            elif status.brew_updates > 0:
                self._set_idle(f"↑  {status.brew_updates} Homebrew package(s) available")
            else:
                self._set_idle("✓  Up to date")

        except Exception:  # noqa: BLE001
            self._set_idle("Ready")

        # ── layer toggles ─────────────────────────────────────────────────────
        uupd_config = Path("/etc/uupd/config.json")
        os_on = flatpak_on = brew_on = True
        if uupd_config.exists():
            with contextlib.suppress(Exception):
                cfg     = json.loads(uupd_config.read_text())
                modules = cfg.get("modules", {})
                os_on      = not modules.get("bootc",   {}).get("disable", False)
                flatpak_on = not modules.get("flatpak", {}).get("disable", False)
                brew_on    = not modules.get("brew",    {}).get("disable", False)
        self.query_one("#layer-os",      AdwSwitchRow).set_value(os_on)
        self.query_one("#layer-flatpak", AdwSwitchRow).set_value(flatpak_on)
        self.query_one("#layer-brew",    AdwSwitchRow).set_value(brew_on)

    async def _load_compression(self, clean_ref: str) -> None:
        """Detect compression type via skopeo — background worker."""
        from bluefinctl.core.system import get_image_compression
        comp = await get_image_compression(clean_ref)
        with contextlib.suppress(Exception):
            self.query_one("#img-compression", AdwPropertyRow).update_value(comp)

    # ─────────────────────────────────────────────────────────────────────────
    # Schedule radio helper
    # ─────────────────────────────────────────────────────────────────────────

    def _set_schedule_selection(self, active_id: str) -> None:
        """Highlight the active schedule row, grey out others."""
        # Map from row id → title (with bullet)
        bullet_map = {
            "sched-auto":   ("● Automatic",   "○ Notify only", "○ Manual"),
            "sched-notify": ("○ Automatic",   "● Notify only", "○ Manual"),
            "sched-manual": ("○ Automatic",   "○ Notify only", "● Manual"),
        }
        bullets = bullet_map.get(active_id, bullet_map["sched-auto"])
        ids     = ["sched-auto", "sched-notify", "sched-manual"]
        for row_id, bullet in zip(ids, bullets, strict=True):
            with contextlib.suppress(Exception):
                row = self.query_one(f"#{row_id}", AdwButtonRow)
                row._title = bullet
                row.refresh()
                if row_id == active_id:
                    row.add_class("-active")
                else:
                    row.remove_class("-active")

    # ─────────────────────────────────────────────────────────────────────────
    # Event handlers
    # ─────────────────────────────────────────────────────────────────────────

    def on_adw_switch_row_changed(self, event: AdwSwitchRow.Changed) -> None:
        row_id = event.row.id
        if row_id == "focus-switch":
            self.run_worker(self._toggle_focus(event.value), exclusive=True)
        elif row_id in ("layer-os", "layer-flatpak", "layer-brew"):
            layer_map = {
                "layer-os":      "bootc",
                "layer-flatpak": "flatpak",
                "layer-brew":    "brew",
            }
            layer = layer_map[row_id]
            from bluefinctl.core.updates import set_layer_enabled
            self.run_worker(set_layer_enabled(layer, event.value), exclusive=True)
            self._set_idle(
                f"✓  {layer.capitalize()} updates {'enabled' if event.value else 'disabled'}"
            )

    def on_adw_button_row_pressed(self, event: AdwButtonRow.Pressed) -> None:
        btn_id = event.row.id
        if btn_id in ("sched-auto", "sched-notify", "sched-manual"):
            self.run_worker(self._apply_schedule(btn_id), exclusive=True)
        elif btn_id == "btn-stable":
            self.run_worker(self._switch_channel("stable"))
        elif btn_id == "btn-testing":
            self.run_worker(self._switch_channel("testing"))
        elif btn_id == "btn-rollback":
            self.run_worker(self._confirm_rollback())
        elif btn_id == "btn-snooze-1h":
            self.run_worker(self._snooze(1, "for 1 hour"), exclusive=True)
        elif btn_id == "btn-snooze-tonight":
            self.run_worker(
                self._snooze(self._hours_until_tonight(), "until tonight"), exclusive=True
            )
        elif btn_id == "btn-snooze-tomorrow":
            self.run_worker(
                self._snooze(self._hours_until_tomorrow(), "until tomorrow morning"),
                exclusive=True,
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-update-now":
            self.run_worker(self.action_update_now(), exclusive=True)
        elif btn_id == "btn-check":
            self.run_worker(self._check_for_updates(), exclusive=True)
        elif btn_id == "btn-op-cancel":
            self._set_idle("Ready")
        elif btn_id == "btn-op-confirm":
            self._ops().set_idle("Ready")

    # ─────────────────────────────────────────────────────────────────────────
    # Operations
    # ─────────────────────────────────────────────────────────────────────────

    async def action_update_now(self) -> None:
        """Run uupd and show indeterminate progress in the OpsBar."""
        import shutil
        ops = self._ops()
        if not shutil.which("uupd"):
            self._set_idle("✗  uupd not found")
            return
        self._set_running("Updating system…", stage=0)
        try:
            proc = await asyncio.create_subprocess_exec(
                "pkexec", "/usr/bin/uupd",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            if proc.returncode == 0:
                ops.set_complete("✓  Update complete")
            else:
                self._set_idle(f"✗  Update failed (exit {proc.returncode})")
        except FileNotFoundError:
            self._set_idle("✗  uupd not found")
        except Exception as e:  # noqa: BLE001
            self._set_idle(f"✗  {e}")

    async def _check_for_updates(self) -> None:
        self._set_running("Checking for updates…")
        try:
            from bluefinctl.core.updates import get_update_status
            status = await get_update_status()
            if status.brew_updates > 0:
                self._set_idle(f"↑  {status.brew_updates} Homebrew package(s) available")
            else:
                self._set_idle("✓  Up to date")
        except Exception as e:  # noqa: BLE001
            self._set_idle(f"✗  {e}")

    async def _apply_schedule(self, row_id: str) -> None:
        from bluefinctl.core.updates import UpdateStrategy, set_update_strategy
        strategy_map = {
            "sched-auto":   UpdateStrategy.AUTOMATIC,
            "sched-notify": UpdateStrategy.NOTIFY,
            "sched-manual": UpdateStrategy.MANUAL,
        }
        strategy = strategy_map[row_id]
        label_map = {
            "sched-auto":   "Automatic",
            "sched-notify": "Notify only",
            "sched-manual": "Manual",
        }
        self._set_running(f"Applying schedule: {label_map[row_id]}…")
        try:
            await set_update_strategy(strategy)
            self._set_schedule_selection(row_id)
            self._set_idle(f"✓  Schedule set to {label_map[row_id]}")
        except Exception as e:  # noqa: BLE001
            self._set_idle(f"✗  {e}")

    async def _toggle_focus(self, on: bool) -> None:
        from bluefinctl.core.updates import activate_focus_mode, deactivate_focus_mode
        if on:
            await activate_focus_mode()
            self._set_idle("⏸  Updates paused — focus mode active")
        else:
            await deactivate_focus_mode()
            self._set_idle("▶  Updates resumed")

    async def _snooze(self, hours: int, label: str) -> None:
        from bluefinctl.core.updates import activate_focus_mode
        await activate_focus_mode(duration_hours=hours)
        self.query_one("#focus-switch", AdwSwitchRow).set_value(True)
        self._set_idle(f"⏸  Updates snoozed {label}")

    async def _switch_channel(self, channel: str) -> None:
        """Switch the bootc image channel after showing a confirm dialog."""
        from bluefinctl.core.system import get_system_info
        from bluefinctl.screens._modals import ConfirmModal, OperationLogModal
        try:
            info = await get_system_info()
            base_ref = info.clean_image_ref  # e.g. ghcr.io/projectbluefin/dakota (no tag)
            if not base_ref:
                self.notify("Cannot determine current image ref", severity="error")
                return
            target = f"{base_ref}:{'testing' if channel == 'testing' else 'latest'}"
        except Exception:  # noqa: BLE001
            self.notify("Cannot determine current image ref", severity="error")
            return

        confirmed = await self.app.push_screen_wait(
            ConfirmModal(
                f"Switch to {channel.capitalize()} Stream",
                f"Target image:\n  {target}\n\nA reboot is required to apply.",
            )
        )
        if confirmed:
            await self.app.push_screen_wait(
                OperationLogModal(
                    f"Switch to {channel}",
                    ["pkexec", "bootc", "switch", target],
                )
            )
            self.notify(f"Switched to {channel} stream. Reboot to apply.", title="Stream")
            self.run_worker(self._load(), exclusive=True)

    async def _confirm_rollback(self) -> None:
        from bluefinctl.screens._modals import ConfirmModal, OperationLogModal
        confirmed = await self.app.push_screen_wait(
            ConfirmModal(
                "Roll Back OS Image",
                "Roll back to the previous image?\nA reboot is required to apply.",
            )
        )
        if confirmed:
            self._set_running("Rolling back…")
            rc = await self.app.push_screen_wait(
                OperationLogModal("Rollback", ["pkexec", "bootc", "rollback"])
            )
            if rc == 0:
                self._set_idle("✓  Rollback staged — reboot to apply")
            else:
                self._set_idle(f"✗  Rollback failed (exit {rc})")

    # ─────────────────────────────────────────────────────────────────────────
    # Keybinding actions
    # ─────────────────────────────────────────────────────────────────────────

    async def action_channel_stable(self) -> None:
        await self._switch_channel("stable")

    async def action_channel_testing(self) -> None:
        await self._switch_channel("testing")

    async def action_rollback(self) -> None:
        await self._confirm_rollback()

    # ─────────────────────────────────────────────────────────────────────────
    # Bottom bar helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _ops(self) -> OpsBar:
        return self.query_one(OpsBar)

    def _set_idle(self, message: str) -> None:
        self._ops().set_idle(message)

    def _set_running(self, message: str, stage: int = 0) -> None:
        self._ops().set_running(message, stage=stage)

    @staticmethod
    def _hours_until_tonight() -> int:
        from datetime import datetime, timedelta
        now    = datetime.now()
        target = now.replace(hour=22, minute=0, second=0, microsecond=0)
        if now.hour >= 22:
            target = (now + timedelta(days=1)).replace(
                hour=22, minute=0, second=0, microsecond=0
            )
        return max(1, int((target - now).total_seconds() / 3600))

    @staticmethod
    def _hours_until_tomorrow() -> int:
        from datetime import datetime, timedelta
        now    = datetime.now()
        target = (now + timedelta(days=1)).replace(
            hour=8, minute=0, second=0, microsecond=0
        )
        return max(1, int((target - now).total_seconds() / 3600))
