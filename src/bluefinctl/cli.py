"""CLI entry point for bluefinctl.

Handles both TUI launch (default) and headless subcommands.
"""

import typer

app = typer.Typer(
    name="bluefinctl",
    help="TUI control panel for Bluefin OS",
    no_args_is_help=False,
    invoke_without_command=True,
)


@app.callback()
def main(ctx: typer.Context) -> None:
    """Launch the bluefinctl TUI dashboard.

    If a subcommand is given, run it headless instead.
    """
    if ctx.invoked_subcommand is None:
        from bluefinctl.app import BluefinCtl

        app_instance = BluefinCtl()
        app_instance.run()


@app.command()
def status() -> None:
    """Print system status (non-interactive)."""
    from bluefinctl.core.system import print_status

    print_status()


@app.command()
def brew(
    action: str = typer.Argument(None, help="add|remove|upgrade|search|list"),
    package: str = typer.Argument(None, help="Package name (for add/remove/search)"),
) -> None:
    """Manage Homebrew packages."""
    if action is None:
        # Launch TUI at brew screen
        from bluefinctl.app import BluefinCtl

        app_instance = BluefinCtl(start_screen="brew")
        app_instance.run()
    else:
        from bluefinctl.core.brew import brew_action

        brew_action(action, package)


@app.command()
def update(
    check: bool = typer.Option(False, "--check", "-c", help="Check only, don't apply"),
) -> None:
    """Trigger system update."""
    from bluefinctl.core.updates import run_update

    run_update(check_only=check)


@app.command()
def devmode() -> None:
    """Toggle developer mode."""
    from bluefinctl.core.devmode import toggle_devmode

    toggle_devmode()


@app.command()
def ai() -> None:
    """AI stack management (launches TUI)."""
    from bluefinctl.app import BluefinCtl

    app_instance = BluefinCtl(start_screen="ai")
    app_instance.run()


if __name__ == "__main__":
    app()
