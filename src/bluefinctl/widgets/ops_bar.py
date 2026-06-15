"""OpsBar — animated bottom-bar feedback widget.

The single source of operation feedback in bluefinctl. Docked to the
bottom of every screen. No in-app toasts anywhere.

Visual states::

  Idle (last result persists):
    ✓  Up to date

  Running (step 3/7, with completed-step ticker):
    ✓ Lima  ✓ Docker   ⠹  ████████░░░░░░░░  3/7  Installing VS Code…

  Running (no step counter):
    ⠸  Updating system…

  Success:
    ████████████████  ✓  Done — Docker installed

  Failure:
    ✗  Failed — brew install docker: exit 1

  Confirm pending:
    Roll back to previous build?     [Confirm] [Cancel]

API::

    ops = self.query_one(OpsBar)
    ops.set_idle("✓  Up to date")
    ops.set_running("Installing Docker…", step=1, total=4)
    ops.add_completed("Docker")              # ✓ Docker appears in ticker
    ops.set_running("Installing Lima…", step=2, total=4)
    ops.add_completed("Lima")
    ops.set_complete("✓  Done — 2 tools installed")
    ops.set_error("✗  Failed — brew install: exit 1")
    ops.set_confirm("Roll back to 20250610?", "rollback:ref")
    # then read ops.pending_op in on_button_pressed

Backward-compatible with old call sites that pass stage= keyword.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Label

# ── Spinner ───────────────────────────────────────────────────────────────────
_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_SPINNER_LEN = len(_SPINNER)

# ── Block bar ─────────────────────────────────────────────────────────────────
_BAR_WIDTH = 16
_FILL = "█"
_EMPTY = "░"

# ── States ────────────────────────────────────────────────────────────────────
_IDLE = "idle"
_RUNNING = "running"
_COMPLETE = "complete"
_ERROR = "error"
_CONFIRM = "confirm"

# Max completed steps to show in the ticker prefix (avoids overflow)
_MAX_TICKER = 5


class OpsBar(Widget):
    """Persistent animated bottom bar — the single source of operation feedback.

    Layout (height 3 = 1 border-top + 2 content rows):
      Row 1: ops-label  — full-width status/progress text with Rich markup
      Row 2: (blank — used for vertical centering within the 2 content rows)

    The confirm buttons float to the right inside ops-label row.
    """

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
    OpsBar #ops-label {
        width: 1fr;
        height: 1;
        content-align: left middle;
    }
    OpsBar #ops-confirm-btns {
        width: auto;
        height: 1;
        display: none;
        align: right middle;
    }
    OpsBar #ops-confirm-btns.visible {
        display: block;
    }
    OpsBar #ops-confirm-btns Button {
        margin-left: 1;
        height: 1;
        min-width: 10;
    }
    """

    #: Reactive — readable by screens after set_confirm()
    pending_op: reactive[str] = reactive("")

    def __init__(
        self,
        stages: list[str] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        _ = stages  # backward-compat; not used in new design
        self._state: str = _IDLE
        self._message: str = ""
        self._step: int = 0
        self._total: int = 0
        self._completed: list[str] = []
        self._spinner_idx: int = 0

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Label("", id="ops-label", markup=True)
        with Horizontal(id="ops-confirm-btns"):
            yield Button("Confirm", id="btn-op-confirm", variant="warning")
            yield Button("Cancel",  id="btn-op-cancel",  variant="default")

    def on_mount(self) -> None:
        # Tick every 100 ms — advances spinner only when running
        self.set_interval(0.1, self._tick)

    # ── Animation tick ────────────────────────────────────────────────────────

    def _tick(self) -> None:
        if self._state == _RUNNING:
            self._spinner_idx = (self._spinner_idx + 1) % _SPINNER_LEN
            self._refresh_label()

    # ── Markup builder ────────────────────────────────────────────────────────

    def _build_markup(self) -> str:  # noqa: PLR0911
        """Return the Rich markup string for the current state."""
        if self._state == _IDLE:
            return self._message

        if self._state == _RUNNING:
            ticker = self._build_ticker()
            sp = _SPINNER[self._spinner_idx]
            if self._total > 0:
                pct   = max(0.0, min(1.0, self._step / self._total))
                n_fill = int(_BAR_WIDTH * pct)
                n_empty = _BAR_WIDTH - n_fill
                bar = (
                    f"[green]{'█' * n_fill}[/green]"
                    f"[dim]{'░' * n_empty}[/dim]"
                )
                ctr = f"[dim]{self._step}/{self._total}[/dim]"
                return f"{ticker}[yellow]{sp}[/yellow]  {bar}  {ctr}  {self._message}"
            return f"{ticker}[yellow]{sp}[/yellow]  {self._message}"

        if self._state == _COMPLETE:
            bar = f"[green]{'█' * _BAR_WIDTH}[/green]"
            return f"{bar}  [bold green]{self._message}[/bold green]"

        if self._state == _ERROR:
            return f"[bold red]{self._message}[/bold red]"

        if self._state == _CONFIRM:
            return f"[yellow]{self._message}[/yellow]"

        return self._message

    def _build_ticker(self) -> str:
        """Build the ✓-prefixed completed-step ticker that precedes the spinner."""
        if not self._completed:
            return ""
        recent = self._completed[-_MAX_TICKER:]
        parts = [f"[dim green]✓ {c}[/dim green]" for c in recent]
        return "  ".join(parts) + "   "

    def _refresh_label(self) -> None:
        self.query_one("#ops-label", Label).update(self._build_markup())

    # ── Confirm buttons ───────────────────────────────────────────────────────

    def _set_confirm_visible(self, visible: bool) -> None:
        try:
            btns = self.query_one("#ops-confirm-btns")
            if visible:
                btns.add_class("visible")
            else:
                btns.remove_class("visible")
        except Exception:  # noqa: BLE001
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    def set_idle(self, message: str) -> None:
        """Show a static status message (idle).  Persists until next operation."""
        self._state    = _IDLE
        self._message  = message
        self._step     = 0
        self._total    = 0
        self._completed = []
        self._refresh_label()
        self._set_confirm_visible(False)

    def set_running(
        self,
        message: str,
        *,
        step: int = 0,
        total: int = 0,
        stage: int = 0,   # backward-compat alias for step
    ) -> None:
        """Start the animated spinner + block progress bar.

        Args:
            message: Current step description shown after the bar.
            step:    Current step index (1-based).  0 = indeterminate.
            total:   Total steps.  0 = indeterminate.
            stage:   Alias for ``step`` (kept for backward-compat).
        """
        self._state   = _RUNNING
        self._message = message
        if step:
            self._step = step
        elif stage:
            self._step = stage
        if total:
            self._total = total
        self._refresh_label()
        self._set_confirm_visible(False)

    def add_completed(self, name: str) -> None:
        """Mark a step done — scrolls ``✓ <name>`` into the ticker strip."""
        self._completed.append(name)
        if self._state == _RUNNING:
            self._refresh_label()

    def set_complete(self, message: str) -> None:
        """Show a full green bar and success message."""
        self._state    = _COMPLETE
        self._message  = message
        self._step     = self._total
        self._completed = []
        self._refresh_label()
        self._set_confirm_visible(False)

    def set_error(self, message: str) -> None:
        """Show a red failure message."""
        self._state    = _ERROR
        self._message  = message
        self._completed = []
        self._refresh_label()
        self._set_confirm_visible(False)

    def set_confirm(self, message: str, op: str) -> None:
        """Show confirm/cancel buttons for a pending destructive operation.

        After calling this, read ``ops.pending_op`` in ``on_button_pressed``
        when ``btn-op-confirm`` fires.
        """
        self.pending_op = op
        self._state    = _CONFIRM
        self._message  = message
        self._refresh_label()
        self._set_confirm_visible(True)
