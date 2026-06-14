---
name: bluefinctl-dev
description: >-
  Development patterns and conventions for the bluefinctl Textual TUI project.
  Use when working in /var/home/jorge/src/bluefinctl — adding screens, wiring
  actions, creating modals, modifying the theme/bundle system, working with
  core/ modules, or debugging layout issues. Covers the 4-screen navigation
  (System, Updates, Developer, AI), ADW widget library, OpsBar, @work pattern,
  bootc image ref handling, and all non-obvious Textual behaviors discovered
  in this codebase.
metadata:
  context7-sources:
    - /textualize/textual
    - /tiangolo/typer
---

# bluefinctl Development

## When to Use

- Adding or modifying any screen in `screens/`
- Working with `core/` modules (system, updates, bundles, devmode, ai)
- Debugging widget layout, CSS, or async behaviour
- Wiring new actions, keybindings, or Command Palette entries
- Working with bootc image refs, channel switching, or rollback

## When NOT to Use

- Pure AI stack work (GPU detection, quadlet deploy) → also load `docs/skills/ai-stacks.md`
- Human gate decisions → `docs/skills/human-gates.md`

## Quick start

```bash
cd /var/home/jorge/src/bluefinctl
pip install -e ".[dev]"          # editable install
bctl                             # launch TUI (short alias)
ghostty -e bctl &                # detached Ghostty window
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

| Key | Screen | Core module | Notes |
|-----|--------|-------------|-------|
| 1 | `screens/system.py` | `core/system.py` | 2-col; Release Stream switch; Rollback calendar; AdwButtonsRow quick actions |
| 2 | `screens/updates.py` | `core/updates.py` | Full-width image banner; radio schedule; staged-update alert; OpsBar footer |
| 3 | `screens/devmode.py` | `core/devmode.py` + `core/bundles.py` | 3 tabs: Kits/Tools/Environments; devmode toggle at top; per-package install |
| 4 | `screens/ai.py` | `core/ai.py` | 2 tabs: Stacks/Tools; GPU detection; bundled quadlet catalog |

Navigation items: **System · Updates · Developer · AI** (number keys 1–4).  
Toolkit is merged into Developer Mode (tab 3 → Kits tab).

## ADW widget library — `widgets/adw.py`

All screens use GNOME HIG-compliant widgets. **Never use raw `Static` + borders for layout.**

```python
from bluefinctl.widgets.adw import (
    AdwPreferencesGroup,  # bordered group: title ABOVE box, rows inside
    AdwActionRow,         # title+subtitle left, trailing widget right
    AdwSwitchRow,         # [✓]/[ ] toggle at height 1; subtitle supported
    AdwComboRow,          # cycling value label, fires AdwComboRow.Changed
    AdwButtonRow,         # full-width text row; subtitle supported; fires AdwButtonRow.Pressed
    AdwButtonsRow,        # real Textual Buttons side-by-side (accent-coloured)
    AdwPropertyRow,       # read-only key: value at height 1
    AdwExpanderRow,       # collapsible row
)
```

### Two-column layout

```python
with Horizontal(classes="adw-cols"):
    with Vertical(classes="adw-col"):   # left
        yield AdwPreferencesGroup(...)
    with Vertical(classes="adw-col"):   # right
        yield AdwPreferencesGroup(...)
```

### Action buttons

```python
# Primary actions — real Textual Button widgets with accent colour
yield AdwButtonsRow(
    Button("Update Now", variant="primary", id="btn-update"),
    Button("Check for Updates",              id="btn-check"),
)
# Handle via on_button_pressed

# Suggestion rows with optional subtitle (2-line when subtitle present)
yield AdwButtonRow(
    "Roll Back to Previous Build",
    subtitle="Requires reboot to apply",
    variant="destructive",
    id="btn-rollback",
)
# Handle via on_adw_button_row_pressed
```

## Content area convention

```python
def compose(self) -> ComposeResult:
    yield ViewSwitcher("myscreen")
    with ScrollableContainer(id="adw-content"):
        with Horizontal(classes="adw-cols"):
            with Vertical(classes="adw-col"):
                yield AdwPreferencesGroup(...)
            with Vertical(classes="adw-col"):
                yield AdwPreferencesGroup(...)
    yield OpsBar()   # always LAST — dock: bottom
```

## OpsBar — persistent bottom bar

```python
from bluefinctl.widgets.ops_bar import OpsBar

self.query_one(OpsBar).set_idle("✓  Up to date")
self.query_one(OpsBar).set_running("Updating…", stage=1)
self.query_one(OpsBar).set_complete("✓  Done")
self.query_one(OpsBar).set_confirm("Roll back?", "rollback")

