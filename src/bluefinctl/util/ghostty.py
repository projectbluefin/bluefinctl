"""Ghostty terminal detection."""

from __future__ import annotations

import os


def is_ghostty() -> bool:
    """Check if running inside Ghostty terminal."""
    return os.environ.get("TERM_PROGRAM") == "ghostty"
