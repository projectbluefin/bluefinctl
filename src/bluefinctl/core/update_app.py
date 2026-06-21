"""CLI progress runner for ``bctl update``.

Uses Rich Progress for clean multi-task in-place updates — no scroll, no mess.
Supports Ghostty, Ptyxis, and any ANSI terminal.

Visual layout (each row updates in-place via cursor-up, no scrolling):

  ⠹  System Image    ━━━━━━━━░░░░░░░░  14/19  Pulling · ↓ 1.2 GB  0:01:23
  ⠸  Flatpak         ░░░░░░░░░░░░░░░░     —   updating…           0:00:18
  ✓  Homebrew        ━━━━━━━━━━━━━━━━   1/1   2 formulae upgraded  0:00:12
  ⠹  Containers      ░░░░░░░░░░░░░░░░     —   waiting…            0:00:03

OSC 9;4 progress is written to /dev/tty alongside — updates the tab/titlebar
in Ghostty and Ptyxis without interfering with the Rich display.
"""

from __future__ import annotations

import asyncio
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.style import Style
from rich.table import Column
from rich.text import Text

from bluefinctl.util.osc import (
    osc_notify,
    osc_progress,
    osc_progress_clear,
    osc_progress_error,
    osc_progress_indeterminate,
    set_terminal_title,
)

# ── Custom column ─────────────────────────────────────────────────────────────

class _StatColumn(ProgressColumn):
    """Dim stat field — shows stage label, data size, or result summary."""

    def __init__(self) -> None:
        super().__init__(table_column=Column(min_width=22, no_wrap=True))

    def render(self, task: Task) -> Text:
        return Text(task.fields.get("stat", ""), style="dim")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_bytes(n: float) -> str:
    """Format byte count as a terse human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


_STAGE_LABEL     = {"pulling": "Pulling", "importing": "Importing", "staging": "Staging"}
_STAGE_OSC_START = {"pulling": 0,  "importing": 72, "staging": 81}
_STAGE_OSC_LEN   = {"pulling": 72, "importing":  9, "staging":  9}


def _make_progress(accent_hex: str) -> Progress:
    accent = Style(color=accent_hex)
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}[/bold]", table_column=Column(min_width=14)),
        BarColumn(
            bar_width=None,         # expands to fill terminal width
            complete_style=accent,
            finished_style=accent,
            pulse_style=Style(color=accent_hex, dim=True),
        ),
        MofNCompleteColumn(),
        _StatColumn(),
        TimeElapsedColumn(),
        console=Console(highlight=False),
        transient=False,
        refresh_per_second=10,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

async def run_update_cli(*, accent_hex: str, has_containers: bool) -> str:
    """Run a full system update. Returns ``"done"`` or ``"failed"``."""
    from bluefinctl.core.update_runner import (
        run_bootc_upgrade,
        run_brew_update,
        run_flatpak_update,
    )
    if has_containers:
        from bluefinctl.core.update_runner import run_container_autoupdate

    progress = _make_progress(accent_hex)

    with progress:
        # ── Phase 1: bootc ────────────────────────────────────────────────────
        bootc_id = progress.add_task("System Image", total=None, stat="connecting…")
        osc_progress_indeterminate()
        set_terminal_title("bctl update · System Image…")

        # Accumulate bytes transferred across all layers.
        # ProgressBytes gives bytes_/bytes_total for the *current* layer.
        # We sum bytes_total for layers we've fully seen and add the
        # in-progress bytes for the current layer.
        _layer_bytes_done: list[int] = []
        _current_layer_bytes = 0
        _bootc_steps_total = 0

        bootc_ok = True
        try:
            async for event in run_bootc_upgrade():
                if event.type == "ProgressBytes" and event.bytes_total > 0:
                    _current_layer_bytes = event.bytes_
                    # Layer fully received — commit it
                    if event.bytes_ >= event.bytes_total:
                        _layer_bytes_done.append(event.bytes_total)
                        _current_layer_bytes = 0

                elif event.type == "ProgressSteps" and event.steps_total > 0:
                    _bootc_steps_total = event.steps_total
                    stage     = _STAGE_LABEL.get(event.task, event.task.title() or "Working")
                    osc_start = _STAGE_OSC_START.get(event.task, 0)
                    osc_len   = _STAGE_OSC_LEN.get(event.task, 9)
                    pct       = event.steps / event.steps_total

                    osc_progress(int(osc_start + pct * osc_len))
                    set_terminal_title(
                        f"bctl update · {stage} {event.steps}/{event.steps_total}"
                    )

                    total_bytes = sum(_layer_bytes_done) + _current_layer_bytes
                    bytes_str   = f"↓ {_fmt_bytes(total_bytes)}" if total_bytes > 0 else ""
                    stat        = stage + (f"  ·  {bytes_str}" if bytes_str else "")

                    progress.update(
                        bootc_id,
                        total=event.steps_total,
                        completed=event.steps,
                        stat=stat,
                    )
                elif event.percent is not None:
                    pct = max(0.0, min(event.percent, 100.0))
                    progress.update(
                        bootc_id,
                        total=100,
                        completed=pct,
                        stat=event.description or "Working…",
                    )
                    osc_progress(int(pct))
                    if event.description:
                        set_terminal_title(f"bctl update · {event.description}")

        except Exception:  # noqa: BLE001
            bootc_ok = False

        if not bootc_ok:
            progress.update(
                bootc_id,
                description="[red]✗[/red] System Image",
                stat="failed",
            )
            osc_progress_error()
            osc_progress_clear()
            set_terminal_title("")
            return "failed"

        # Mark bootc complete — show final total bytes pulled
        final_bytes = sum(_layer_bytes_done) + _current_layer_bytes
        final_stat  = "staged — reboot when ready"
        if final_bytes > 0:
            final_stat = f"↓ {_fmt_bytes(final_bytes)}  ·  {final_stat}"

        t = _bootc_steps_total or 1
        progress.update(
            bootc_id,
            total=t,
            completed=t,
            description=f"[{accent_hex}]✓[/{accent_hex}] System Image",
            stat=final_stat,
        )
        osc_progress(90)

        # ── Phase 2: flatpak · brew · [containers] ────────────────────────────
        set_terminal_title("bctl update · Updating apps…")

        flatpak_id   = progress.add_task("Flatpak",    total=None, stat="")
        brew_id      = progress.add_task("Homebrew",   total=None, stat="")
        container_id: TaskID | None = (
            progress.add_task("Containers", total=None, stat="")
            if has_containers else None
        )

        async def _run(coro: Any, task_id: TaskID, label: str) -> tuple[bool, str]:
            try:
                ok, summary = await coro
            except Exception as exc:  # noqa: BLE001
                ok, summary = False, str(exc)
            icon = f"[{accent_hex}]✓[/{accent_hex}]" if ok else "[red]✗[/red]"
            progress.update(
                task_id,
                total=1,
                completed=1,
                description=f"{icon} {label}",
                stat=summary,
            )
            return ok, summary

        runners: list[Any] = [
            _run(run_flatpak_update(),  flatpak_id,   "Flatpak"),
            _run(run_brew_update(),     brew_id,      "Homebrew"),
        ]
        if has_containers and container_id is not None:
            runners.append(_run(run_container_autoupdate(), container_id, "Containers"))

        await asyncio.gather(*runners)

        osc_progress(100)
        set_terminal_title("bctl update · Done ✓")
        osc_notify("bctl update", "System update complete — reboot when ready")
        osc_progress_clear()
        set_terminal_title("")

    return "done"
