"""Updates screen — image info, update schedule, components, reboot strategy, rollback.

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

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label

from bluefinctl.core.notify import system_notify
from bluefinctl.screens._viewswitcher import ViewSwitcher
from bluefinctl.widgets.adw import (
    AdwButtonRow,
    AdwPreferencesGroup,
    AdwPropertyRow,
    AdwSwitchRow,
)
from bluefinctl.widgets.ops_bar import OpsBar


class UpdatesScreen(Screen[None]):
    """Updates — image info, schedule, components, reboot strategy, rollback."""

    BINDINGS = [
        Binding("u", "update_now", "Update Now"),
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

    /* Scrollable content area — always show vertical scrollbar */
    #adw-content {
        height: 1fr;
        scrollbar-gutter: stable;
    }

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
                        "Reboot Strategy",
                        AdwSwitchRow(
                            "Reboot on Logout",
                            subtitle=(
                                "When a staged update exists and you log out, reboot "
                                "automatically. Pairs with GDM autologin."
                            ),
                            id="reboot-on-logout",
                        ),
                        AdwButtonRow(
                            "Scheduled Window",
                            subtitle=(
                                "Reboot between 2–4\u202fAM if a staged update exists "
                                "and AC power is connected"
                            ),
                            id="sched-reboot-window",
                        ),
                        AdwButtonRow(
                            "Manual",
                            subtitle="I will reboot myself when ready",
                            id="sched-reboot-manual",
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
        from bluefinctl.core.updates import UpdateStrategy, get_reboot_strategy, get_update_status

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

            # Compression — async network call; start as separate worker
            if info.clean_image_ref:
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

        # ── update strategy ───────────────────────────────────────────────────
        try:
            status = await get_update_status()

            label = {
                UpdateStrategy.AUTOMATIC:  "sched-auto",
                UpdateStrategy.NOTIFY:     "sched-notify",
                UpdateStrategy.MANUAL:     "sched-manual",
                UpdateStrategy.SCHEDULED:  "sched-auto",  # treated as automatic in UI
            }.get(status.strategy, "sched-auto")
            self._set_schedule_selection(label)

            if status.brew_updates > 0:
                self._set_idle(f"↑  {status.brew_updates} Homebrew package(s) available")
            else:
                self._set_idle("✓  Up to date")

        except Exception:  # noqa: BLE001
            self._set_idle("Ready")

        # ── reboot strategy switches ──────────────────────────────────────────
        with contextlib.suppress(Exception):
            reboot_strategy = get_reboot_strategy()
            self.query_one("#reboot-on-logout", AdwSwitchRow).set_value(
                reboot_strategy.get("reboot-on-logout", False)
            )

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
                row.update_title(bullet)
                if row_id == active_id:
                    row.add_class("-active")
                else:
                    row.remove_class("-active")

    # ─────────────────────────────────────────────────────────────────────────
    # Event handlers
    # ─────────────────────────────────────────────────────────────────────────

    def on_adw_switch_row_changed(self, event: AdwSwitchRow.Changed) -> None:
        row_id = event.row.id
        if row_id == "reboot-on-logout":
            self._set_reboot_on_logout(event.value)
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
            self._apply_schedule(btn_id)
        elif btn_id == "sched-reboot-window":
            self._activate_reboot_window()
        elif btn_id == "sched-reboot-manual":
            self._set_manual_reboot()

    @on(Button.Pressed, "#btn-update-now")
    def _on_update_now(self) -> None:
        self.action_update_now()

    @on(Button.Pressed, "#btn-check")
    def _on_check(self) -> None:
        self._check_for_updates()

    @on(Button.Pressed, "#btn-op-cancel")
    def _on_op_cancel(self) -> None:
        self._set_idle("Ready")

    @on(Button.Pressed, "#btn-op-confirm")
    def _on_op_confirm(self) -> None:
        self._ops().set_idle("Ready")

    # ─────────────────────────────────────────────────────────────────────────
    # Operations
    # ─────────────────────────────────────────────────────────────────────────

    @work(exclusive=True)
    async def action_update_now(self) -> None:
        """Run a full system update: bootc → flatpak / brew / distrobox."""
        from bluefinctl.core.update_runner import (
            run_bootc_upgrade,
            run_brew_update,
            run_distrobox_update,
            run_flatpak_update,
        )
        from bluefinctl.util.osc import (
            osc_notify,
            osc_progress,
            osc_progress_clear,
            osc_progress_indeterminate,
            set_terminal_title,
        )

        ops = self._ops()
        _stage_label = {
            "pulling": "Downloading",
            "importing": "Importing",
            "staging": "Deploying",
        }

        # ── Phase 1: bootc ─────────────────────────────────────────────────
        set_terminal_title("bluefinctl · System Image…")
        osc_progress_indeterminate()
        ops.set_running("System Image…")

        try:
            async for event in run_bootc_upgrade():
                stage = _stage_label.get(event.task, event.task.title() or "Working")
                if event.type == "ProgressSteps" and event.steps_total > 0:
                    osc_progress(int(event.steps / event.steps_total * 80))
                    set_terminal_title(
                        f"bluefinctl · {stage} {event.steps}/{event.steps_total}"
                    )
                    ops.set_running(
                        f"{stage} {event.steps}/{event.steps_total} layers…",
                        step=event.steps,
                        total=event.steps_total,
                    )
                elif event.type == "ProgressBytes" and event.bytes_total > 0:
                    mib = event.bytes_ / (1024 * 1024)
                    mib_t = event.bytes_total / (1024 * 1024)
                    ops.set_running(f"{stage}  {mib:.0f}/{mib_t:.0f} MiB…")
        except Exception as exc:  # noqa: BLE001
            self._set_idle(f"✗  bootc failed — {exc}")
            osc_progress_clear()
            set_terminal_title("")
            return

        ops.add_completed("System Image")
        osc_progress(82)

        # ── Phase 2: flatpak · brew · distrobox (parallel) ─────────────────
        set_terminal_title("bluefinctl · Flatpak · Brew · Distrobox…")
        ops.set_running("Flatpak · Brew · Distrobox…")

        results = await asyncio.gather(
            run_flatpak_update(),
            run_brew_update(),
            run_distrobox_update(),
            return_exceptions=True,
        )
        for name, result in [
            ("Flatpak",   results[0]),
            ("Homebrew",  results[1]),
            ("Distrobox", results[2]),
        ]:
            if isinstance(result, Exception):
                continue
            ok, _ = result  # type: ignore[misc]
            if ok:
                ops.add_completed(name)

        osc_progress(100)
        osc_notify("bluefinctl", "System update complete — reboot when ready")
        ops.set_complete("✓  Update complete — reboot when ready")
        osc_progress_clear()
        set_terminal_title("")

    @work(exclusive=True)
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

    @work(exclusive=True)
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

    @work(exclusive=True)
    async def _set_reboot_on_logout(self, enabled: bool) -> None:
        from bluefinctl.core.updates import set_reboot_on_logout
        self._set_running("Configuring reboot-on-logout…")
        try:
            await set_reboot_on_logout(enabled)
            if enabled:
                self._set_idle("✓  Reboot on logout enabled")
                system_notify(
                    "Reboot on Logout",
                    "Will reboot automatically when a staged update exists.",
                )
            else:
                self._set_idle("✓  Reboot on logout disabled")
        except Exception as exc:  # noqa: BLE001
            self._set_idle(f"✗  {exc}")

    @work(exclusive=True)
    async def _set_manual_reboot(self) -> None:
        """Disable all automatic reboot strategies — manual reboot only."""
        from bluefinctl.core.updates import set_reboot_on_logout, set_scheduled_reboot_window
        self._set_running("Disabling automatic reboots…")
        try:
            await set_reboot_on_logout(False)
            await set_scheduled_reboot_window(False)
            with contextlib.suppress(Exception):
                self.query_one("#reboot-on-logout", AdwSwitchRow).set_value(False)
            self._set_idle("✓  Manual reboot — no automatic reboots")
        except Exception as exc:  # noqa: BLE001
            self._set_idle(f"✗  {exc}")

    @work(exclusive=True)
    async def _activate_reboot_window(self) -> None:
        from bluefinctl.core.updates import get_reboot_strategy, set_scheduled_reboot_window
        strategy = get_reboot_strategy()
        already_on = strategy.get("sched-reboot-window", False)
        self._set_running("Configuring scheduled reboot window…")
        try:
            await set_scheduled_reboot_window(not already_on)
            if not already_on:
                self._set_idle("✓  Scheduled window enabled (2–4\u202fAM)")
                system_notify(
                    "Scheduled Reboot Window",
                    "Will reboot at 2 AM when staged update + AC power.",
                )
            else:
                self._set_idle("✓  Scheduled window disabled")
        except Exception as exc:  # noqa: BLE001
            self._set_idle(f"✗  {exc}")

    # ─────────────────────────────────────────────────────────────────────────
    # Bottom bar helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _ops(self) -> OpsBar:
        return self.query_one(OpsBar)

    def _set_idle(self, message: str) -> None:
        self._ops().set_idle(message)

    def _set_running(self, message: str, stage: int = 0) -> None:
        self._ops().set_running(message, stage=stage)
