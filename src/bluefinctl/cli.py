"""CLI entry point for bluefinctl.

Provides both TUI launch (default) and headless subcommands for scripting.
Every operation has a headless CLI path and a TUI path sharing the same core.
"""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(
    name="bluefinctl",
    help="TUI control panel for Bluefin OS",
    no_args_is_help=False,
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    screen: str = typer.Option(None, "--screen", "-s", help="Jump to screen"),
) -> None:
    """Launch the bluefinctl TUI (default) or run a headless command."""
    if ctx.invoked_subcommand is None:
        from bluefinctl.app import BluefinCtl
        app_instance = BluefinCtl(start_screen=screen)
        app_instance.run()


@app.command()
def status() -> None:
    """Print system status (headless)."""
    from bluefinctl.core.system import print_status
    print_status()




@app.command()
def update(
    check: bool = typer.Option(False, "--check", help="Check only, don't apply"),
) -> None:
    """Update the entire system: OS image, Flatpaks, Brew, and containers."""
    from rich.console import Console

    from bluefinctl.core.update_runner import (
        check_for_update,
        get_autoupdate_containers,
        get_image_info,
    )
    from bluefinctl.theme.accent import ACCENT_COLORS, get_accent_color, get_color_scheme

    _scheme     = get_color_scheme()
    _shade_idx  = 0 if _scheme == "dark" else 1
    _accent_hex = ACCENT_COLORS[get_accent_color()][_shade_idx]

    console    = Console()
    image_info = get_image_info()

    # ── --check mode ───────────────────────────────────────────────────────────
    if check:
        console.print("[dim]Checking for updates…[/dim]")
        if check_for_update():
            ref = image_info.ref or "unknown"
            console.print(f"[{_accent_hex}]●[/{_accent_hex}]  Update available  ·  {ref}")
        else:
            console.print(f"[{_accent_hex}]✓[/{_accent_hex}]  System is up to date")
        return

    # Prime sudo credentials before the progress display starts
    import asyncio
    import subprocess as _sp
    _sp.run(["sudo", "-v"], check=False)

    # ── Full update ────────────────────────────────────────────────────────
    from bluefinctl.core.update_app import run_update_cli

    _has_containers = bool(get_autoupdate_containers())
    asyncio.run(run_update_cli(accent_hex=_accent_hex, has_containers=_has_containers))

@app.command()
def devmode(
    enable: bool = typer.Option(False, "--enable", help="Enable developer mode (headless)"),
    disable: bool = typer.Option(False, "--disable", help="Disable developer mode (headless)"),
) -> None:
    """Open the Developer screen, or enable/disable developer mode headlessly."""
    if enable and disable:
        import sys
        print("Error: --enable and --disable are mutually exclusive", file=sys.stderr)
        raise typer.Exit(1)
    if enable or disable:
        from bluefinctl.core.devmode import _check_devmode_active, toggle_devmode
        active = _check_devmode_active().active
        if enable:
            if active:
                print("Developer mode is already active.")
            else:
                toggle_devmode()
        else:
            if not active:
                print("Developer mode is already inactive.")
            else:
                toggle_devmode()
        return
    from bluefinctl.app import BluefinCtl
    BluefinCtl(start_screen="devmode").run()


