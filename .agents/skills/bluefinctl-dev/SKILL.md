---
name: bluefinctl-dev
description: Development patterns and conventions for the bluefinctl Textual TUI project. Use when working in /var/home/jorge/src/bluefinctl, adding screens, wiring actions, creating modals, or modifying the theme/bundle system.
---

# bluefinctl Development

## Quick start

```bash
cd /var/home/jorge/src/bluefinctl
pip install -e ".[dev]"          # editable install
bctl                             # launch TUI (short alias)
ghostty -e bctl &                # launch in detached Ghostty window
ghostty -e textual run --dev src/bluefinctl/app.py &  # hot-reload CSS
```

## Architecture

```
core/           Business logic only — NO Textual imports, fully testable
screens/        One Screen subclass per panel, thin presentation layer
widgets/        adw.py · ops_bar.py · segmented_progress.py · rollback_calendar.py · operation_modal.py
theme/          accent.py (gsettings reader + theme builder) + bluefin.tcss
stacks/         Bundled AI stack quadlet files (nvidia/ and amd/)
util/           OSC escape sequences, Ghostty detection, terminal launcher
```

**Rule:** All subprocess calls, file I/O, and system state live in `core/`. Screens only call core functions and present results.

## Four screens

| Key | Screen file | Core module | Notes |
|-----|-------------|-------------|-------|
| 1 | screens/system.py | core/system.py | 2-col layout; Release Stream switch; Rollback calendar; AdwButtonsRow quick actions |
| 2 | screens/updates.py | core/updates.py | Full-width image banner; 2-col; radio schedule; OpsBar |
| 3 | screens/devmode.py | core/devmode.py + core/bundles.py | 3 tabs: Kits/Tools/Environments; devmode toggle at top |
| 4 | screens/ai.py | core/ai.py | 2 tabs: Stacks/Tools; category filter; bundled quadlet catalog |

Toolkit is merged into Developer Mode (tab 3). Navigation items: System, Updates, Developer, AI.

## ADW widget library — `widgets/adw.py`

All screens use GNOME HIG-compliant widgets. **Never use raw `Static` + borders for layout.**

```python
from bluefinctl.widgets.adw import (
    AdwPreferencesGroup,  # bordered group: title ABOVE box, rows inside
    AdwActionRow,         # title+subtitle left, trailing widget right
    AdwSwitchRow,         # fires AdwSwitchRow.Changed(row, value); subtitle supported
    AdwComboRow,          # cycling value label, fires AdwComboRow.Changed
    AdwButtonRow,         # full-width text row with › or action; subtitle supported
    AdwButtonsRow,        # real Textual Buttons side-by-side (accent-coloured primary)
    AdwPropertyRow,       # read-only key: value display
    AdwExpanderRow,       # collapsible row
)
```

### Row height rules (CRITICAL — learned the hard way)

**`height: auto` on Horizontal widgets does NOT size to content** in Textual — it fills available space instead. All row widgets use explicit `height: 1` (or `auto`) in DEFAULT_CSS.

**Switch replacement:** Textual's `Switch` widget uses `border: tall` (3 rows tall). We replaced it with `_CheckToggle`, a custom Widget that renders `[ ]`/`[✓]` at height 1.

### Two-column layout

Use `.adw-cols` / `.adw-col` CSS classes for side-by-side groups:

```python
with Horizontal(classes="adw-cols"):
    with Vertical(classes="adw-col"):   # left column
        yield AdwPreferencesGroup(...)
    with Vertical(classes="adw-col"):   # right column
        yield AdwPreferencesGroup(...)
```

`.adw-col` has `padding: 0 2` giving a 4-char gap between columns.

### Action buttons

Use `AdwButtonsRow` (real Textual `Button` widgets) for primary actions:

