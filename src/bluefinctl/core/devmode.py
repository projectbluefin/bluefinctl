"""Core business logic — developer mode toggle."""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass

from rich.console import Console


@dataclass
class DevmodeState:
    """Current devmode state."""

    active: bool = False
    groups: list[str] | None = None  # Groups added by devmode


# Groups that devmode adds the user to
DEVMODE_GROUPS = ["docker", "mock", "lxd"]

# Packages enabled by devmode (installed via brew)
DEVMODE_PACKAGES = [
    "podman-compose",
    "dive",
    "kind",
]


def _check_devmode_active() -> DevmodeState:
    """Check current devmode state."""
    try:
        result = subprocess.run(
            ["groups"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            current_groups = set(result.stdout.strip().split())
            active_devmode_groups = [g for g in DEVMODE_GROUPS if g in current_groups]
            return DevmodeState(
                active=len(active_devmode_groups) > 0,
                groups=active_devmode_groups,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return DevmodeState(active=False)


async def enable_devmode() -> bool:
    """Enable developer mode — add groups and install dev tools."""
    console = Console()
    console.print("[bold]Enabling developer mode...[/bold]")

    # Add user to devmode groups
    import os
    username = os.environ.get("USER", "")

    for group in DEVMODE_GROUPS:
        proc = await asyncio.create_subprocess_exec(
            "pkexec", "usermod", "-aG", group, username,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode == 0:
            console.print(f"  [green]ok[/green] Added to group: {group}")
        else:
            # Group may not exist on this image — that's OK
            console.print(f"  [dim]  Skipped group: {group}[/dim]")

    # Install dev tools
    for pkg in DEVMODE_PACKAGES:
        proc = await asyncio.create_subprocess_exec(
            "brew", "install", pkg,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode == 0:
            console.print(f"  [green]ok[/green] Installed: {pkg}")
        else:
            console.print(f"  [yellow]![/yellow] Failed to install: {pkg}")

    console.print("\n[green bold]Developer mode enabled![/green bold]")
    console.print("[dim]Log out and back in for group changes to take effect.[/dim]")
    return True


async def disable_devmode() -> bool:
    """Disable developer mode — remove groups."""
    console = Console()
    console.print("[bold]Disabling developer mode...[/bold]")

    import os
    username = os.environ.get("USER", "")

    for group in DEVMODE_GROUPS:
        proc = await asyncio.create_subprocess_exec(
            "pkexec", "gpasswd", "-d", username, group,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode == 0:
            console.print(f"  [green]ok[/green] Removed from group: {group}")

    console.print("\n[green bold]Developer mode disabled.[/green bold]")
    console.print("[dim]Log out and back in for group changes to take effect.[/dim]")
    return True


def toggle_devmode() -> None:
    """Toggle devmode from CLI (non-interactive)."""
    console = Console()
    state = _check_devmode_active()

    if state.active:
        console.print(f"Developer mode is [green]ACTIVE[/green] (groups: {', '.join(state.groups or [])})")
        console.print("Disabling...")
        asyncio.run(disable_devmode())
    else:
        console.print("Developer mode is [dim]INACTIVE[/dim]")
        console.print("Enabling...")
        asyncio.run(enable_devmode())