@app.command()
def ai(
    action: str = typer.Argument("list", help="list/deploy/stop"),
    stack: str = typer.Argument(None, help="Stack name"),
) -> None:
    """Manage AI stacks."""
    import asyncio

    from rich.console import Console
    from rich.table import Table

    from bluefinctl.core.ai import deploy_stack as _deploy
    from bluefinctl.core.ai import get_stacks
    from bluefinctl.core.ai import stop_stack as _stop

    console = Console()

    if action == "list":
        gpu, stacks = asyncio.run(get_stacks())
        console.print(f"GPU: {gpu.display}")
        console.print()
        table = Table(title="AI Stacks")
        table.add_column("Stack", style="bold")
        table.add_column("VRAM")
        table.add_column("Category")
        table.add_column("Status")
        for s in stacks:
            table.add_row(s.name, f"{s.vram_gb} GB", s.category.value, s.status.value)
        console.print(table)
    elif action == "deploy" and stack:
        gpu, stacks = asyncio.run(get_stacks())
        target = next((s for s in stacks if s.slug == stack), None)
        if target:
            typer.echo(f"Deploying {target.name}...")
            success = asyncio.run(_deploy(target))
            if success:
                typer.echo("Deployed")
            else:
                typer.echo("Failed", err=True)
                raise typer.Exit(1)
        else:
            typer.echo(f"Stack not found: {stack}", err=True)
            raise typer.Exit(1)
    elif action == "stop" and stack:
        gpu, stacks = asyncio.run(get_stacks())
        target = next((s for s in stacks if s.slug == stack), None)
        if target:
            success = asyncio.run(_stop(target))
            if success:
                typer.echo("Stopped")
            else:
                typer.echo("Failed", err=True)
                raise typer.Exit(1)
        else:
            typer.echo(f"Stack not found: {stack}", err=True)
            raise typer.Exit(1)
    else:
        typer.echo("Usage: bluefinctl ai list | ai deploy <stack> | ai stop <stack>", err=True)
        raise typer.Exit(1)


@app.command()
def focus(
    action: str = typer.Argument("status", help="on / off / status"),
) -> None:
    """Activate or deactivate focus mode (pauses automatic updates)."""
    import asyncio

    from rich.console import Console

    from bluefinctl.core.updates import (
        activate_focus_mode,
        deactivate_focus_mode,
        get_update_status,
    )

    console = Console()

    if action == "on":
        asyncio.run(activate_focus_mode())
        console.print("[yellow]Focus mode active[/yellow] — automatic updates paused.")
    elif action == "off":
        asyncio.run(deactivate_focus_mode())
        console.print("[green]Focus mode deactivated[/green] — updates will resume on schedule.")
    elif action == "status":
        status = asyncio.run(get_update_status())
        if status.focus_mode and status.focus_mode.active:
            since = status.focus_mode.activated_at or "unknown"
            console.print(f"[yellow]Focus mode ACTIVE[/yellow] since {since}")
            if status.focus_mode.is_stale:
                console.print("[dim]Warning: focus mode has been active > 7 days[/dim]")
        else:
            console.print("[green]Focus mode OFF[/green] — updates running normally.")
    else:
        typer.echo(f"Unknown action '{action}'. Use: on / off / status", err=True)
        raise typer.Exit(1)


# ── Kit / bundle management ───────────────────────────────────────────────────

kit_app = typer.Typer(help="Manage software kits (Brewfile bundles)")
app.add_typer(kit_app, name="kit")


@kit_app.command("list")
def kit_list() -> None:
    """List available kits and their activation status."""
    import asyncio

    from rich.console import Console
    from rich.table import Table

    from bluefinctl.core.bundles import get_bundles

    console = Console()
    bundles = asyncio.run(get_bundles())

    table = Table(title="Software Kits")
    table.add_column("Kit", style="bold")
    table.add_column("Category")
    table.add_column("Status")
    table.add_column("Packages", justify="right")
    for b in bundles:
        table.add_row(b.name, b.meta.category.value, b.state.value,
                      f"{b.installed_count}/{b.total_count}")
    console.print(table)


@kit_app.command("install")
def kit_install(
    name: str = typer.Argument(..., help="Bundle slug to install"),
) -> None:
    """Install a kit (Brewfile bundle) on this system."""
    import asyncio

    from rich.console import Console

    from bluefinctl.core.bundles import activate_bundle_steps

    console = Console()

    async def _run() -> None:
        async for update in activate_bundle_steps(name):
            if update.message:
                console.print(update.message)

    try:
        asyncio.run(_run())
        console.print(f"[green]Kit '{name}' installed.[/green]")
    except FileNotFoundError:
        Console(stderr=True).print(f"[red]Kit '{name}' not found.[/red]")
        raise typer.Exit(1) from None
    except RuntimeError as e:
        Console(stderr=True).print(f"[red]Failed: {e}[/red]")
        raise typer.Exit(1) from None


