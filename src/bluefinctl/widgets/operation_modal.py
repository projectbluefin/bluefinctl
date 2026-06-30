"""Unified operation progress modal.

Every operation in bluefinctl — brew install, podman pull, bootc switch,
Lima setup — uses this same visual treatment:

  +-- Installing Kit: Kubernetes ----------------------------+
  |                                                          |
  |  Step 2/3: Installing packages via Homebrew              |
  |  ============================............  8/12 packages |
  |                                                          |
  |  [l] Show log                                            |
  |                                                          |
  +----------------------------------------------------------+

Components:
  1. Title (operation name)
  2. Step description (current step in multi-step operations)
  3. ProgressBar — accent-colored, determinate or indeterminate
  4. Collapsible raw log (hidden by default, expand with 'l')
  5. Cancel action (Escape) / Close when done
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Log, ProgressBar, Static

from bluefinctl.core.progress import ProgressParser, ProgressUpdate
from bluefinctl.util.osc import osc_progress, osc_progress_clear, osc_progress_error


class OperationModal(ModalScreen[int]):
    """Unified progress modal for all bluefinctl operations.

    Drives a ProgressBar from a stream of ProgressUpdate objects.
    Supports both subprocess commands and async generator workflows.

    Returns 0 on success, non-zero on failure.
    """

    BINDINGS = [
        Binding("l", "toggle_log", "Toggle Log"),
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    OperationModal {
        align: center middle;
    }
    OperationModal > Vertical {
        width: 70;
        height: auto;
        max-height: 40;
        padding: 1 2;
        background: $surface;
        border: thick $border;
    }
    OperationModal #op-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    OperationModal #op-step {
        margin-bottom: 1;
        color: $text;
    }
    OperationModal #op-progress-container {
        height: auto;
        margin-bottom: 1;
    }
    OperationModal ProgressBar {
        width: 100%;
    }
    OperationModal #op-log {
        height: 12;
        display: none;
        border: solid $border;
        margin: 1 0;
        background: $background;
    }
    OperationModal #op-log.visible {
        display: block;
    }
    OperationModal #op-footer {
        height: auto;
        margin-top: 1;
    }
    OperationModal #op-footer-hint {
        color: $text-muted;
    }
    OperationModal .op-buttons {
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        title: str,
        command: list[str] | None = None,
        parser: ProgressParser | None = None,
        steps: AsyncGenerator[ProgressUpdate] | None = None,
    ) -> None:
        """Create an operation modal.

        Args:
            title: Operation title shown at top.
            command: Subprocess command to run (mutually exclusive with steps).
            parser: ProgressParser to interpret subprocess output lines.
            steps: Async generator yielding ProgressUpdate objects directly.
        """
        super().__init__()
        self._title = title
        self._command = command
        self._parser = parser
        self._steps = steps
        self._rc: int = -1
        self._process: asyncio.subprocess.Process | None = None
        self._log_visible = False
        self._done = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, id="op-title", markup=False)
            yield Label("Preparing...", id="op-step", markup=False)
            with Static(id="op-progress-container"):
                yield ProgressBar(id="op-bar", total=100, show_eta=False)
            yield Log(id="op-log", highlight=True)
            yield Label("[l] Show log    [Esc] Cancel", id="op-footer-hint", markup=False)
            yield Button("Close", id="btn-close", variant="default", disabled=True)

    def on_mount(self) -> None:
        # Start indeterminate progress
        bar = self.query_one("#op-bar", ProgressBar)
        bar.update(total=None)  # indeterminate

        if self._steps is not None:
            self.run_worker(self._run_steps())
        elif self._command is not None:
            self.run_worker(self._run_command())

    async def _run_command(self) -> None:
        """Run a subprocess command with progress parsing."""
        from bluefinctl.core.progress import IndeterminateParser

        log = self.query_one("#op-log", Log)
        parser = self._parser or IndeterminateParser()

        try:
            self._process = await asyncio.create_subprocess_exec(
                self._command[0],  # type: ignore[index]
                *self._command[1:],  # type: ignore[index]
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            if self._process.stdout:
                async for raw_line in self._process.stdout:
                    line = raw_line.decode(errors="replace").rstrip()
                    log.write_line(line)

                    update = parser.parse_line(line)
                    if update:
                        self._apply_update(update)

            self._rc = await self._process.wait()

        except FileNotFoundError:
            log.write_line(f"Error: command not found — {self._command[0]}")  # type: ignore[index]
            self._rc = 127
        except Exception as exc:  # noqa: BLE001
            log.write_line(f"Error: {exc}")
            self._rc = 1
        finally:
            self._process = None
            self._finish()

    async def _run_steps(self) -> None:
        """Run an async generator workflow that yields ProgressUpdate objects."""
        log = self.query_one("#op-log", Log)

        try:
            async for update in self._steps:  # type: ignore[union-attr]
                self._apply_update(update)
                if update.message:
                    log.write_line(update.message)
            self._rc = 0
        except Exception as exc:  # noqa: BLE001
            log.write_line(f"Error: {exc}")
            self._rc = 1
        finally:
            self._finish()

    def _apply_update(self, update: ProgressUpdate) -> None:
        """Apply a progress update to the UI."""
        bar = self.query_one("#op-bar", ProgressBar)
        step_label = self.query_one("#op-step", Label)

        # Update step description
        if update.step and update.total_steps:
            step_label.update(
                f"Step {update.step}/{update.total_steps}: {update.message}",
            )
        elif update.message:
            step_label.update(update.message)

        # Update progress bar
        if update.percent is not None:
            bar.update(total=100, progress=update.percent)
            # Emit OSC 9;4
            with contextlib.suppress(Exception):
                osc_progress(int(update.percent))
        else:
            bar.update(total=None)  # indeterminate

    def _finish(self) -> None:
        """Mark operation as complete and enable Close button."""
        self._done = True
        bar = self.query_one("#op-bar", ProgressBar)
        step_label = self.query_one("#op-step", Label)
        btn = self.query_one("#btn-close", Button)
        hint = self.query_one("#op-footer-hint", Label)

        if self._rc == 0:
            bar.update(total=100, progress=100)
            step_label.update("Complete")
            with contextlib.suppress(Exception):
                osc_progress_clear()
        else:
            step_label.update(f"Failed (exit {self._rc})")
            with contextlib.suppress(Exception):
                osc_progress_error()

        hint.update("[Enter] Close")
        btn.disabled = False
        btn.focus()

    def action_toggle_log(self) -> None:
        """Toggle visibility of the raw log output."""
        log = self.query_one("#op-log", Log)
        self._log_visible = not self._log_visible
        if self._log_visible:
            log.add_class("visible")
            hint_text = "[l] Hide log    [Esc] Cancel"
        else:
            log.remove_class("visible")
            hint_text = "[l] Show log    [Esc] Cancel"

        if not self._done:
            self.query_one("#op-footer-hint", Label).update(hint_text)

    def action_cancel(self) -> None:
        """Cancel the operation or close if done."""
        if self._done:
            self.dismiss(self._rc)
        elif self._process:
            self._process.terminate()
        else:
            self.dismiss(-1)

    def on_button_pressed(self, _event: Button.Pressed) -> None:
        self.dismiss(self._rc)
