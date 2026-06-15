"""Core business logic — update management via uupd."""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

UUPD_CONFIG = Path("/etc/uupd/config.json")
STATE_DIR = Path.home() / ".config" / "bluefinctl"
STATE_FILE = STATE_DIR / "state.json"
TIMER_DROPIN = Path("/etc/systemd/system/uupd.timer.d/bluefinctl-schedule.conf")


class UpdateStrategy(StrEnum):
    """User-facing update strategy."""

    AUTOMATIC = "automatic"
    NOTIFY = "notify"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class Schedule(StrEnum):
    """Predefined update schedules."""

    NIGHT_OWL = "02:00"     # 2-5 AM
    EARLY_BIRD = "05:00"    # 5-7 AM
    LUNCH = "12:00"         # 12-1 PM
    CUSTOM = "custom"


@dataclass
class FocusState:
    """Focus mode state."""

    active: bool = False
    activated_at: str | None = None
    expires_at: str | None = None
    reason: str = ""

    @property
    def days_active(self) -> int:
        if not self.active or not self.activated_at:
            return 0
        activated = datetime.fromisoformat(self.activated_at)
        return (datetime.now() - activated).days

    @property
    def is_stale(self) -> bool:
        """True if focus mode has been active > 7 days."""
        return self.days_active > 7


@dataclass
class UpdateStatus:
    """Current update state for display."""

    strategy: UpdateStrategy = UpdateStrategy.AUTOMATIC
    timer_active: bool = True
    focus_mode: FocusState | None = None
    os_current: bool = True
    os_staged: bool = False
    flatpak_updates: int = 0
    brew_updates: int = 0
    last_check: str = "unknown"
    channel: str = "stable"

    def render(self) -> str:
        """Render as multi-line string for dashboard card."""
        focus_indicator = ""
        if self.focus_mode and self.focus_mode.active:
            focus_indicator = " [FOCUS]"

        os_status = "ok Current" if self.os_current else "~ Update available"
        if self.os_staged:
            os_status = "> Staged (reboot to apply)"

        flatpak_status = (
            f"~ {self.flatpak_updates} updates"
            if self.flatpak_updates > 0
            else "ok Current"
        )
        brew_status = (
            f"~ {self.brew_updates} updates"
            if self.brew_updates > 0
            else "ok Current"
        )

        lines = [
            f"Strategy: {self.strategy.value.title()}{focus_indicator}",
            f"OS Image: {os_status}",
            f"Flatpaks: {flatpak_status}",
            f"Brew:     {brew_status}",
            f"Channel:  {self.channel}",
        ]
        return "\n".join(lines)


def _read_uupd_config() -> dict[str, Any]:
    """Read uupd configuration."""
    if UUPD_CONFIG.exists():
        result: dict[str, Any] = json.loads(UUPD_CONFIG.read_text())
        return result
    return {}


