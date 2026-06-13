"""OSC escape sequence helpers for terminal integration.

Supports:
- OSC 0/2 — Terminal window/tab title
- OSC 9;4  — Progress bar in terminal titlebar/tab (Ghostty, Ptyxis, iTerm2, WezTerm)
- OSC 8   — Clickable hyperlinks
"""

from __future__ import annotations

import sys


def _write_osc(seq: str) -> None:
    try:
        with open('/dev/tty', 'w') as tty:
            tty.write(seq)
            tty.flush()
    except OSError:
        sys.stderr.write(seq)
        sys.stderr.flush()


def osc_progress(percent: int) -> None:
    """Emit OSC 9;4 progress indicator.

    Supported by: Ghostty, Ptyxis, iTerm2, WezTerm, ConEmu
    Shows a progress bar in the terminal's tab/titlebar.

    Args:
        percent: 0-100 for progress, -1 to clear
    """
    if percent < 0:
        _write_osc("\033]9;4;0;0\033\\")
    else:
        _write_osc(f"\033]9;4;1;{percent}\033\\")


def osc_progress_error() -> None:
    """Set progress indicator to error state (red)."""
    _write_osc("\033]9;4;2;100\033\\")


def osc_progress_indeterminate() -> None:
    """Set progress indicator to indeterminate (pulsing)."""
    _write_osc("\033]9;4;3;0\033\\")


def osc_progress_clear() -> None:
    """Clear the progress indicator."""
    osc_progress(-1)


def osc_hyperlink(url: str, text: str) -> str:
    """Return a string with an OSC 8 hyperlink.

    Renders as clickable in supported terminals.
    """
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def set_terminal_title(title: str) -> None:
    """Set the terminal window/tab title via OSC 0.

    OSC 0 sets both the icon name and window title. Supported by virtually
    all terminal emulators (Ghostty, Ptyxis, iTerm2, GNOME Terminal, etc.).
    """
    _write_osc(f"\033]0;{title}\007")


def osc_notify(title: str, body: str = "") -> None:
    """Send a desktop notification via OSC 777 (supported by some terminals)."""
    _write_osc(f"\033]777;notify;{title};{body}\033\\")