@kit_app.command("remove")
def kit_remove(
    name: str = typer.Argument(..., help="Bundle slug to remove"),
) -> None:
    """Remove a kit (Brewfile bundle) from this system."""
    import asyncio

    from rich.console import Console

    from bluefinctl.core.bundles import deactivate_bundle_steps

    console = Console()

    async def _run() -> None:
        async for update in deactivate_bundle_steps(name):
            if update.message:
                console.print(update.message)

    try:
        asyncio.run(_run())
        console.print(f"[green]Kit '{name}' removed.[/green]")
    except FileNotFoundError:
        Console(stderr=True).print(f"[red]Kit '{name}' not found.[/red]")
        raise typer.Exit(1) from None
    except RuntimeError as e:
        Console(stderr=True).print(f"[red]Failed: {e}[/red]")
        raise typer.Exit(1) from None


# ── Bluefin-specific commands ─────────────────────────────────────────────────

@app.command()
def changelogs() -> None:
    """Show the Bluefin release changelog."""
    import json
    import re
    import shutil
    import subprocess
    import urllib.error
    import urllib.request

    from bluefinctl.core.system import _read_image_info

    data = _read_image_info()
    tag = data.get("image-tag", "")
    repo = "projectbluefin/bluefin-lts" if tag.startswith("lts") else "projectbluefin/bluefin"

    content = ""
    tried_specific = False
    # Try version-specific release first (stable/gts/lts streams only)
    if re.search(r"gts$|stable$|^lts", tag):
        tried_specific = True
        date_match = subprocess.run(
            ["grep", "-oP", r"OSTREE_VERSION=.*\d{2}\.\K\d{8}[.0-9]*", "/etc/os-release"],
            capture_output=True, text=True,
        )
        date = date_match.stdout.strip()
        if date:
            try:
                with urllib.request.urlopen(
                    f"https://api.github.com/repos/{repo}/releases", timeout=10
                ) as r:
                    releases = json.loads(r.read())
                content = next(
                    (rel["body"] for rel in releases if rel.get("tag_name") == f"{tag}-{date}"),
                    "",
                )
            except urllib.error.URLError:
                pass

    if not content:
        if tried_specific:
            typer.echo("WARN: Could not find a version-specific release, showing latest.")
        try:
            with urllib.request.urlopen(
                f"https://api.github.com/repos/{repo}/releases/latest", timeout=10
            ) as r:
                content = json.loads(r.read()).get("body", "")
        except urllib.error.URLError as e:
            typer.echo(f"Error fetching changelog: {e}", err=True)
            raise typer.Exit(1) from e

    if shutil.which("glow"):
        proc = subprocess.Popen(["glow", "-p"], stdin=subprocess.PIPE)
        proc.communicate(content.encode())
    else:
        typer.echo(content)


