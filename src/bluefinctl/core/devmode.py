"""Core business logic — developer mode and developer tool workflows."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from collections.abc import AsyncGenerator
from dataclasses import dataclass, replace

from rich.console import Console

from bluefinctl.core.progress import BrewInstallParser, ProgressUpdate


@dataclass
class DevmodeState:
    """Current devmode state."""

    active: bool = False
    groups: list[str] | None = None


@dataclass(frozen=True)
class DevTool:
    """A developer tool with install metadata and runtime status."""

    slug: str
    command: str
    package: str
    name: str
    description: str
    category: str
    installed: bool = False


DEVMODE_GROUPS = ["docker", "mock", "lxd"]

DEVMODE_PACKAGES = [
    "podman-compose",
    "dive",
    "kind",
]

DEV_TOOL_REGISTRY: tuple[DevTool, ...] = (
    DevTool(
        slug="podman-compose",
        command="podman-compose",
        package="podman-compose",
        name="podman-compose",
        description="Compose-compatible orchestration for Podman",
        category="Dev Tools",
    ),
    DevTool(
        slug="dive",
        command="dive",
        package="dive",
        name="dive",
        description="Container layer explorer",
        category="Dev Tools",
    ),
    DevTool(
        slug="kind",
        command="kind",
        package="kind",
        name="kind",
        description="Local Kubernetes clusters",
        category="Dev Tools",
    ),
    DevTool(
        slug="devcontainer",
        command="devcontainer",
        package="devcontainer",
        name="devcontainer",
        description="Dev Container CLI",
        category="Dev Tools",
    ),
    DevTool(
        slug="sysprof",
        command="sysprof",
        package="sysprof",
        name="Sysprof",
        description="System profiler",
        category="Performance",
    ),
    DevTool(
        slug="bcc",
        command="bcc",
        package="bcc",
        name="BCC",
        description="BPF compiler collection",
        category="Performance",
    ),
    DevTool(
        slug="bpftrace",
        command="bpftrace",
        package="bpftrace",
        name="bpftrace",
        description="High-level BPF tracing",
        category="Performance",
    ),
    DevTool(
        slug="qemu-system-x86_64",
        command="qemu-system-x86_64",
        package="qemu",
        name="QEMU/KVM",
        description="Machine emulator and virtualizer",
        category="Virtualization",
    ),
    DevTool(
        slug="incus",
        command="incus",
        package="incus",
        name="Incus",
        description="Container and VM manager",
        category="Virtualization",
    ),
)


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


def get_dev_tools_status() -> list[DevTool]:
    """Return canonical developer tools with current install status."""
    return [
        replace(tool, installed=shutil.which(tool.command) is not None)
        for tool in DEV_TOOL_REGISTRY
    ]


def _find_dev_tool(tool_or_slug: DevTool | str) -> DevTool:
    if isinstance(tool_or_slug, DevTool):
        return tool_or_slug
    for tool in get_dev_tools_status():
        if tool.slug == tool_or_slug:
            return tool
    raise ValueError(f"Unknown developer tool: {tool_or_slug}")


async def _brew_install_steps(
    packages: list[str],
    title: str,
) -> AsyncGenerator[ProgressUpdate, None]:
    if not packages:
        yield ProgressUpdate(percent=100, message="Nothing to install")
        return

    parser = BrewInstallParser(total_packages=len(packages))
    yield ProgressUpdate(percent=0, step=1, total_steps=len(packages), message=title)
    proc = await asyncio.create_subprocess_exec(
        "brew", "install", *packages,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout:
        async for raw_line in proc.stdout:
            line = raw_line.decode(errors="replace").rstrip()
            update = parser.parse_line(line)
            yield update or ProgressUpdate(message=line)
    rc = await proc.wait()
    if rc != 0:
        raise RuntimeError(f"brew install failed ({rc})")
    yield ProgressUpdate(percent=100, message="Developer tools installed")


async def install_dev_tool_steps(
    tool_or_slug: DevTool | str,
) -> AsyncGenerator[ProgressUpdate, None]:
    """Install one developer tool and stream progress for OperationModal."""
    tool = _find_dev_tool(tool_or_slug)
    if tool.installed:
        yield ProgressUpdate(percent=100, message=f"{tool.name} is already installed")
        return
    async for update in _brew_install_steps([tool.package], f"Installing {tool.name}"):
        yield update


async def install_missing_dev_tools_steps() -> AsyncGenerator[ProgressUpdate, None]:
    """Install every missing canonical developer tool."""
    missing = [tool.package for tool in get_dev_tools_status() if not tool.installed]
    async for update in _brew_install_steps(missing, "Installing missing developer tools"):
        yield update


async def lima_setup_steps() -> AsyncGenerator[ProgressUpdate, None]:
    """Set up Lima VM — KVM preflight, install lima, start default VM, verify."""
    total = 4

    # ── Step 1: KVM preflight ──────────────────────────────────────────────
    yield ProgressUpdate(percent=5, step=1, total_steps=total, message="Checking KVM support…")
    if os.path.exists("/dev/kvm"):
        yield ProgressUpdate(percent=10, message="✓ /dev/kvm present")
    else:
        username = os.environ.get("USER", "")
        yield ProgressUpdate(percent=8, message="/dev/kvm not found — adding user to kvm group…")
        proc = await asyncio.create_subprocess_exec(
            "pkexec", "usermod", "-aG", "kvm", username,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode == 0:
            yield ProgressUpdate(
                percent=12,
                message="Added to kvm group — log out and back in for KVM acceleration",
            )
        else:
            yield ProgressUpdate(
                percent=12,
                message="⚠ Could not add to kvm group — Lima will use QEMU SLIRP",
            )

    # ── Step 2: Install Lima ────────────────────────────────────────────
    yield ProgressUpdate(percent=20, step=2, total_steps=total, message="Installing Lima…")
    if shutil.which("limactl"):
        yield ProgressUpdate(percent=40, message="✓ Lima already installed")
    else:
        parser = BrewInstallParser(total_packages=1)
        proc = await asyncio.create_subprocess_exec(
            "brew", "install", "lima",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        if proc.stdout:
            async for raw_line in proc.stdout:
                line = raw_line.decode(errors="replace").rstrip()
                update = parser.parse_line(line)
                yield update or ProgressUpdate(message=line)
        rc = await proc.wait()
        if rc != 0:
            raise RuntimeError(f"brew install lima failed (exit {rc})")
        yield ProgressUpdate(percent=45, message="✓ Lima installed")

    # ── Step 3: Start default VM ───────────────────────────────────────
    yield ProgressUpdate(percent=50, step=3, total_steps=total, message="Starting default Lima VM…")
    proc = await asyncio.create_subprocess_exec(
        "limactl", "start",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout:
        async for raw_line in proc.stdout:
            line = raw_line.decode(errors="replace").rstrip()
            if line:
                yield ProgressUpdate(message=line)
    rc = await proc.wait()
    if rc != 0:
        # Non-zero can mean the VM is already running — proceed to verify
        yield ProgressUpdate(percent=80, message="VM may already be running — verifying…")

    # ── Step 4: Verify ──────────────────────────────────────────────────
    yield ProgressUpdate(percent=90, step=4, total_steps=total, message="Verifying Lima VM…")
    try:
        proc = await asyncio.create_subprocess_exec(
            "limactl", "list", "--format", "{{.Name}} {{.Status}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            vms = [v for v in stdout.decode().strip().splitlines() if v.strip()]
            if vms:
                yield ProgressUpdate(percent=100, message=f"✓ {len(vms)} VM(s) ready — {vms[0]}")
                return
        raise RuntimeError("No VMs found after setup")
    except FileNotFoundError as exc:
        raise RuntimeError("limactl not found after install") from exc


async def enable_devmode() -> bool:
    """Enable developer mode — add groups and install dev tools."""
    console = Console()
    console.print("[bold]Enabling developer mode...[/bold]")

    username = os.environ.get("USER", "")

    for group in DEVMODE_GROUPS:
        proc = await asyncio.create_subprocess_exec(
            "pkexec", "usermod", "-aG", group, username,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode == 0:
            console.print(f"  [green]ok[/green] Added to group: {group}")
        else:
            console.print(f"  [dim]  Skipped group: {group}[/dim]")

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
        groups = ", ".join(state.groups or [])
        console.print(f"Developer mode is [green]ACTIVE[/green] (groups: {groups})")
        console.print("Disabling...")
        asyncio.run(disable_devmode())
    else:
        console.print("Developer mode is [dim]INACTIVE[/dim]")
        console.print("Enabling...")
        asyncio.run(enable_devmode())
