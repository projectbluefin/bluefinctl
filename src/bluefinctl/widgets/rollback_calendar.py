"""Rollback calendar widget.

Shows a month grid where each date cell indicates whether a bootc image
was published on that date.  Arrow-key navigation, Enter to roll back.

Design spec: docs/DESIGN.md § "Rollback Calendar Card"

Tag format:   <base>:<version>-<YYYYMMDD>
              e.g. ghcr.io/projectbluefin/dakota:latest-20260610
Verification: skopeo inspect --raw docker://<ref>  (lightweight manifest HEAD)
Cache:        ~/.local/state/bluefinctl/available-images.json  (TTL 24 h)
"""

from __future__ import annotations

import asyncio
import datetime
import json
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label

_CACHE_PATH = Path.home() / ".local" / "state" / "bluefinctl" / "available-images.json"
_CACHE_TTL_HOURS = 24
_DOW = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def _load_cache() -> dict[str, bool]:
    """Load availability cache, drop entries older than TTL."""
    if not _CACHE_PATH.exists():
        return {}
    try:
        raw = json.loads(_CACHE_PATH.read_text())
        cutoff = (
            datetime.datetime.now() - datetime.timedelta(hours=_CACHE_TTL_HOURS)
        ).isoformat()
        return {
            k: v["avail"]
            for k, v in raw.items()
            if isinstance(v, dict) and v.get("ts", "") >= cutoff
        }
    except Exception:  # noqa: BLE001
        return {}


def _save_cache(data: dict[str, bool]) -> None:
    """Persist availability cache with timestamps."""
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().isoformat()
    serialised = {k: {"avail": v, "ts": ts} for k, v in data.items()}
    _CACHE_PATH.write_text(json.dumps(serialised, indent=2))


def _tag_for_date(base_ref: str, tag_prefix: str, d: datetime.date) -> str:
    """Build the image ref for a specific date."""
    return f"{base_ref}:{tag_prefix}-{d.strftime('%Y%m%d')}"