@app.command(name="toggle-testing")
def toggle_testing() -> None:
    """Toggle between the stable and testing image channels."""
    import re
    import subprocess

    from rich.prompt import Confirm

    from bluefinctl.core.system import _read_image_info

    data = _read_image_info()
    tag = data.get("image-tag", "")
    ref = data.get("image-ref", "")

    # Strip transport prefix — match just logic exactly
    image_path = re.sub(r"^.*://", "", re.sub(r"^[a-z-]+:", "", ref))

    if "testing" in tag:
        new_tag = "stable" if tag == "testing" else tag.replace("-testing", "")
        if not Confirm.ask(f"Switch from testing to {new_tag}?"):
            raise typer.Exit(0)
    else:
        tag_map = {"stable": "testing", "latest": "testing",
                   "lts": "lts-testing", "lts-hwe": "lts-hwe-testing"}
        new_tag = tag_map.get(tag)
        if not new_tag:
            typer.echo(f"Cannot toggle testing from channel '{tag}'.", err=True)
            raise typer.Exit(1)
        typer.echo("Testing images may be unstable and are not recommended for daily use.")
        if not Confirm.ask(f"Switch to testing channel ({new_tag})?"):
            raise typer.Exit(0)

    subprocess.run(
        ["pkexec", "bootc", "switch", "--enforce-container-sigpolicy",
         f"{image_path}:{new_tag}"],
        check=True,
    )


@app.command()
def powerwash() -> None:
    """Factory reset this device to its initial state (experimental)."""
    import subprocess

    from rich.prompt import Confirm

    typer.echo(
        "Warning: This is an experimental feature that will reset this device "
        "to its factory state."
    )
    if not Confirm.ask("Wipe this machine?"):
        raise typer.Exit(0)
    if not Confirm.ask("Are you sure — wipe this machine?"):
        raise typer.Exit(0)
    subprocess.run(["sudo", "bootc", "install", "reset", "--experimental"], check=True)


@app.command(name="install-system-flatpaks")
def install_system_flatpaks(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Install the default Bluefin system Flatpaks."""
    import os
    import subprocess

    from rich.prompt import Confirm

    brewfile = os.environ.get(
        "TARGET_FLATPAK_FILE",
        "/usr/share/ublue-os/homebrew/system-flatpaks.Brewfile",
    )
    if not yes and not Confirm.ask("Install system flatpaks?"):
        raise typer.Exit(0)
    subprocess.run(["brew", "bundle", f"--file={brewfile}"], check=True)


_VM_FLATPAKS = [
    "org.virt_manager.virt-manager",
    "org.virt_manager.virt_manager.Extension.Qemu",
]


def _vms_installed() -> bool:
    import subprocess
    result = subprocess.run(
        ["flatpak", "list", "--system", "--columns=application"],
        capture_output=True, text=True,
    )
    return "org.virt_manager.virt-manager" in result.stdout


@app.command(name="setup-vms")
def setup_vms() -> None:
    """Install the VM stack: virt-manager + QEMU extension."""
    import subprocess
    subprocess.run(
        ["flatpak", "install", "--system", "--noninteractive", "flathub", *_VM_FLATPAKS],
        check=True,
    )
    subprocess.run(["/usr/libexec/ensure-libvirt-session-config"], check=True)
    typer.echo(
        "VM stack ready. Supports: Linux/Windows VMs, Windows 11 (UEFI + TPM), USB passthrough."
    )


@app.command(name="toggle-vms")
def toggle_vms() -> None:
    """Toggle the VM stack (virt-manager + QEMU) on or off."""
    import subprocess

    from rich.prompt import Confirm

    if _vms_installed():
        if not Confirm.ask("Remove the VM stack (virt-manager + QEMU)?"):
            raise typer.Exit(0)
        subprocess.run(
            ["flatpak", "uninstall", "--system", "--noninteractive", *_VM_FLATPAKS],
        )
        # clean up libvirt session URI
        subprocess.run(
            ["sed", "-i", "/uri_default.*session/d",
             str(Path.home() / ".config/libvirt/libvirt.conf")],
        )
        typer.echo("VM stack removed.")
    else:
        if not Confirm.ask("Install the VM stack (virt-manager + QEMU)?"):
            raise typer.Exit(0)
        setup_vms()


@app.command(name="bluefin-cli")
def bluefin_cli() -> None:
    """Configure the Bluefin-CLI terminal experience (ublue-bling toggle)."""
    import os  # noqa: PLC0415

    os.execvp("ublue-bling", ["ublue-bling"])  # noqa: S606
