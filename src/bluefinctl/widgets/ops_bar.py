"""Shared bottom operations bar — persistent across all screens and tabs.

Always docked to the bottom of whichever screen mounts it.  Displays:
  - A short status message (left)
  - A SegmentedProgressBar (centre, fills remaining width)
  - Optional [Confirm] / [Cancel] buttons for destructive ops (right)

Usage in a Screen::

    def compose(self) -> ComposeResult:
        yield ViewSwitcher("updates")
        with ScrollableContainer(id="adw-content"):
            ...
        yield OpsBar()

    # Then call helpers from screen methods:
    self.query_one(OpsBar).set_idle("✓  Up to date")
    self.query_one(OpsBar).set_running("Updating Brew…", stage=1)
    self.query_one(OpsBar).set_confirm("Roll back?", "rollback")
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Label

from bluefinctl.widgets.segmented_progress import SegmentedProgressBar


class OpsBar(Widget):
    """Persistent bottom bar: status + segmented progress + optional confirm."""

    DEFAULT_CSS = """
    OpsBar {
        dock: bottom;
        height: 3;
        width: 1fr;
        background: $panel;
        border-top: solid $surface;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    OpsBar #ops-msg {
        width: 22;
        color: $text-muted;
    }
    OpsBar #ops-progress {
        width: 1fr;
    }
    OpsBar #ops-confirm-btns {
        width: auto;
        display: none;
        align: right middle;
    }
    OpsBar #ops-confirm-btns.visible {
        display: block;
    }
    OpsBar #ops-confirm-btns Button {
        margin-left: 1;
        height: 1;
    }
    """

    def __init__(
        self,
        stages: list[str] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._stages = stages or []
        self._pending_op: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("Ready", id="ops-msg")
        yield SegmentedProgressBar(stages=self._stages, id="ops-progress")
        with Horizontal(id="ops-confirm-btns"):
            yield Button("Confirm", id="btn-op-confirm", variant="error")
            yield Button("Cancel",  id="btn-op-cancel",  variant="default")

    # ── helpers ───────────────────────────────────────────────────────────────

    @property
    def pending_op(self) -> str | None:
        return self._pending_op

    def _bar(self) -> SegmentedProgressBar:
        return self.query_one("#ops-progress", SegmentedProgressBar)

    def set_stages(self, stages: list[str]) -> None:
        """Replace the segment labels (e.g. when switching operation type)."""
        self._bar().set_stages(stages)

    def set_idle(self, message: str) -> None:
        """Show a static status; reset all segments to empty."""
        self._pending_op = None
        self.query_one("#ops-msg", Label).update(message)
        self._bar().reset()
        self.query_one("#ops-confirm-btns").remove_class("visible")

    def set_running(self, message: str, stage: int = 0) -> None:
        """Show running state and advance the bar to the given stage index."""
        self._pending_op = None
        self.query_one("#ops-msg", Label).update(message)
        self._bar().advance(stage, 0.0)
        self.query_one("#ops-confirm-btns").remove_class("visible")

    def set_complete(self, message: str, *, error_at: int | None = None) -> None:
        """Mark all stages done (or one errored) and show final message."""
        self._pending_op = None
        self.query_one("#ops-msg", Label).update(message)
        self._bar().complete(error_at=error_at)
        self.query_one("#ops-confirm-btns").remove_class("visible")

    def set_confirm(self, message: str, op_key: str) -> None:
        """Show an inline confirm prompt; op_key is passed back on Confirm."""
        self._pending_op = op_key
        self.query_one("#ops-msg", Label).update(message)
        self._bar().reset()
        self.query_one("#ops-confirm-btns").add_class("visible")

    def update_message(self, message: str) -> None:
        """Update only the status message without touching the bar."""
        self.query_one("#ops-msg", Label).update(message)
