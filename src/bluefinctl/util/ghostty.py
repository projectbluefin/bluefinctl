"""Ghostty-specific terminal integration.

Detects Ghostty terminal and enables enhanced features:
- Kitty keyboard protocol for richer keybindings
- Ghostty's app-id for window management
- sixel/kitty graphics protocol detection
"""

from __future__ import annotations

import os


def is_ghostty() -> bool:
    """Check if running inside Ghostty terminal."""
    return os.environ.get("TERM_PROGRAM") == "ghostty"


def is_ptyxis() -> bool:
    """Check if running inside Ptyxis (GNOME Terminal successor)."""
    return os.environ.get("TERM_PROGRAM") == "ptyxis"


def get_terminal_name() -> str:
    """Get the name of the current terminal emulator."""
    term_program = os.environ.get("TERM_PROGRAM", "")
    if term_program:
        return term_program
    # Fallback: check TERM
    return os.environ.get("TERM", "unknown")


def supports_kitty_keyboard() -> bool:
    """Check if terminal supports Kitty keyboard protocol.

    Ghostty and Kitty both support this for enhanced key handling.
    """
    return os.environ.get("TERM_PROGRAM") in ("ghostty", "kitty", "WezTerm")


def supports_graphics() -> bool:
    """Check if terminal supports inline graphics (sixel or kitty protocol)."""
    # Ghostty supports kitty graphics protocol
    # This could be used for inline GPU graphs, sparklines, etc.
    return os.environ.get("TERM_PROGRAM") in ("ghostty", "kitty", "WezTerm")
