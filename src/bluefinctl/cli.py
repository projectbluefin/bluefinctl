"""CLI entry point for bluefinctl.

Provides both TUI launch (default) and headless subcommands for scripting.
Every operation has a headless CLI path and a TUI path sharing the same core.
"""

from __future__ import annotations

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
def devmode() -> None:
    """Open the Developer screen."""
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
