"""Core business logic — developer mode and developer tool workflows."""

from __future__ import annotations

import asyncio
import json
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


@dataclass
class LimaStatus:
    """Lima VM status from limactl."""

    installed: bool
    vm_count: int
    running_count: int
    summary: str


def get_lima_status() -> LimaStatus:
    """Return Lima installation and VM status via limactl list --json."""
    if not shutil.which("limactl"):
        return LimaStatus(installed=False, vm_count=0, running_count=0, summary="not installed")
    try:
        result = subprocess.run(
            ["limactl", "list", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return LimaStatus(installed=True, vm_count=0, running_count=0, summary="no VMs")
        vms = [json.loads(line) for line in result.stdout.strip().splitlines() if line.strip()]
        running = sum(1 for v in vms if v.get("status") == "Running")
        count = len(vms)
        if count == 0:
            summary = "installed, no VMs"
        elif running > 0:
            summary = f"{count} VM{'s' if count > 1 else ''} ({running} running)"
        else:
            summary = f"{count} VM{'s' if count > 1 else ''} (stopped)"
        return LimaStatus(installed=True, vm_count=count, running_count=running, summary=summary)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        return LimaStatus(installed=True, vm_count=0, running_count=0, summary="error")


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


DEVMODE_GROUPS = ["docker", "incus-admin", "libvirt", "dialout"]

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
) -> AsyncGenerator[ProgressUpdate]:
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
) -> AsyncGenerator[ProgressUpdate]:
    """Install one developer tool and stream progress for OperationModal."""
    tool = _find_dev_tool(tool_or_slug)
    if tool.installed:
        yield ProgressUpdate(percent=100, message=f"{tool.name} is already installed")
        return
    async for update in _brew_install_steps([tool.package], f"Installing {tool.name}"):
        yield update


async def install_missing_dev_tools_steps() -> AsyncGenerator[ProgressUpdate]:
    """Install every missing canonical developer tool."""
    missing = [tool.package for tool in get_dev_tools_status() if not tool.installed]
    async for update in _brew_install_steps(missing, "Installing missing developer tools"):
        yield update


async def lima_setup_steps() -> AsyncGenerator[ProgressUpdate]:
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


# ─────────────────────────────────────────────────────────────────────────────
# Feature Portal — detection and install steps for DX tools
# ─────────────────────────────────────────────────────────────────────────────

#: Human-readable names for all feature portal tool IDs
TOOL_NAMES: dict[str, str] = {
    "docker":    "Docker",
    "podman":    "Podman Desktop",
    "lima":      "The Bluefin WSL Experience",
    "incus":     "Incus",
    "vscode":    "VS Code",
    "vscodium":  "VSCodium",
    "zed":       "Zed",
    "jetbrains": "JetBrains Toolbox",
    "neovim":    "Neovim",
    "helix":     "Helix",
    "vms":       "Virtual Machines",
}


# ── Detection helpers ─────────────────────────────────────────────────────────

def _is_flatpak_installed(app_id: str) -> bool:
    result = subprocess.run(
        ["flatpak", "info", app_id],
        capture_output=True,
        timeout=10,
    )
    return result.returncode == 0


def _is_brew_cask_installed(cask: str) -> bool:
    result = subprocess.run(
        ["brew", "list", "--cask", cask],
        capture_output=True,
        timeout=30,
    )
    return result.returncode == 0


def is_docker_installed() -> bool:
    """True if `docker` is on PATH."""
    return shutil.which("docker") is not None


def is_podman_desktop_installed() -> bool:
    """True if Podman Desktop Flatpak is installed."""
    return _is_flatpak_installed("io.podman_desktop.PodmanDesktop")


