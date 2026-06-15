"""Core business logic — Brewfile management."""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

# Brewfile locations
SYSTEM_BREWFILES = Path("/usr/share/ublue-os/homebrew")
USER_BREWFILE = Path.home() / ".config" / "bluefin" / "Brewfile"
USER_DISABLED = Path.home() / ".config" / "bluefin" / "disabled.list"


class PackageSource(StrEnum):
    """Where a package declaration comes from."""

    SYSTEM = "system"   # Shipped in image (read-only)
    USER = "user"       # User-added
    DISABLED = "disabled"  # User removed from system set


class PackageType(StrEnum):
    """Brew package type."""

    FORMULA = "brew"
    CASK = "cask"
    TAP = "tap"
    VSCODE = "vscode"


@dataclass
class Package:
    """A single package entry from a Brewfile."""

    name: str
    type: PackageType = PackageType.FORMULA
    source: PackageSource = PackageSource.SYSTEM
    description: str = ""
    installed: bool = True
    version: str = ""
    outdated: bool = False


@dataclass
class BrewState:
    """Complete state of the layered Brewfile system."""

    packages: list[Package] = field(default_factory=list)
    taps: list[str] = field(default_factory=list)

    @property
    def system_packages(self) -> list[Package]:
        return [p for p in self.packages if p.source == PackageSource.SYSTEM]

    @property
    def user_packages(self) -> list[Package]:
        return [p for p in self.packages if p.source == PackageSource.USER]

    @property
    def disabled_packages(self) -> list[Package]:
        return [p for p in self.packages if p.source == PackageSource.DISABLED]

    @property
    def outdated_count(self) -> int:
        return sum(1 for p in self.packages if p.outdated)


def _parse_brewfile(path: Path) -> list[Package]:
    """Parse a Brewfile into package entries."""
    packages: list[Package] = []
    if not path.exists():
        return packages

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Parse: brew "name", cask "name", tap "name"
        for pkg_type in PackageType:
            prefix = pkg_type.value + " "
            if line.startswith(prefix):
                # Extract name from quotes
                rest = line[len(prefix):]
                name = rest.strip().strip('"').strip("'")
                # Handle args like: brew "name", args: ["--with-foo"]
                if "," in name:
                    name = name.split(",")[0].strip().strip('"')
                packages.append(Package(name=name, type=pkg_type))
                break

    return packages


def _read_disabled_list() -> set[str]:
    """Read the user's disabled package list."""
    if USER_DISABLED.exists():
        return {
            line.strip()
            for line in USER_DISABLED.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }
    return set()


