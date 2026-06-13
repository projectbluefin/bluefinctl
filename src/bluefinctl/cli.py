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
    """Trigger system update."""
    import subprocess

    if check:
        result = subprocess.run(
            ["systemctl", "is-active", "uupd.timer"],
            capture_output=True, text=True,
        )
        typer.echo(f"uupd timer: {result.stdout.strip()}")
    else:
        typer.echo("Starting update...")
        run_result = subprocess.run(
            ["systemctl", "start", "--wait", "uupd.service"],
        )
        raise typer.Exit(run_result.returncode)


@app.command()
def devmode(
    action: str = typer.Argument("status", help="on/off/status"),
) -> None:
    """Toggle or check developer mode."""
    from bluefinctl.core.devmode import _check_devmode_active, toggle_devmode

    if action == "status":
        state = _check_devmode_active()
        if state.active:
            typer.echo(f"Developer mode: ACTIVE (groups: {', '.join(state.groups or [])})")
        else:
            typer.echo("Developer mode: INACTIVE")
    elif action in ("on", "off"):
        toggle_devmode()
    else:
        typer.echo(f"Unknown action: {action}. Use on/off/status.", err=True)
        raise typer.Exit(1)


@app.command()
def kit(
    action: str = typer.Argument("list", help="list/install/remove"),
    name: str = typer.Argument(None, help="Kit name"),
) -> None:
    """Manage kits (Brewfile collections)."""
    import asyncio

    from rich.console import Console
    from rich.table import Table

    from bluefinctl.core.bundles import get_bundles

    console = Console()

    if action == "list":
        bundles = asyncio.run(get_bundles())
        table = Table(title="Kits")
        table.add_column("Kit", style="bold")
        table.add_column("Status")
        table.add_column("Packages")
        for b in bundles:
            table.add_row(b.name, b.state.value, f"{b.installed_count}/{b.total_count}")
        console.print(table)
    elif action == "install" and name:
        from bluefinctl.core.bundles import activate_bundle
        typer.echo(f"Activating kit: {name}")
        success = asyncio.run(activate_bundle(name))
        if success:
            typer.echo("Done")
        else:
            typer.echo("Failed", err=True)
            raise typer.Exit(1)
    else:
        typer.echo("Usage: bluefinctl kit list | bluefinctl kit install <name>")


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
        typer.echo("Usage: bluefinctl ai list | ai deploy <stack> | ai stop <stack>")
