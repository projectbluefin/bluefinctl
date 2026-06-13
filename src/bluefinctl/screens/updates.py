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
        self.notify("Toggling focus mode...", title="Focus Mode")

    async def action_update_now(self) -> None:
        self.notify("Triggering update...", title="Update")

    async def action_rollback(self) -> None:
        self.notify("Rolling back to previous deployment...", title="Rollback")