```python
yield AdwButtonsRow(
    Button("Update Now", variant="primary", id="btn-update"),
    Button("Check for Updates",              id="btn-check"),
)
# Handle via on_button_pressed (NOT on_adw_button_row_pressed)
```

Use `AdwButtonRow` for secondary suggestion rows (renders with › chevron or as radio options):

```python
yield AdwButtonRow("Roll Back to Previous Build", variant="destructive", id="btn-rollback")
# With subtitle (2-line display):
yield AdwButtonRow("● Automatic", subtitle="Downloads and installs automatically", id="sched-auto")
# Handle via on_adw_button_row_pressed
```

## Content area convention

Every screen uses `ScrollableContainer(id="adw-content")` + `OpsBar()`:

```python
def compose(self) -> ComposeResult:
    yield ViewSwitcher("myscreen")
    with ScrollableContainer(id="adw-content"):
        with Horizontal(classes="adw-cols"):
            with Vertical(classes="adw-col"):
                yield AdwPreferencesGroup("Left Group", ...)
            with Vertical(classes="adw-col"):
                yield AdwPreferencesGroup("Right Group", ...)
    yield OpsBar()   # always last — docks to bottom
```

## OpsBar — shared persistent bottom bar

`widgets/ops_bar.py` — docked `height: 3` at the bottom of every screen.

```python
from bluefinctl.widgets.ops_bar import OpsBar

# From any screen method:
self.query_one(OpsBar).set_idle("✓  Up to date")
self.query_one(OpsBar).set_running("Updating Brew…", stage=1)
self.query_one(OpsBar).set_complete("✓  Done")
self.query_one(OpsBar).set_confirm("Roll back?", "rollback")  # shows [Confirm][Cancel]

# Confirm handler:
def on_button_pressed(self, event: Button.Pressed) -> None:
    if event.button.id == "btn-op-confirm":
        op = self.query_one(OpsBar).pending_op   # "rollback", "channel-testing", etc.
        ...
    elif event.button.id == "btn-op-cancel":
        self.query_one(OpsBar).set_idle("Ready")
```

## Segmented progress bar

`widgets/segmented_progress.py` — multi-segment bar driven by uupd JSON output.

```python
from bluefinctl.widgets.segmented_progress import SegmentedProgressBar

bar = SegmentedProgressBar(stages=["System", "Brew", "Flatpak"])
bar.advance(1, 0.0)   # stage 1 active, 0% fill
bar.complete()        # all green
bar.complete(error_at=1)  # stage 1 errored
bar.reset()           # all grey/pending
```

## Rollback calendar

`widgets/rollback_calendar.py` — month grid with per-date image availability.

```python
from bluefinctl.widgets.rollback_calendar import RollbackCalendar

cal = RollbackCalendar(id="rollback-calendar")
# after loading image info:
cal.configure(
    base_ref="ghcr.io/projectbluefin/dakota",
    tag_prefix="latest",
)
# Handle selection:
def on_rollback_calendar_date_selected(self, event: RollbackCalendar.DateSelected):
    # event.date, event.image_ref
    self.run_worker(self._rollback_to(event.image_ref, str(event.date)))
```

## core/system.py — SystemInfo

```python
from bluefinctl.core.system import SystemInfo, get_system_info, get_image_compression

info = await get_system_info()
info.image_name       # "dakota"
info.image_tag        # "latest" or "testing"
info.image_ref        # "ostree-image-signed:docker://ghcr.io/projectbluefin/dakota"
info.clean_image_ref  # "ghcr.io/projectbluefin/dakota"   (no transport prefix, no tag)
info.full_clean_ref   # "ghcr.io/projectbluefin/dakota:latest"  (use this for display)
info.image_signed     # bool — True if ref started with "ostree-image-signed:"
info.image_staged     # bool — True if bootc status shows a staged update
info.boot_status      # "Current" or "Update staged — reboot to apply"

# Compression type via skopeo (network call — use as background worker):
comp = await get_image_compression(info.full_clean_ref)
# Returns: "zstd:chunked", "zstd", "gzip", or "unknown"
```