class RollbackCalendar(Widget):
    """Interactive month calendar for picking a rollback image date.

    Fire ``RollbackCalendar.DateSelected`` when the user presses Enter on
    a date that has been verified as available.

    Usage::

        cal = RollbackCalendar()
        # once system info is loaded:
        cal.configure("ghcr.io/projectbluefin/dakota", "latest")
    """

    class DateSelected(Message):
        """User confirmed a rollback target date."""

        def __init__(self, date: datetime.date, image_ref: str) -> None:
            super().__init__()
            self.date = date
            self.image_ref = image_ref

    BINDINGS = [
        Binding("left",  "prev_day",  "Previous day",  show=False),
        Binding("right", "next_day",  "Next day",      show=False),
        Binding("up",    "prev_week", "Previous week", show=False),
        Binding("down",  "next_week", "Next week",     show=False),
        Binding("enter", "select",    "Roll back",     show=False),
    ]

    DEFAULT_CSS = """
    RollbackCalendar {
        height: auto;
        background: $surface;
        padding: 0 1;
        border: round $panel;
    }
    RollbackCalendar > #cal-hint {
        color: $text-muted;
        height: 1;
        margin-top: 1;
    }
    """

    can_focus = True

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._base_ref: str = ""
        self._tag_prefix: str = ""
        self._today = datetime.date.today()
        self._cursor = self._today
        self._booted_date: datetime.date | None = None
        # Three-value availability: True=available, False=unavailable, None=unknown
        self._avail: dict[datetime.date, bool | None] = {}
        self._cache: dict[str, bool] = {}

    def compose(self) -> ComposeResult:
        yield Label("", id="cal-hint")

    def on_mount(self) -> None:
        self._cache = _load_cache()
        self._update_hint()

    # ── Public API ────────────────────────────────────────────────────────────

    def configure(
        self,
        base_ref: str,
        tag_prefix: str,
        booted_date: datetime.date | None = None,
    ) -> None:
        """Set image info and kick off background verification."""
        self._base_ref = base_ref
        self._tag_prefix = tag_prefix
        self._booted_date = booted_date
        self.run_worker(self._verify_recent(days=7), exclusive=True)
        self.refresh()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def render(self) -> Text:
        result = Text()

        # Month header
        result.append(
            f" {self._cursor.strftime('%B %Y')}\n",
            style="bold",
        )

        # Day-of-week row
        result.append(" " + "  ".join(_DOW) + "\n", style="dim")

        # Build the month grid
        first = self._cursor.replace(day=1)
        # isoweekday: Mon=1, Sun=7 → pad=0..6
        pad = (first.isoweekday() - 1) % 7
        result.append("   " * pad)

        day = first
        col = pad
        while day.month == self._cursor.month:
            style, text = self._cell(day)
            result.append(text, style=style)
            col += 1
            if col % 7 == 0:
                result.append("\n")
            else:
                result.append(" ")
            day += datetime.timedelta(days=1)

        if col % 7 != 0:
            result.append("\n")

        return result

    def _cell(self, day: datetime.date) -> tuple[str, str]:
        """Return (rich_style, text) for one date cell."""
        is_cursor  = day == self._cursor
        is_today   = day == self._today
        is_booted  = day == self._booted_date
        is_future  = day > self._today

        avail = self._avail.get(day)

        if is_future:
            style = "dim"
            text  = f" {day.day:2}"
        elif is_cursor:
            style = "bold reverse"
            text  = f"[{day.day:2}]"
        elif is_booted:
            style = "bold green"
            text  = f"*{day.day:2}"
        elif avail is True:
            style = "green" if is_today else ""
            text  = f" {day.day:2}"
        elif avail is False:
            style = "dim red"
            text  = f" {day.day:2}"
        else:
            # Not yet verified
            style = "dim"
            text  = " . "

        return style, f"{text:3}"

    def _update_hint(self) -> None:
        try:
            hint = self.query_one("#cal-hint", Label)
        except Exception:  # noqa: BLE001
            return
        if self._base_ref:
            ref = _tag_for_date(self._base_ref, self._tag_prefix, self._cursor)
            avail = self._avail.get(self._cursor)
            if avail is True:
                status = "✓ available — Enter to roll back"
            elif avail is False:
                status = "✗ no build on this date"
            else:
                status = "· verifying…"
            hint.update(f" {ref}  {status}")
        else:
            hint.update(" Loading image info…")

    # ── Navigation ────────────────────────────────────────────────────────────

    def action_prev_day(self) -> None:
        self._cursor -= datetime.timedelta(days=1)
        self._maybe_verify(self._cursor)
        self.refresh()
        self._update_hint()

    def action_next_day(self) -> None:
        new = self._cursor + datetime.timedelta(days=1)
        if new <= self._today:
            self._cursor = new
            self._maybe_verify(self._cursor)
            self.refresh()
            self._update_hint()

    def action_prev_week(self) -> None:
        self._cursor -= datetime.timedelta(weeks=1)
        self._maybe_verify(self._cursor)
        self.refresh()
        self._update_hint()

    def action_next_week(self) -> None:
        new = self._cursor + datetime.timedelta(weeks=1)
        if new <= self._today:
            self._cursor = new
            self._maybe_verify(self._cursor)
            self.refresh()
            self._update_hint()

    def action_select(self) -> None:
        if not self._base_ref:
            return
        avail = self._avail.get(self._cursor)
        if avail is True:
            ref = _tag_for_date(self._base_ref, self._tag_prefix, self._cursor)
            self.post_message(self.DateSelected(self._cursor, ref))
        elif avail is None:
            # Verify first, then re-prompt
            self.run_worker(self._verify_one(self._cursor), exclusive=True)

    # ── Verification ─────────────────────────────────────────────────────────

    def _maybe_verify(self, day: datetime.date) -> None:
        if day not in self._avail and not day > self._today:
            self.run_worker(self._verify_one(day))

    async def _verify_recent(self, days: int = 7) -> None:
        """Verify the last N days in the background."""
        today = self._today
        for i in range(days):
            d = today - datetime.timedelta(days=i)
            await self._verify_one(d)

    async def _verify_one(self, day: datetime.date) -> None:
        if not self._base_ref or day > self._today:
            return
        ref = _tag_for_date(self._base_ref, self._tag_prefix, day)
        # Check cache first
        if ref in self._cache:
            self._avail[day] = self._cache[ref]
            self.refresh()
            self._update_hint()
            return

        available = await _check_image_exists(ref)
        self._avail[day] = available
        self._cache[ref] = available
        _save_cache(self._cache)
        self.refresh()
        self._update_hint()


async def _check_image_exists(ref: str) -> bool:
    """Return True if the OCI image tag exists (lightweight manifest HEAD)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "skopeo", "inspect", "--raw", f"docker://{ref}",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=10.0)
        return proc.returncode == 0
    except (TimeoutError, FileNotFoundError, OSError):
        # Fallback: try with podman manifest inspect
        try:
            result = await asyncio.create_subprocess_exec(
                "podman", "manifest", "inspect", ref,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(result.wait(), timeout=10.0)
            return result.returncode == 0
        except (TimeoutError, FileNotFoundError, OSError):
            return False
