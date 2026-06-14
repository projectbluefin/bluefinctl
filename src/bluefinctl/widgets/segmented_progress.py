"""Multi-segment progress bar widget.

Renders a row of named segments, each with fill state:

    ✓ System ██████████  ▶ Brew ████░░░░░░  · Flatpak ░░░░░░░░░░

States per segment:
    pending  — muted, empty bar
    active   — bold, partially filled bar
    done     — green, full bar
    error    — red, filled to failure point
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rich.text import Text
from textual.widget import Widget

SegState = Literal["pending", "active", "done", "error"]


@dataclass
class Segment:
    name: str
    progress: float = 0.0       # 0.0 – 1.0
    state: SegState = "pending"


class SegmentedProgressBar(Widget):
    """Horizontal multi-segment progress bar.

    Usage::

        bar = SegmentedProgressBar(id="ops-progress")
        bar.set_stages(["System", "Brew", "Flatpak"])

        # Mark stage 0 active at 40%
        bar.advance(0, 0.4)

        # Mark stage 0 done, stage 1 active at 0%
        bar.advance(1, 0.0)

        # All done
        bar.complete()

        # Reset to idle
        bar.reset()
    """

    DEFAULT_CSS = """
    SegmentedProgressBar {
        height: 1;
        width: 1fr;
        background: transparent;
    }
    """

    def __init__(self, stages: list[str] | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._segs: list[Segment] = [Segment(n) for n in (stages or [])]

    # ── Public API ────────────────────────────────────────────────────────────

    def set_stages(self, names: list[str]) -> None:
        """Replace stages and reset to idle."""
        self._segs = [Segment(n) for n in names]
        self.refresh()

    def advance(self, stage_index: int, stage_progress: float = 0.0) -> None:
        """Mark stages before index as done; set stage_index to active."""
        for i, seg in enumerate(self._segs):
            if i < stage_index:
                seg.state = "done"
                seg.progress = 1.0
            elif i == stage_index:
                seg.state = "active"
                seg.progress = max(0.0, min(1.0, stage_progress))
            else:
                seg.state = "pending"
                seg.progress = 0.0
        self.refresh()

    def complete(self, *, error_at: int | None = None) -> None:
        """Mark all stages done (or mark error_at stage as error)."""
        for i, seg in enumerate(self._segs):
            if error_at is not None and i == error_at:
                seg.state = "error"
            else:
                seg.state = "done"
                seg.progress = 1.0
        self.refresh()

    def reset(self) -> None:
        """Reset all segments to pending/empty."""
        for seg in self._segs:
            seg.state = "pending"
            seg.progress = 0.0
        self.refresh()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def render(self) -> Text:
        if not self._segs:
            return Text("Ready", style="dim")

        width = self.size.width or 80
        n = len(self._segs)
        gap = 2
        # Each segment: icon(2) + name + space(1) + bar
        available = width - gap * (n - 1)
        per_seg = available // n
        bar_w = max(6, per_seg - 12)   # leave room for icon + name

        result = Text()
        for i, seg in enumerate(self._segs):
            if i > 0:
                result.append(" " * gap)

            filled = round(seg.progress * bar_w)
            empty = bar_w - filled
            name = seg.name[:10]

            if seg.state == "done":
                result.append("✓ ", style="bold green")
                result.append(f"{name:<10}", style="green")
                result.append(" ")
                result.append("█" * bar_w, style="green")

            elif seg.state == "active":
                result.append("▶ ", style="bold")
                result.append(f"{name:<10}", style="bold")
                result.append(" ")
                result.append("█" * filled, style="bold")
                result.append("░" * empty, style="dim")

            elif seg.state == "error":
                result.append("✗ ", style="bold red")
                result.append(f"{name:<10}", style="red")
                result.append(" ")
                result.append("█" * filled, style="red bold")
                result.append("░" * empty, style="dim red")

            else:  # pending
                result.append("· ", style="dim")
                result.append(f"{name:<10}", style="dim")
                result.append(" ")
                result.append("░" * bar_w, style="dim")

        return result