**Important:** `image_ref` from image-info.json does NOT include the tag (it's in `image_tag`).
Always use `full_clean_ref` for display. Use `clean_image_ref` (no tag) for `bootc switch` target base.

## Channel switching — correct bootc switch target

The image-ref in `/usr/share/ublue-os/image-info.json` has NO tag. Tags are stored separately.
To switch channels:

```python
info = await get_system_info()
base   = info.clean_image_ref          # "ghcr.io/projectbluefin/dakota"
target = f"{base}:testing"             # "ghcr.io/projectbluefin/dakota:testing"
# Run: ["pkexec", "bootc", "switch", target]
```

Verified real tags on registry: `:latest` and `:testing` both exist for projectbluefin/dakota.

## AI stack catalog

`stacks/nvidia/` and `stacks/amd/` — bundled quadlet files.

`_discover_stacks()` in `core/ai.py` checks system-installed dirs first, falls back to bundled catalog.

Deploy flow: `_copy_quadlets()` substitutes `${NGC_MONTH}` / `${ROCM_VERSION}` into container files.

## pkexec patterns

**One pkexec prompt per logical operation** — batch multiple systemctl calls:

```python
# GOOD: one prompt
script = "systemctl unmask uupd.timer && systemctl enable --now uupd.timer"
proc = await asyncio.create_subprocess_exec("pkexec", "bash", "-c", script, ...)

# BAD: two prompts
proc1 = await asyncio.create_subprocess_exec("pkexec", "systemctl", "unmask", ...)
proc2 = await asyncio.create_subprocess_exec("pkexec", "systemctl", "enable", ...)
```

## Theme system — live dark/light

The app follows GNOME `color-scheme` live via `gsettings monitor`. Never hardcode `$background`, `$surface`, etc. in TCSS — they resolve from the active Theme at runtime.

## Common pitfalls

- **`height: auto` on Horizontal** — expands to fill parent, not shrink to content. Use explicit `height: 1` and `on_mount` to set `height: 2` for subtitle rows.
- **Switch widget** — `border: tall` makes it 3 rows. Use `_CheckToggle` instead.
- **`AdwButtonRow` vs `AdwButtonsRow`** — `AdwButtonRow` = suggestion row with `›`; `AdwButtonsRow` = real Textual Buttons for primary actions.
- **`push_screen_wait` requires a worker** — Textual 1.x raises `NoActiveWorker` if called outside one. The correct fix is `@work(exclusive=True)` on the async method; it becomes a plain callable that starts a worker. Call it directly — no `run_worker(self.method())` wrapper needed. Applies to ALL async methods that call `push_screen_wait`, including action methods triggered by keybindings.
- **Console() in core**: never use rich Console inside Textual — use `self.notify()`
- **pkexec hangs**: polkit auth dialog appears in a separate GTK window — don't add timeouts
- **bootc switch**: positional target — `["pkexec", "bootc", "switch", ref]` not `--target`
- **Textual CSS**: `vh`/`vw` NOT supported; `Static` does NOT scroll (wrap in ScrollableContainer)
- **asyncio**: use `get_running_loop()` not `get_event_loop()` in async functions
- **CSS color vars**: never define `$background`/`$surface`/etc. in TCSS — breaks theme switching
- **lru_cache + live updates**: call `.cache_clear()` before re-reading a changed gsettings value
- **ADW `id` arg**: `A002` (shadowing builtin) is suppressed in `pyproject.toml` — it's standard Textual API
- **OpsBar placement**: always yield `OpsBar()` as the LAST child of compose — it uses `dock: bottom`
- **image-info.json tag**: `image-ref` has NO tag; `image_tag` is separate. Use `full_clean_ref` for display.
- **skopeo inspect for compression**: is a network call — always run as `run_worker`, never block the main thread