# Confirm/cancel wired via on_button_pressed:
def on_button_pressed(self, event: Button.Pressed) -> None:
    if event.button.id == "btn-op-confirm":
        op = self.query_one(OpsBar).pending_op   # "rollback", etc.
    elif event.button.id == "btn-op-cancel":
        self.query_one(OpsBar).set_idle("Ready")
```

## @work — the correct pattern for async actions

**`push_screen_wait` requires a worker context.** In Textual 1.x, async action methods called via keybindings do NOT automatically run in a worker — `get_current_worker()` raises `NoActiveWorker`.

**The fix:** `@work(exclusive=True)` on every async method that calls `push_screen_wait`.

```python
from textual import work

@work(exclusive=True)
async def action_toggle_devmode(self, desired: bool | None = None) -> None:
    confirmed = await self.app.push_screen_wait(ConfirmModal(...))
    ...

# Call sites — plain call, NO run_worker wrapper:
def on_button_pressed(self, event: Button.Pressed) -> None:
    self.action_toggle_devmode()   # ✓ correct

def on_adw_switch_row_changed(self, event: AdwSwitchRow.Changed) -> None:
    self.action_toggle_devmode(event.value)   # ✓ correct
```

**Never do this:**
```python
self.run_worker(self.action_toggle_devmode())  # ✗ wrong when method is @work
```

This was fixed twice in this codebase. Any async method that calls `push_screen_wait` must be `@work`.

## core/system.py — SystemInfo

```python
from bluefinctl.core.system import SystemInfo, get_system_info, get_image_compression

info = await get_system_info()
info.image_name       # "dakota"
info.image_tag        # "latest" or "testing"
info.image_ref        # "ostree-image-signed:docker://ghcr.io/projectbluefin/dakota"
info.clean_image_ref  # "ghcr.io/projectbluefin/dakota"  (no transport prefix, NO tag)
info.full_clean_ref   # "ghcr.io/projectbluefin/dakota:latest"  ← use this for display
info.image_signed     # True when ref starts with "ostree-image-signed:"
info.image_staged     # True when bootc status shows a staged update

# Compression (network call — always run as background worker):
comp = await get_image_compression(info.full_clean_ref)
# Returns: "zstd:chunked", "zstd", "gzip", or "unknown"
```

**Critical:** `image_ref` from `/usr/share/ublue-os/image-info.json` has **no tag** — tag is in `image_tag`. Always use `full_clean_ref` for display and user-facing strings.

## Channel switching — correct bootc target

```python
info = await get_system_info()
base   = info.clean_image_ref   # "ghcr.io/projectbluefin/dakota"  (NO tag)
target = f"{base}:testing"      # "ghcr.io/projectbluefin/dakota:testing"
# Both :latest and :testing verified to exist on ghcr.io
proc = await asyncio.create_subprocess_exec("pkexec", "bootc", "switch", target, ...)
```

## _CheckToggle — compact checkbox widget

Textual's built-in `Switch` uses `border: tall` forcing 3 rows. Every `AdwSwitchRow` uses `_CheckToggle` instead — renders `[✓]`/`[ ]` at exactly `height: 1` (bumps to `height: 2` when subtitle is present). `set_value()` never fires `Changed`. This has been fixed twice — do not regress by importing `Switch`.

## pkexec patterns

One pkexec prompt per logical operation — batch multiple systemctl calls:

```python
# GOOD
script = "systemctl unmask uupd.timer && systemctl enable --now uupd.timer"
proc = await asyncio.create_subprocess_exec("pkexec", "bash", "-c", script, ...)

# BAD — two auth prompts
proc1 = await asyncio.create_subprocess_exec("pkexec", "systemctl", "unmask", ...)
proc2 = await asyncio.create_subprocess_exec("pkexec", "systemctl", "enable", ...)
```

## Red Flags

- `from textual.widgets import Switch` in any file — should be `_CheckToggle`
- `self.run_worker(self.action_something())` on a `@work`-decorated method
- `async def action_*` that calls `push_screen_wait` without `@work`
- `info.clean_image_ref` used as display string (missing tag)
- `height: auto` on `Horizontal` containers (expands to fill, not shrink)
- Hardcoded color variables (`$background`, `$surface`) in TCSS
- `asyncio.get_event_loop()` — use `get_running_loop()` inside async functions
- Rich `Console()` inside Textual screen/widget — use `self.notify()` instead

## Verification

After any change to screens, widgets, or core:

- [ ] `pytest` passing (43 tests)
- [ ] `ruff check src/ tests/` clean
- [ ] `mypy src/` clean (strict)
- [ ] `ghostty -e bctl &` launched and affected screen visible/functional
- [ ] No `Switch` imports remain in ADW widget code
- [ ] All new async actions that call `push_screen_wait` have `@work(exclusive=True)`
- [ ] Skill file updated in same PR if new pattern discovered

## Common pitfalls

See `docs/skills/textual-dev.md` for the full pitfall catalogue.