async def _write_uupd_config(cfg: dict[str, Any]) -> None:
    """Write uupd config via pkexec tee (requires elevated privileges)."""
    content = json.dumps(cfg, indent=2).encode()
    proc = await asyncio.create_subprocess_exec(
        "pkexec", "tee", str(UUPD_CONFIG),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate(content)
    if proc.returncode != 0:
        raise RuntimeError(f"pkexec tee failed (exit {proc.returncode})")


def _read_state() -> dict[str, Any]:
    """Read bluefinctl local state."""
    if STATE_FILE.exists():
        result: dict[str, Any] = json.loads(STATE_FILE.read_text())
        return result
    return {}


def _write_state(state: dict[str, Any]) -> None:
    """Write bluefinctl local state."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _is_timer_active() -> bool:
    """Check if uupd.timer is active."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "uupd.timer"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() == "active"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _is_timer_masked() -> bool:
    """Check if uupd.timer is masked (focus mode)."""
    try:
        result = subprocess.run(
            ["systemctl", "is-enabled", "uupd.timer"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() == "masked"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


async def get_update_status() -> UpdateStatus:
    """Gather current update status."""
    loop = asyncio.get_running_loop()

    timer_active = await loop.run_in_executor(None, _is_timer_active)
    timer_masked = await loop.run_in_executor(None, _is_timer_masked)
    state = await loop.run_in_executor(None, _read_state)

    # Determine strategy from timer state
    if timer_masked or not timer_active:
        strategy = UpdateStrategy.MANUAL
    else:
        strategy = UpdateStrategy.AUTOMATIC

    # Parse focus mode from state
    focus_data = state.get("focus_mode", {})
    focus_mode = FocusState(
        active=focus_data.get("active", False) or timer_masked,
        activated_at=focus_data.get("activated_at"),
        expires_at=focus_data.get("expires_at"),
        reason=focus_data.get("reason", ""),
    )

    # Check for pending brew updates (fast check)
    brew_updates = 0
    try:
        proc = await asyncio.create_subprocess_exec(
            "brew", "outdated", "--quiet",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0 and stdout:
            brew_updates = len(stdout.decode().strip().splitlines())
    except (FileNotFoundError, OSError):
        pass

    # Determine channel from bootc status
    channel = "stable"
    try:
        proc = await asyncio.create_subprocess_exec(
            "bootc", "status", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            data = json.loads(stdout)
            ref = (
                data.get("status", {})
                .get("booted", {})
                .get("image", {})
                .get("image", {})
                .get("image", "")
            )
            if ":" in ref:
                raw_tag = ref.split(":", 1)[1]
                channel = "stable" if raw_tag in ("latest", "stable") else raw_tag
    except (FileNotFoundError, OSError, json.JSONDecodeError, KeyError):
        pass

    return UpdateStatus(
        strategy=strategy,
        timer_active=timer_active,
        focus_mode=focus_mode,
        brew_updates=brew_updates,
        channel=channel,
    )


async def set_update_strategy(strategy: UpdateStrategy) -> None:
    """Apply an update strategy by configuring the systemd timer and uupd config."""
    loop = asyncio.get_running_loop()

    if strategy == UpdateStrategy.MANUAL:
        # Mask the timer so it can't run
        proc = await asyncio.create_subprocess_exec(
            "pkexec", "systemctl", "mask", "uupd.timer",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    else:
        # Unmask + enable timer
        for cmd in [
            ["pkexec", "systemctl", "unmask", "uupd.timer"],
            ["pkexec", "systemctl", "enable", "--now", "uupd.timer"],
        ]:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

        # Update notify-only flag
        cfg = await loop.run_in_executor(None, _read_uupd_config)
        cfg["notify-only"] = strategy == UpdateStrategy.NOTIFY
        await _write_uupd_config(cfg)


async def set_layer_enabled(layer: str, enabled: bool) -> None:
    """Enable or disable a specific update layer in uupd config."""
    loop = asyncio.get_running_loop()
    cfg = await loop.run_in_executor(None, _read_uupd_config)
    modules = cfg.setdefault("modules", {})
    modules.setdefault(layer, {})["disable"] = not enabled
    await _write_uupd_config(cfg)


# ——— Focus Mode —————————————————————————————————————————————

async def activate_focus_mode(
    duration_hours: int | None = None,
    reason: str = "",
) -> None:
    """Activate focus mode — pause all updates."""
    # Mask the timer
    proc = await asyncio.create_subprocess_exec(
        "pkexec", "systemctl", "mask", "uupd.timer",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    # Record state
    state = _read_state()
    now = datetime.now().isoformat()
    expires = None
    if duration_hours:
        expires = (datetime.now() + timedelta(hours=duration_hours)).isoformat()

    state["focus_mode"] = {
        "active": True,
        "activated_at": now,
        "expires_at": expires,
        "reason": reason,
    }
    _write_state(state)


async def deactivate_focus_mode() -> None:
    """Deactivate focus mode — resume updates."""
    # Unmask and restart timer
    proc = await asyncio.create_subprocess_exec(
        "pkexec", "systemctl", "unmask", "uupd.timer",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    proc = await asyncio.create_subprocess_exec(
        "pkexec", "systemctl", "enable", "--now", "uupd.timer",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    # Clear state
    state = _read_state()
    state["focus_mode"] = {"active": False}
    _write_state(state)


# ——— CLI entry point —————————————————————————————————————————

def run_update(check_only: bool = False) -> None:
    """Run update from CLI (non-interactive)."""
    from rich.console import Console

    console = Console()

    if check_only:
        status = asyncio.run(get_update_status())
        console.print(status.render())
    else:
        console.print("[bold]Starting system update...[/bold]")
        # Trigger uupd manually
        result = subprocess.run(
            ["systemctl", "start", "uupd.service"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            console.print("[green]ok[/green] Update triggered successfully")
        else:
            console.print(f"[red]X[/red] Failed: {result.stderr.strip()}")


# ─── Smart Reboot Strategies ──────────────────────────────────────────────────

_REBOOT_CONFIG_DIR  = Path.home() / ".config" / "bluefinctl"
_REBOOT_MARKER      = _REBOOT_CONFIG_DIR / "reboot-on-logout"
_REBOOT_SERVICE_DIR = Path.home() / ".config" / "systemd" / "user" / "session.target.wants"
_REBOOT_SERVICE     = _REBOOT_SERVICE_DIR / "bluefinctl-reboot.service"
_TIMER_FILE = Path.home() / ".config" / "systemd" / "user" / "bluefinctl-reboot-window.timer"
_TIMER_SERVICE_FILE = _TIMER_FILE.parent / "bluefinctl-reboot-window.service"
_REBOOT_LOG = Path.home() / ".local" / "share" / "bluefinctl" / "reboot-skipped.log"

_REBOOT_SERVICE_UNIT = """\
[Unit]
Description=Reboot on logout if staged update exists
After=graphical-session.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true
ExecStopPost=/bin/sh -c '\
  if bootc status --json 2>/dev/null | jq -e .status.staged >/dev/null 2>&1 && \
     ! systemd-inhibit --list --no-pager 2>/dev/null | grep -qE '\'\'audio|video|idle'\'' ; then \
    systemctl reboot; \
  fi'

[Install]
WantedBy=graphical-session.target
"""

_REBOOT_TIMER_UNIT = """\
[Unit]
Description=Reboot window for staged OS updates (2 AM)

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
"""

_REBOOT_TIMER_SERVICE_UNIT = """\
[Unit]
Description=Apply staged OS update in reboot window

[Service]
Type=oneshot
ExecStart=/bin/sh -c '\
  if bootc status --json 2>/dev/null | jq -e .status.staged >/dev/null 2>&1 && \
     cat /sys/class/power_supply/AC*/online 2>/dev/null | grep -q 1 && \
     ! systemd-inhibit --list --no-pager 2>/dev/null | grep -qE '\'\'audio|video|idle'\'' ; then \
    systemctl reboot; \
  else \
    mkdir -p ~/.local/share/bluefinctl && \
    echo "$(date -Iseconds) reboot skipped" >> ~/.local/share/bluefinctl/reboot-skipped.log; \
  fi'
"""


def get_reboot_strategy() -> dict[str, bool]:
    """Return the current reboot-strategy switch states."""
    return {
        "reboot-on-logout":   _REBOOT_MARKER.exists(),
        "sched-reboot-window": _TIMER_FILE.exists(),
    }


async def set_reboot_on_logout(enabled: bool) -> None:
    """Enable or disable the reboot-on-logout strategy."""
    if enabled:
        _REBOOT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _REBOOT_MARKER.touch(exist_ok=True)
        _REBOOT_SERVICE_DIR.mkdir(parents=True, exist_ok=True)
        _REBOOT_SERVICE.write_text(_REBOOT_SERVICE_UNIT)
    else:
        _REBOOT_MARKER.unlink(missing_ok=True)
        _REBOOT_SERVICE.unlink(missing_ok=True)

    proc = await asyncio.create_subprocess_exec(
        "systemctl", "--user", "daemon-reload",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


async def set_scheduled_reboot_window(enabled: bool) -> None:
    """Enable or disable the 2 AM scheduled-reboot-window timer."""
    if enabled:
        _TIMER_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TIMER_FILE.write_text(_REBOOT_TIMER_UNIT)
        _TIMER_SERVICE_FILE.write_text(_REBOOT_TIMER_SERVICE_UNIT)
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "--user", "enable", "--now",
            "bluefinctl-reboot-window.timer",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    else:
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "--user", "disable", "--now",
            "bluefinctl-reboot-window.timer",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    await proc.wait()
    if not enabled:
        _TIMER_FILE.unlink(missing_ok=True)
        _TIMER_SERVICE_FILE.unlink(missing_ok=True)
