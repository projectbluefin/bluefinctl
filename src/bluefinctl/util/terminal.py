"""Launch external applications in a new terminal window.

Detects the running terminal emulator and spawns a new window/tab
with the specified command.

Supported terminals (in priority order):
  - Ghostty
  - Ptyxis (GNOME 47+)
  - gnome-terminal
  - xterm (fallback)
"""

from __future__ import annotations

import os
import shutil
import subprocess


def _detect_terminal() -> str:
    """Detect the current terminal emulator."""
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    if term_program == "ghostty":
        return "ghostty"

    # Check for Ptyxis (GNOME Console)
    if shutil.which("ptyxis"):
        return "ptyxis"

    # Check for gnome-terminal
    if shutil.which("gnome-terminal"):
        return "gnome-terminal"

    # Fallback
    return "xterm"


def launch_in_terminal(command: list[str], title: str = "") -> None:
    """Launch a command in a new terminal window.

    Args:
        command: Command and arguments to run.
        title: Optional window title.
    """
    terminal = _detect_terminal()

    if terminal == "ghostty":
        args = ["ghostty", "-e", *command]
        if title:
            args = ["ghostty", f"--title={title}", "-e", *command]
    elif terminal == "ptyxis":
        args = ["ptyxis", "--", *command]
    elif terminal == "gnome-terminal":
        args = ["gnome-terminal", "--"]
        if title:
            args = ["gnome-terminal", f"--title={title}", "--"]
        args.extend(command)
    else:
        args = ["xterm", "-e", *command]
        if title:
            args = ["xterm", "-T", title, "-e", *command]

    subprocess.Popen(
        args,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
