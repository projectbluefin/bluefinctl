"""Shared modal dialogs for bluefinctl screens.

Provides:
- ConfirmModal   — yes/no confirmation dialog; returns bool
- InputModal     — single-line text prompt; returns str | None
- OperationLogModal — runs a subprocess and streams output; returns exit code
"""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Log


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
            yield Label(self._title, id="confirm-title", classes="card--title")
            yield Label(self._message, id="confirm-body")
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
            yield Label(self._title, id="input-title", classes="card--title")
            yield Label(self._prompt, id="input-prompt")
            yield Input(placeholder=self._placeholder, id="input-field")
            with Horizontal():
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("OK", id="btn-ok", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-ok":
            value = self.query_one("#input-field", Input).value
            self.dismiss(value)
        else:
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
            yield Label(self._title, id="op-title", classes="card--title")
            yield Label(f"  $ {' '.join(self._command)}", id="op-cmd")
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

            assert proc.stdout is not None
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
