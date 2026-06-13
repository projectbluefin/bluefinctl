"""CLI entry point for bluefinctl.

For now, just launches the TUI. Subcommands will be added later
once the TUI design is validated.
"""

import typer

app = typer.Typer(
    name="bluefinctl",
    help="TUI control panel for Bluefin OS",
    no_args_is_help=False,
    invoke_without_command=True,
)


@app.callback()
def main(
    screen: str = typer.Option("system", "--screen", "-s", help="Start screen"),
) -> None:
    """Launch the bluefinctl TUI dashboard."""
    from bluefinctl.app import BluefinCtl

    tui = BluefinCtl(start_screen=screen)
    tui.run()


if __name__ == "__main__":
    app()