def is_lima_installed() -> bool:
    """True if the ubuntu Lima VM is configured."""
    if not shutil.which("limactl"):
        return False
    try:
        result = subprocess.run(
            ["limactl", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "ubuntu" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_vscode_installed() -> bool:
    return _is_brew_cask_installed("visual-studio-code-linux")


def is_vscodium_installed() -> bool:
    return _is_brew_cask_installed("vscodium-linux")


def is_zed_installed() -> bool:
    return _is_brew_cask_installed("zed-linux")


def is_jetbrains_installed() -> bool:
    return _is_brew_cask_installed("jetbrains-toolbox-linux")


def is_neovim_installed() -> bool:
    return shutil.which("nvim") is not None


def is_helix_installed() -> bool:
    return shutil.which("hx") is not None


def is_vms_installed() -> bool:
    return _is_flatpak_installed("org.virt_manager.virt-manager")


def is_incus_installed() -> bool:
    """True if `incus` is on PATH (installed via Homebrew)."""
    return shutil.which("incus") is not None


# ── Generic async install helpers ──────────────────────────────────────────────

async def _flatpak_install_steps(
    app_id: str,
    display_name: str = "",
) -> AsyncGenerator[ProgressUpdate]:
    name = display_name or app_id
    yield ProgressUpdate(percent=0, step=1, total_steps=1, message=f"Installing {name}…")
    proc = await asyncio.create_subprocess_exec(
        "flatpak", "install", "--system", "--noninteractive", "flathub", app_id,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout:
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if line:
                yield ProgressUpdate(message=line)
    rc = await proc.wait()
    if rc != 0:
        raise RuntimeError(f"flatpak install {app_id} failed (exit {rc})")
    yield ProgressUpdate(percent=100, message=f"✓ {name} installed")


async def _brew_cask_steps(
    cask: str,
    display_name: str = "",
    tap: str | None = None,
) -> AsyncGenerator[ProgressUpdate]:
    name = display_name or cask
    total = 2 if tap else 1
    step = 0
    if tap:
        step += 1
        yield ProgressUpdate(percent=10, step=step, total_steps=total, message=f"Tapping {tap}…")
        proc = await asyncio.create_subprocess_exec(
            "brew", "tap", tap,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        if proc.stdout:
            async for raw in proc.stdout:
                line = raw.decode(errors="replace").rstrip()
                if line:
                    yield ProgressUpdate(message=line)
        await proc.wait()
        yield ProgressUpdate(message=f"✓ Tapped {tap}")
    step += 1
    yield ProgressUpdate(percent=30, step=step, total_steps=total, message=f"Installing {name}…")
    proc = await asyncio.create_subprocess_exec(
        "brew", "install", "--cask", cask,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout:
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if line:
                yield ProgressUpdate(message=line)
    rc = await proc.wait()
    if rc != 0:
        raise RuntimeError(f"brew install --cask {cask} failed (exit {rc})")
    yield ProgressUpdate(percent=100, message=f"✓ {name} installed")


# ── Per-tool install step generators ─────────────────────────────────────────

async def install_docker_steps() -> AsyncGenerator[ProgressUpdate]:
    """Install Docker + compose + lazydocker + dive via Homebrew."""
    total = 2
    yield ProgressUpdate(
        percent=0, step=1, total_steps=total,
        message="Installing Docker toolchain…",
    )
    packages = ["docker", "docker-compose", "lazydocker", "dive"]
    parser = BrewInstallParser(total_packages=len(packages))
    proc = await asyncio.create_subprocess_exec(
        "brew", "install", *packages,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout:
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            update = parser.parse_line(line)
            yield update or ProgressUpdate(message=line)
    rc = await proc.wait()
    if rc != 0:
        raise RuntimeError(f"brew install docker toolchain failed (exit {rc})")
    yield ProgressUpdate(percent=80, message="✓ Docker toolchain installed")

    # Add user to docker group
    yield ProgressUpdate(
        percent=85, step=2, total_steps=total,
        message="Adding user to docker group…",
    )
    username = os.environ.get("USER", "")
    proc2 = await asyncio.create_subprocess_exec(
        "pkexec", "usermod", "-aG", "docker", username,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc2.wait()
    yield ProgressUpdate(percent=100, message="✓ Docker ready — log out to activate docker group")


async def install_podman_desktop_steps() -> AsyncGenerator[ProgressUpdate]:
    """Install Podman Desktop via Flatpak."""
    async for u in _flatpak_install_steps("io.podman_desktop.PodmanDesktop", "Podman Desktop"):
        yield u


async def install_lima_steps() -> AsyncGenerator[ProgressUpdate]:
    """Install Lima + start ubuntu-lts VM + wire VS Code SSH."""
    total = 4

    # Step 1 — install lima
    yield ProgressUpdate(percent=0, step=1, total_steps=total, message="Installing Lima…")
    if shutil.which("limactl"):
        yield ProgressUpdate(percent=20, message="✓ Lima already installed")
    else:
        parser = BrewInstallParser(total_packages=1)
        proc = await asyncio.create_subprocess_exec(
            "brew", "install", "lima",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        if proc.stdout:
            async for raw in proc.stdout:
                line = raw.decode(errors="replace").rstrip()
                update = parser.parse_line(line)
                yield update or ProgressUpdate(message=line)
        rc = await proc.wait()
        if rc != 0:
            raise RuntimeError(f"brew install lima failed (exit {rc})")
        yield ProgressUpdate(percent=20, message="✓ Lima installed")

    # Step 2 — start ubuntu-lts VM
    yield ProgressUpdate(
        percent=25, step=2, total_steps=total,
        message="Downloading Ubuntu LTS (~600MB)…",
    )
    proc = await asyncio.create_subprocess_exec(
        "limactl", "start",
        "--name", "ubuntu",
        "--mount-writable",
        "--tty=false",
        "template:ubuntu-lts",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout:
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if line:
                yield ProgressUpdate(message=line)
    rc = await proc.wait()
    if rc not in (0, 1):  # 1 can mean "already running"
        raise RuntimeError(f"limactl start ubuntu failed (exit {rc})")
    yield ProgressUpdate(percent=70, message="✓ Ubuntu VM started")

    # Step 3 — wire VS Code SSH
    yield ProgressUpdate(percent=75, step=3, total_steps=total, message="Wiring VS Code SSH…")
    ssh_config = os.path.expanduser("~/.ssh/config")
    include_line = "Include ~/.lima/*/ssh.config\n"
    try:
        import pathlib
        config_path = pathlib.Path(ssh_config)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        existing = config_path.read_text() if config_path.exists() else ""
        if include_line.strip() not in existing:
            config_path.write_text(include_line + existing)
        yield ProgressUpdate(percent=85, message="✓ VS Code SSH wired")
    except OSError as exc:
        yield ProgressUpdate(percent=85, message=f"⚠ Could not update ~/.ssh/config: {exc}")

    # Step 4 — enable autostart
    yield ProgressUpdate(percent=90, step=4, total_steps=total, message="Enabling autostart…")
    proc = await asyncio.create_subprocess_exec(
        "limactl", "autostart", "enable", "ubuntu",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    yield ProgressUpdate(percent=95, message="✓ Ubuntu VM ready")

    # Step 5 — install VS Code (preselected with the WSL Experience)
    yield ProgressUpdate(
        percent=96, step=5, total_steps=5,
        message="Installing VS Code (included with WSL Experience)…",
    )
    async for u in install_vscode_steps():
        yield u
    yield ProgressUpdate(
        percent=100,
        message="✓ Done — drop in with: limactl shell ubuntu",
    )


async def install_vscode_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_cask_steps(
        "visual-studio-code-linux", "VS Code", tap="ublue-os/tap",
    ):
        yield u


async def install_vscodium_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_cask_steps(
        "vscodium-linux", "VSCodium", tap="ublue-os/tap",
    ):
        yield u


async def install_zed_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_cask_steps(
        "zed-linux", "Zed", tap="ublue-os/experimental-tap",
    ):
        yield u


async def install_jetbrains_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_cask_steps(
        "jetbrains-toolbox-linux", "JetBrains Toolbox", tap="ublue-os/tap",
    ):
        yield u


async def install_neovim_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_install_steps(["neovim"], "Installing Neovim…"):
        yield u


async def install_helix_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_install_steps(["helix"], "Installing Helix…"):
        yield u


async def install_vms_steps() -> AsyncGenerator[ProgressUpdate]:
    """Install virt-manager + QEMU extension via Flatpak."""
    total = 2
    yield ProgressUpdate(
        percent=0, step=1, total_steps=total,
        message="Installing virt-manager…",
    )
    proc = await asyncio.create_subprocess_exec(
        "flatpak", "install", "--system", "--noninteractive",
        "flathub",
        "org.virt_manager.virt-manager",
        "org.virt_manager.virt_manager.Extension.Qemu",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout:
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if line:
                yield ProgressUpdate(message=line)
    rc = await proc.wait()
    if rc != 0:
        raise RuntimeError(f"flatpak install virt-manager failed (exit {rc})")
    yield ProgressUpdate(percent=100, message="✓ Virtual Machines installed")


# ── Dispatcher ────────────────────────────────────────────────────────────────



async def install_incus_steps() -> AsyncGenerator[ProgressUpdate]:
    """Install Incus via Homebrew and add user to incus-admin group."""
    total = 2
    yield ProgressUpdate(percent=0, step=1, total_steps=total, message="Installing Incus…")
    async for u in _brew_install_steps(["incus"], "Installing Incus…"):
        yield u
    yield ProgressUpdate(percent=80, message="✓ Incus installed")

    yield ProgressUpdate(
        percent=85, step=2, total_steps=total,
        message="Adding user to incus-admin group…",
    )
    username = os.environ.get("USER", "")
    proc = await asyncio.create_subprocess_exec(
        "pkexec", "usermod", "-aG", "incus-admin", username,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    yield ProgressUpdate(
        percent=100,
        message="✓ Incus ready — log out to activate incus-admin group",
    )

# ── Generic async remove helpers ─────────────────────────────────────────────

async def _brew_uninstall_steps(
    packages: list[str],
    display_name: str,
) -> AsyncGenerator[ProgressUpdate]:
    yield ProgressUpdate(percent=0, step=1, total_steps=1, message=f"Removing {display_name}…")
    proc = await asyncio.create_subprocess_exec(
        "brew", "uninstall", *packages,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout:
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if line:
                yield ProgressUpdate(message=line)
    rc = await proc.wait()
    if rc != 0:
        raise RuntimeError(f"brew uninstall {display_name} failed (exit {rc})")
    yield ProgressUpdate(percent=100, message=f"✓ {display_name} removed")


async def _brew_cask_uninstall_steps(
    cask: str,
    display_name: str,
) -> AsyncGenerator[ProgressUpdate]:
    yield ProgressUpdate(percent=0, step=1, total_steps=1, message=f"Removing {display_name}…")
    proc = await asyncio.create_subprocess_exec(
        "brew", "uninstall", "--cask", cask,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout:
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if line:
                yield ProgressUpdate(message=line)
    rc = await proc.wait()
    if rc != 0:
        raise RuntimeError(f"brew uninstall --cask {cask} failed (exit {rc})")
    yield ProgressUpdate(percent=100, message=f"✓ {display_name} removed")


async def _flatpak_uninstall_steps(
    app_id: str,
    display_name: str = "",
) -> AsyncGenerator[ProgressUpdate]:
    name = display_name or app_id
    yield ProgressUpdate(percent=0, step=1, total_steps=1, message=f"Removing {name}…")
    proc = await asyncio.create_subprocess_exec(
        "flatpak", "uninstall", "--system", "--noninteractive", app_id,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout:
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if line:
                yield ProgressUpdate(message=line)
    rc = await proc.wait()
    if rc != 0:
        raise RuntimeError(f"flatpak uninstall {app_id} failed (exit {rc})")
    yield ProgressUpdate(percent=100, message=f"✓ {name} removed")


# ── Per-tool remove step generators ──────────────────────────────────────────

async def remove_docker_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_uninstall_steps(
        ["docker", "docker-compose", "lazydocker", "dive"], "Docker",
    ):
        yield u
    # Remove user from docker group (best-effort, non-fatal — mirrors disable_devmode)
    proc = await asyncio.create_subprocess_exec(
        "pkexec", "gpasswd", "-d", os.environ.get("USER", ""), "docker",
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


async def remove_podman_desktop_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _flatpak_uninstall_steps("io.podman_desktop.PodmanDesktop", "Podman Desktop"):
        yield u


async def remove_lima_steps() -> AsyncGenerator[ProgressUpdate]:
    total = 3
    yield ProgressUpdate(percent=0, step=1, total_steps=total, message="Stopping Lima VMs…")
    proc = await asyncio.create_subprocess_exec(
        "limactl", "stop", "ubuntu",
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    yield ProgressUpdate(percent=30, step=2, total_steps=total, message="Deleting Lima VMs…")
    proc2 = await asyncio.create_subprocess_exec(
        "limactl", "delete", "ubuntu",
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc2.wait()
    yield ProgressUpdate(percent=60, step=3, total_steps=total, message="Removing Lima…")
    async for u in _brew_uninstall_steps(["lima"], "Lima"):
        # ponytail: strip step/total to avoid progress bar reset
        yield ProgressUpdate(percent=u.percent, message=u.message)


async def remove_incus_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_uninstall_steps(["incus"], "Incus"):
        yield u


async def remove_vscode_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_cask_uninstall_steps("visual-studio-code-linux", "VS Code"):
        yield u


async def remove_vscodium_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_cask_uninstall_steps("vscodium-linux", "VSCodium"):
        yield u


async def remove_zed_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_cask_uninstall_steps("zed-linux", "Zed"):
        yield u


async def remove_jetbrains_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_cask_uninstall_steps("jetbrains-toolbox-linux", "JetBrains Toolbox"):
        yield u


async def remove_neovim_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_uninstall_steps(["neovim"], "Neovim"):
        yield u


async def remove_helix_steps() -> AsyncGenerator[ProgressUpdate]:
    async for u in _brew_uninstall_steps(["helix"], "Helix"):
        yield u


async def remove_vms_steps() -> AsyncGenerator[ProgressUpdate]:
    yield ProgressUpdate(percent=0, step=1, total_steps=2, message="Removing virt-manager…")
    proc = await asyncio.create_subprocess_exec(
        "flatpak", "uninstall", "--system", "--noninteractive",
        "org.virt_manager.virt-manager",
        "org.virt_manager.virt_manager.Extension.Qemu",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout:
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if line:
                yield ProgressUpdate(message=line)
    rc = await proc.wait()
    if rc != 0:
        raise RuntimeError(f"flatpak uninstall virt-manager failed (exit {rc})")
    yield ProgressUpdate(percent=100, message="✓ Virtual Machines removed")


async def get_remove_steps(tool_id: str) -> AsyncGenerator[ProgressUpdate]:
    """Return the remove step generator for a feature portal tool ID."""
    _dispatch = {
        "docker":    remove_docker_steps,
        "podman":    remove_podman_desktop_steps,
        "lima":      remove_lima_steps,
        "incus":     remove_incus_steps,
        "vscode":    remove_vscode_steps,
        "vscodium":  remove_vscodium_steps,
        "zed":       remove_zed_steps,
        "jetbrains": remove_jetbrains_steps,
        "neovim":    remove_neovim_steps,
        "helix":     remove_helix_steps,
        "vms":       remove_vms_steps,
    }
    fn = _dispatch.get(tool_id)
    if fn is None:
        raise ValueError(f"Unknown tool: {tool_id}")
    async for update in fn():
        yield update


async def get_install_steps(tool_id: str) -> AsyncGenerator[ProgressUpdate]:
    """Return the install step generator for a feature portal tool ID."""
    _dispatch = {
        "docker":    install_docker_steps,
        "podman":    install_podman_desktop_steps,
        "lima":      install_lima_steps,
        "incus":     install_incus_steps,
        "vscode":    install_vscode_steps,
        "vscodium":  install_vscodium_steps,
        "zed":       install_zed_steps,
        "jetbrains": install_jetbrains_steps,
        "neovim":    install_neovim_steps,
        "helix":     install_helix_steps,
        "vms":       install_vms_steps,
    }
    fn = _dispatch.get(tool_id)
    if fn is None:
        raise ValueError(f"Unknown tool: {tool_id}")
    async for update in fn():
        yield update


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
