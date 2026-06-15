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
    import asyncio
    import time

    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.text import Text

    from bluefinctl.core.update_runner import (
        ImageInfo,
        check_for_update,
        get_image_info,
        run_bootc_upgrade,
        run_brew_update,
        run_distrobox_update,
        run_flatpak_update,
    )
    from bluefinctl.util.osc import (
        osc_notify,
        osc_progress,
        osc_progress_clear,
        osc_progress_error,
        osc_progress_indeterminate,
        set_terminal_title,
    )

    console = Console()
    image_info: ImageInfo = get_image_info()

    # ── --check mode ──────────────────────────────────────────────────────────
    if check:
        console.print("[dim]Checking for updates…[/dim]")
        has_update = check_for_update()
        if has_update:
            ref = image_info.ref or "unknown"
            console.print(f"[yellow]●[/yellow]  Update available  ·  {ref}")
        else:
            console.print("[green]✓[/green]  System is up to date")
        return

    # ── Build a Progress subclass that adds a header panel ────────────────────
    class UpdateProgress(Progress):
        """Rich Progress with a Bluefin image header rendered above the tasks."""

        def __init__(self, info: ImageInfo, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)  # type: ignore[arg-type]
            self._info = info

        def get_renderables(self) -> object:  # type: ignore[override]
            ref = self._info.ref or "ghcr.io/projectbluefin/bluefin:latest"
            ver = f"  ·  {self._info.version}" if self._info.version else ""
            header = Text.assemble(
                ("  ", ""),
                ("bluefin", "bold #62a0ea"),
                ("  ", "dim"),
                (ref, "dim white"),
                (ver, "dim cyan"),
                ("  ", ""),
            )
            yield Panel(
                header,
                border_style="dim white",
                padding=(0, 0),
            )
            yield self.make_tasks_table(self.tasks)

    progress = UpdateProgress(
        image_info,
        SpinnerColumn(finished_text="[bold green]✓[/bold green]"),
        TextColumn("{task.description}", markup=True),
        BarColumn(bar_width=30, complete_style="green", finished_style="green"),
        TextColumn("{task.fields[detail]}", style="dim white"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )

    # Stage → human label and OSC weight
    stage_label = {
        "pulling": "Downloading",
        "importing": "Importing",
        "staging": "Deploying",
    }
    # bootc phases: pulling 0-80%, importing 80-90%, staging 90-100%
    stage_osc_start = {"pulling": 0, "importing": 72, "staging": 81}
    stage_osc_len   = {"pulling": 72, "importing": 9,  "staging": 9}

    async def _run() -> None:
        with progress:
            # ── Add all tasks ─────────────────────────────────────────────────
            bootc_t = progress.add_task(
                "[bold]System Image[/bold]",
                total=None,
                detail="preparing…",
            )
            bytes_t = progress.add_task(
                "  [dim]└─ transfer[/dim]",
                total=None,
                detail="",
                visible=False,
            )
            flatpak_t = progress.add_task(
                "[dim]Flatpak[/dim]",
                total=None,
                detail="queued",
                start=False,
            )
            brew_t = progress.add_task(
                "[dim]Homebrew[/dim]",
                total=None,
                detail="queued",
                start=False,
            )
            distrobox_t = progress.add_task(
                "[dim]Distrobox[/dim]",
                total=None,
                detail="queued",
                start=False,
            )

            # ── Phase 1: bootc upgrade ────────────────────────────────────────
            set_terminal_title("bctl update · System Image…")
            osc_progress_indeterminate()

            _last_bytes_time: float = time.monotonic()
            _last_bytes_val: int = 0
            _speed_mibs: float = 0.0
            _bootc_succeeded = True

            try:
                async for event in run_bootc_upgrade():
                    stage = stage_label.get(event.task, event.task.title() or "Working")

                    if event.type == "ProgressSteps" and event.steps_total > 0:
                        pct_in_stage = event.steps / event.steps_total
                        osc_start = stage_osc_start.get(event.task, 0)
                        osc_len   = stage_osc_len.get(event.task, 9)
                        osc_val   = int(osc_start + pct_in_stage * osc_len)
                        osc_progress(osc_val)
                        set_terminal_title(
                            f"bctl update · {stage} {event.steps}/{event.steps_total} layers"
                        )
                        progress.update(
                            bootc_t,
                            total=event.steps_total,
                            completed=event.steps,
                            detail=(
                                f"{stage}  "
                                f"{event.steps}/{event.steps_total} layers"
                            ),
                        )

                    elif event.type == "ProgressBytes" and event.bytes_total > 0:
                        now = time.monotonic()
                        dt = now - _last_bytes_time
                        if dt >= 0.4:
                            delta = event.bytes_ - _last_bytes_val
                            _speed_mibs = (delta / dt) / (1024 * 1024)
                            _last_bytes_time = now
                            _last_bytes_val = event.bytes_

                        mib_done  = event.bytes_ / (1024 * 1024)
                        mib_total = event.bytes_total / (1024 * 1024)
                        speed_str = (
                            f"  ·  {_speed_mibs:.1f} MiB/s"
                            if _speed_mibs > 0.05 else ""
                        )
                        progress.update(
                            bytes_t,
                            total=event.bytes_total,
                            completed=event.bytes_,
                            visible=True,
                            detail=f"{mib_done:.1f} / {mib_total:.1f} MiB{speed_str}",
                        )
            except Exception:
                _bootc_succeeded = False

            # Mark bootc done
            bootc_total = progress.tasks[bootc_t].total or 1
            if _bootc_succeeded:
                progress.update(
                    bootc_t,
                    total=bootc_total,
                    completed=bootc_total,
                    detail="[green]staged — reboot to apply[/green]",
                )
            else:
                progress.update(
                    bootc_t,
                    detail="[red]✗ failed[/red]",
                )
                osc_progress_error()

            progress.update(bytes_t, visible=False)
            osc_progress(90)

            # ── Phase 2: parallel stages ──────────────────────────────────────
            set_terminal_title("bctl update · Flatpak · Brew · Distrobox…")

            for t in [flatpak_t, brew_t, distrobox_t]:
                progress.start_task(t)
                progress.update(t, detail="running…")

            results = await asyncio.gather(
                run_flatpak_update(),
                run_brew_update(),
                run_distrobox_update(),
                return_exceptions=True,
            )

            for task_id, _name, result in [
                (flatpak_t, "Flatpak",   results[0]),
                (brew_t,    "Homebrew",  results[1]),
                (distrobox_t, "Distrobox", results[2]),
            ]:
                if isinstance(result, Exception):
                    progress.update(
                        task_id, total=1, completed=1,
                        detail=f"[red]error: {result}[/red]",
                    )
                else:
                    ok, summary = result  # type: ignore[misc]
                    colour = "green" if ok else "red"
                    progress.update(
                        task_id, total=1, completed=1,
                        detail=f"[{colour}]{summary}[/{colour}]",
                    )

            # ── Done ──────────────────────────────────────────────────────────
            osc_progress(100)
            set_terminal_title("bctl update · Done ✓")
            osc_notify("bctl update", "System update complete — reboot when ready")

        # Print outside the Live context so it stays
        console.print()
        console.print(
            "  [bold green]✓[/bold green]  "
            "Update staged.  Reboot when ready.",
            markup=True,
        )
        console.print()
        osc_progress_clear()
        set_terminal_title("")

    asyncio.run(_run())


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


@app.command(name="install")
def install_package(
    package: str = typer.Argument(
        ..., help="Package spec: brew:<name> or flatpak:<app-id>"
    ),
) -> None:
    """Install a package via brew or flatpak."""
    import asyncio
    import subprocess

    from rich.console import Console

    console = Console()

    if package.startswith("brew:"):
        name = package[len("brew:"):]
        if not name:
            typer.echo("Package name required after brew:", err=True)
            raise typer.Exit(1)
        console.print(f"[bold]Installing[/bold] {name} via Homebrew…")
        result = subprocess.run(["brew", "install", name])
        raise typer.Exit(result.returncode)

    if package.startswith("flatpak:"):
        app_id = package[len("flatpak:"):]
        if not app_id:
            typer.echo("App ID required after flatpak:", err=True)
            raise typer.Exit(1)
        console.print(f"[bold]Installing[/bold] {app_id} via Flatpak…")
        from bluefinctl.core.flatpak import install_package as fp_install
        success = asyncio.run(fp_install(app_id))
        if success:
            console.print(f"[green]ok[/green] Installed {app_id}")
        else:
            typer.echo(f"Failed to install {app_id}", err=True)
            raise typer.Exit(1)

    else:
        typer.echo(
            "Unknown package source. Use brew:<name> or flatpak:<app-id>",
            err=True,
        )
        raise typer.Exit(1)


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
