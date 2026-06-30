"""Shared modal dialogs for bluefinctl screens.

Provides:
- ConfirmModal   — yes/no confirmation dialog; returns bool
- InputModal     — single-line text prompt; returns str | None
- OperationLogModal — runs a subprocess and streams output; returns exit code
"""

from __future__ import annotations

import asyncio

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Log, Static


class ConfirmModal(ModalScreen[bool]):
    """Ask the user to confirm or cancel an action.

    Returns ``True`` if confirmed, ``False`` if cancelled.
    """

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    ConfirmModal > Vertical {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $border;
    }
    ConfirmModal Label#confirm-body {
        margin: 1 0;
    }
    ConfirmModal Horizontal {
        height: auto;
        align: right middle;
        margin-top: 1;
    }
    ConfirmModal Button {
        margin-left: 1;
    }
    """

    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, id="confirm-title", classes="card--title", markup=False)
            yield Label(self._message, id="confirm-body", markup=False)
            with Horizontal():
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Confirm", id="btn-confirm", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-confirm")


class InputModal(ModalScreen[str | None]):
    """Prompt the user for a single line of text.

    Returns the entered string, or ``None`` if cancelled.
    """

    DEFAULT_CSS = """
    InputModal {
        align: center middle;
    }
    InputModal > Vertical {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $border;
    }
    InputModal Input {
        margin: 1 0;
    }
    InputModal Horizontal {
        height: auto;
        align: right middle;
        margin-top: 1;
    }
    InputModal Button {
        margin-left: 1;
    }
    """

    def __init__(self, title: str, prompt: str, placeholder: str = "") -> None:
        super().__init__()
        self._title = title
        self._prompt = prompt
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, id="input-title", classes="card--title", markup=False)
            yield Label(self._prompt, id="input-prompt", markup=False)
            yield Input(placeholder=self._placeholder, id="input-field")
            with Horizontal():
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("OK", id="btn-ok", variant="primary")

    @on(Button.Pressed, "#btn-ok")
    def _on_ok(self) -> None:
        value = self.query_one("#input-field", Input).value
        self.dismiss(value)

    @on(Button.Pressed, "#btn-cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        value = self.query_one("#input-field", Input).value
        self.dismiss(value)


class OperationLogModal(ModalScreen[int]):
    """Run a subprocess and stream its output into a scrollable log widget.

    Returns the process exit code when the user closes the modal.
    """

    DEFAULT_CSS = """
    OperationLogModal {
        align: center middle;
    }
    OperationLogModal > Vertical {
        width: 90;
        height: 30;
        padding: 1 2;
        background: $surface;
        border: thick $border;
    }
    OperationLogModal Log {
        height: 1fr;
        margin: 1 0;
        border: solid $border;
    }
    OperationLogModal Horizontal {
        height: auto;
        align: right middle;
        margin-top: 1;
    }
    """

    def __init__(self, title: str, command: list[str]) -> None:
        super().__init__()
        self._title = title
        self._command = command
        self._rc: int = -1

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, id="op-title", classes="card--title", markup=False)
            yield Label(f"  $ {' '.join(self._command)}", id="op-cmd", markup=False)
            yield Log(id="op-log", highlight=True)
            with Horizontal():
                yield Button("Close", id="btn-close", variant="default", disabled=True)

    def on_mount(self) -> None:
        self.run_worker(self._run())

    async def _run(self) -> None:
        log = self.query_one("#op-log", Log)
        btn = self.query_one("#btn-close", Button)

        try:
            proc = await asyncio.create_subprocess_exec(
                *self._command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            assert proc.stdout is not None  # noqa: S101
            async for raw_line in proc.stdout:
                line = raw_line.decode(errors="replace").rstrip()
                log.write_line(line)

            self._rc = await proc.wait()
            status = "Done" if self._rc == 0 else f"Failed (exit {self._rc})"
            log.write_line(f"\n── {status} ──")

        except FileNotFoundError:
            log.write_line(f"Error: command not found — {self._command[0]}")
            self._rc = 127
        except Exception as exc:  # noqa: BLE001
            log.write_line(f"Error: {exc}")
            self._rc = 1
        finally:
            btn.disabled = False
            btn.focus()

    def on_button_pressed(self, _event: Button.Pressed) -> None:
        self.dismiss(self._rc)


_HELP_TEXT = """\
[bold]Global[/bold]                   [bold]Navigation[/bold]
──────────────────────────   ──────────────────────────
[cyan]q[/cyan]          Quit              [cyan]Up/j[/cyan]       Move up
[cyan]?[/cyan]          This help         [cyan]Down/k[/cyan]     Move down
[cyan]Ctrl+P[/cyan]     Command Palette   [cyan]Enter[/cyan]      Select
[cyan]1-5[/cyan]        Switch screen     [cyan]g/G[/cyan]        Top / Bottom
[cyan]Tab[/cyan]        Focus next        [cyan]/[/cyan]          Search
[cyan]Esc[/cyan]        Close modal

[bold]System Screen[/bold]
──────────────────────────
[cyan]u[/cyan]          Update All
[cyan]d[/cyan]          Toggle devmode
[cyan]c[/cyan]          Launch podman-tui
[cyan]r[/cyan]          System Report

[bold]Updates Screen[/bold]
──────────────────────────
[cyan]f[/cyan]          Toggle focus mode
[cyan]u[/cyan]          Update now
[cyan]R[/cyan]          Rollback OS
[cyan]s[/cyan]          Switch to stable channel
[cyan]t[/cyan]          Switch to testing channel

[bold]Toolkit Screen[/bold]
──────────────────────────
[cyan]Enter[/cyan]      Activate kit
[cyan]r[/cyan]          Refresh
[cyan]Ctrl+P[/cyan]     Install package

[bold]DevMode Screen[/bold]
──────────────────────────
[cyan]Enter[/cyan]      Install / setup
[cyan]a[/cyan]          Install all missing
[cyan]c[/cyan]          Launch podman-tui

[bold]AI Screen[/bold]
──────────────────────────
[cyan]Enter[/cyan]      Deploy stack
[cyan]s[/cyan]          Stop stack
[cyan]l[/cyan]          View logs
[cyan]f[/cyan]          Filter category
"""


class HelpModal(ModalScreen[None]):
    """Display global and per-screen keybindings in a scrollable overlay."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("?", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    HelpModal > Vertical {
        width: 80;
        height: auto;
        max-height: 45;
        padding: 1 2;
        background: $surface;
        border: thick $border;
    }
    HelpModal Label#help-title {
        margin-bottom: 1;
    }
    HelpModal #help-scroll {
        height: 1fr;
        max-height: 35;
    }
    HelpModal Static#help-body {
        height: auto;
    }
    HelpModal Horizontal {
        height: auto;
        align: right middle;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Keyboard Shortcuts", id="help-title", classes="card--title", markup=False)
            with ScrollableContainer(id="help-scroll"):
                yield Static(_HELP_TEXT, id="help-body", markup=True)
            with Horizontal():
                yield Button("Close", id="btn-close", variant="default")

    def on_button_pressed(self, _event: Button.Pressed) -> None:
        self.dismiss(None)
