"""LogView — streams subprocess output inside a Textual RichLog widget."""

from __future__ import annotations

import contextlib
from typing import Any

from textual.message import Message
from textual.widgets import RichLog


class LogView(RichLog):
    """A RichLog that runs a command and streams its combined stdout/stderr.

    Posts ``LogView.Done`` when the process exits.
    """

    class Done(Message):
        """Posted when the subprocess finishes."""

        def __init__(self, return_code: int) -> None:
            super().__init__()
            self.return_code = return_code

    def __init__(self, cmd: list[str], **kwargs: Any) -> None:
        super().__init__(highlight=True, markup=True, wrap=True, **kwargs)
        self._cmd = cmd

    def on_mount(self) -> None:
        self.run_worker(self._stream(), exclusive=True)

    async def _stream(self) -> None:
        import asyncio

        from bluefinctl.util.osc import osc_progress_clear, osc_progress_indeterminate

        with contextlib.suppress(Exception):
            osc_progress_indeterminate()

        rc: int
        try:
            proc = await asyncio.create_subprocess_exec(
                *self._cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            if proc.stdout:
                async for raw in proc.stdout:
                    line = raw.decode(errors="replace").rstrip()
                    self.write(line)
            await proc.wait()
            rc = proc.returncode or 0
        except FileNotFoundError:
            self.write(f"[red]Command not found: {self._cmd[0]}[/red]")
            rc = 127
        except Exception as e:
            self.write(f"[red]Error: {e}[/red]")
            rc = 1
        finally:
            with contextlib.suppress(Exception):
                osc_progress_clear()

        if rc == 0:
            self.write("[green]Done.[/green]")
        else:
            self.write(f"[red]Exited with code {rc}[/red]")

        self.post_message(self.Done(rc))