async def get_brew_state() -> BrewState:
    """Build the complete layered Brewfile state."""
    loop = asyncio.get_running_loop()

    # Parse system Brewfiles
    system_packages: list[Package] = []
    if SYSTEM_BREWFILES.exists():
        for brewfile in sorted(SYSTEM_BREWFILES.glob("*.Brewfile")):
            pkgs = await loop.run_in_executor(None, _parse_brewfile, brewfile)
            for pkg in pkgs:
                pkg.source = PackageSource.SYSTEM
            system_packages.extend(pkgs)

    # Parse user Brewfile
    user_packages = await loop.run_in_executor(None, _parse_brewfile, USER_BREWFILE)
    for pkg in user_packages:
        pkg.source = PackageSource.USER

    # Read disabled list
    disabled = await loop.run_in_executor(None, _read_disabled_list)

    # Mark disabled packages
    for pkg in system_packages:
        if pkg.name in disabled:
            pkg.source = PackageSource.DISABLED

    # Check for outdated packages
    try:
        proc = await asyncio.create_subprocess_exec(
            "brew", "outdated", "--json=v2",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0 and stdout:
            import json
            outdated_data = json.loads(stdout)
            outdated_names = {
                f["name"] for f in outdated_data.get("formulae", [])
            } | {
                c["name"] for c in outdated_data.get("casks", [])
            }
            all_packages = system_packages + user_packages
            for pkg in all_packages:
                if pkg.name in outdated_names:
                    pkg.outdated = True
    except (FileNotFoundError, OSError):
        pass

    return BrewState(packages=system_packages + user_packages)


# ─── Package Operations ─────────────────────────────────────

async def add_package(name: str, pkg_type: PackageType = PackageType.FORMULA) -> bool:
    """Add a package to the user Brewfile."""
    USER_BREWFILE.parent.mkdir(parents=True, exist_ok=True)

    # Append to user Brewfile
    entry = f'{pkg_type.value} "{name}"\n'
    with USER_BREWFILE.open("a") as f:
        f.write(entry)

    # Install it
    cmd = ["brew", "install"]
    if pkg_type == PackageType.CASK:
        cmd.append("--cask")
    cmd.append(name)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    return proc.returncode == 0


async def remove_package(name: str) -> bool:
    """Remove a package (add to disabled list if system, remove from user Brewfile if user)."""
    # Check if it's a system package
    state = await get_brew_state()
    pkg = next((p for p in state.packages if p.name == name), None)

    if pkg and pkg.source == PackageSource.SYSTEM:
        # Add to disabled list
        USER_DISABLED.parent.mkdir(parents=True, exist_ok=True)
        with USER_DISABLED.open("a") as f:
            f.write(f"{name}\n")
    elif pkg and pkg.source == PackageSource.USER:
        # Remove from user Brewfile
        if USER_BREWFILE.exists():
            lines = USER_BREWFILE.read_text().splitlines()
            lines = [ln for ln in lines if f'"{name}"' not in ln]
            USER_BREWFILE.write_text("\n".join(lines) + "\n")

    # Uninstall
    proc = await asyncio.create_subprocess_exec(
        "brew", "uninstall", name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    return proc.returncode == 0


async def upgrade_all() -> asyncio.subprocess.Process:
    """Run brew upgrade, returning the process for progress streaming."""
    return await asyncio.create_subprocess_exec(
        "brew", "upgrade",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )


# ─── CLI entry point ─────────────────────────────────────────

def brew_action(action: str, package: str | None = None) -> None:
    """Execute a brew action from CLI (non-interactive)."""
    from rich.console import Console

    console = Console()

    match action:
        case "list":
            state = asyncio.run(get_brew_state())
            for pkg in state.packages:
                icon = {"system": "[S]", "user": "[U]", "disabled": "[X]"}[pkg.source.value]
                outdated = " ~" if pkg.outdated else ""
                console.print(f"  {icon} {pkg.name}{outdated}")
            console.print(f"\n  Total: {len(state.packages)} packages")

        case "add" if package:
            success = asyncio.run(add_package(package))
            if success:
                console.print(f"[green]ok[/green] Added {package}")
            else:
                console.print(f"[red]X[/red] Failed to add {package}")

        case "remove" if package:
            success = asyncio.run(remove_package(package))
            if success:
                console.print(f"[green]ok[/green] Removed {package}")
            else:
                console.print(f"[red]X[/red] Failed to remove {package}")

        case "upgrade":
            console.print("[bold]Upgrading all packages...[/bold]")
            proc = asyncio.run(upgrade_all())
            # Stream output
            asyncio.run(_stream_output(proc, console))

        case "search" if package:
            console.print(f"Searching for '{package}'...")
            result = subprocess.run(
                ["brew", "search", package],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                console.print(result.stdout)

        case _:
            console.print(
                "[red]Usage: bluefinctl brew <list|add|remove|upgrade|search> [package][/red]"
            )


async def _stream_output(proc: asyncio.subprocess.Process, console: Any) -> None:
    """Stream subprocess output to console."""
    if proc.stdout:
        async for line in proc.stdout:
            console.print(line.decode().rstrip())
    await proc.wait()


# ─── Package Search ──────────────────────────────────────────


@dataclass
class SearchResult:
    """A package found via brew search."""

    name: str
    type: PackageType
    description: str = ""


async def search_packages(query: str) -> list[SearchResult]:
    """Search brew for packages matching query."""
    if not query or len(query) < 2:
        return []

    proc = await asyncio.create_subprocess_exec(
        "brew", "search", query,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0 or not stdout:
        return []

    results: list[SearchResult] = []
    current_type = PackageType.FORMULA
    for line in stdout.decode().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("==> Formulae"):
            current_type = PackageType.FORMULA
            continue
        if line.startswith("==> Casks"):
            current_type = PackageType.CASK
            continue
        if line.startswith("==>"):
            continue
        # Each line is a package name
        results.append(SearchResult(name=line, type=current_type))

    return results[:30]  # Cap results
