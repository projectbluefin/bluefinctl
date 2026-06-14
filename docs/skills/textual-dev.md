---
name: textual-dev
description: >-
  Textual/Python patterns, pitfalls, and conventions specific to bluefinctl.
  Use when writing screens, widgets, modals, or core modules — covers the
  non-obvious Textual behaviors discovered the hard way: @work for
  push_screen_wait, _CheckToggle replacing Switch, height:auto Horizontal
  expansion, pkexec stdout, OSC progress, dark/light theming, and more.
metadata:
  type: reference
  context7-sources:
    - /textualize/textual
---

# Textual Development Patterns

Conventions and pitfalls specific to bluefinctl. The dev skill (`.agents/skills/bluefinctl-dev/`) covers the full workflow; this file records non-obvious requirements and discovered workarounds. **Read before modifying any screen or widget.**

## Contents

- [ADW Widget Library](#adw-widget-library)
- [Workers and push_screen_wait](#workers-and-push_screen_wait)
- [Core / Screen Separation](#core--screen-separation)
- [Modals](#modals)
- [Programmatic Widget State](#programmatic-widget-state)
- [Writing to /etc/](#writing-to-etc)
- [OSC Progress and Terminal Title](#osc-progress-and-terminal-title)
- [Textual CSS Constraints](#textual-css-constraints)
- [Dark / Light Theme](#dark--light-theme)
- [asyncio in Async Functions](#asyncio-in-async-functions)
- [Common Pitfalls](#common-pitfalls)

## ADW Widget Library

All screens use GNOME HIG-compliant widgets from `widgets/adw.py`. Never build raw card layouts with `Static` + borders — use these instead.

### Widget reference

| Widget | Height | Notes |
|--------|--------|-------|
| `AdwPreferencesGroup` | auto | Title above box; rows inside |
| `AdwPropertyRow` | 1 | Read-only key: value |
| `AdwSwitchRow` | 1 (2 with subtitle) | `_CheckToggle` trailing; `set_value()` never fires `Changed` |
| `AdwButtonRow` | auto | Suggestion row with subtitle support; fires `Pressed` |
| `AdwButtonsRow` | 3 | Real Textual `Button` objects side-by-side |
| `AdwComboRow` | 2 | Cycling value; fires `Changed` |
| `AdwExpanderRow` | 2 | Collapsible |

### _CheckToggle replaces Switch

**Textual's `Switch` uses `border: tall` which forces 3 rows.** This inflates every AdwSwitchRow to 3+ rows and can fill an entire terminal on a large display. `_CheckToggle` renders `[✓]`/`[ ]` at exactly `height: 1`.

```python
# ✓ Correct — already in adw.py
# AdwSwitchRow uses _CheckToggle internally

# ✗ Wrong — never import Switch for row widgets
from textual.widgets import Switch
```

`set_value()` on `AdwSwitchRow` directly sets `_CheckToggle._value` without emitting `Changed`. This allows loading state from the system without triggering the change handler.

### Usage pattern

```python
yield AdwPreferencesGroup(
    "Update Layers",
    AdwSwitchRow("OS Image", subtitle="Include bootc image updates", id="layer-os"),
    AdwSwitchRow("Flatpaks", subtitle="Include Flatpak app updates", id="layer-flatpak"),
    AdwButtonRow("Roll Back", subtitle="Requires reboot", variant="destructive", id="btn-rollback"),
    AdwButtonsRow(
        Button("Update Now", variant="primary", id="btn-update"),
        Button("Check for Updates", id="btn-check"),
    ),
)
```

### Setting values programmatically

```python
self.query_one("#layer-os", AdwSwitchRow).set_value(True)   # does NOT fire Changed
self.query_one("#strategy", AdwComboRow).set_value("Automatic")
self.query_one("#channel", AdwPropertyRow).update_value("stable")
```

### Content area — always use #adw-content

```python
def compose(self) -> ComposeResult:
    yield ViewSwitcher("myscreen")
    with ScrollableContainer(id="adw-content"):
        yield AdwPreferencesGroup(...)
    yield OpsBar()   # always LAST
```

`#adw-content` is styled in `bluefin.tcss`. OpsBar uses `dock: bottom` and must be the last child.

### HIG rules to follow

- Heading is ABOVE the boxed group (the `AdwPreferencesGroup` title), not inside it
- One control per row (max two per HIG)
- Row separators between items — `Rule(classes="adw-separator")` — not borders on each row
- Primary actions get `AdwButtonsRow` (real Buttons); suggestion actions get `AdwButtonRow`

## Workers and push_screen_wait

**`push_screen_wait` requires a Textual worker context.** In Textual 1.x, calling it outside a worker raises `NoActiveWorker`. Async action methods triggered by keybindings do NOT automatically run in a worker.

**Correct pattern: `@work(exclusive=True)` on every method that calls `push_screen_wait`.**

```python
from textual import work

@work(exclusive=True)
async def action_toggle_devmode(self) -> None:
    confirmed = await self.app.push_screen_wait(ConfirmModal(...))
    if confirmed:
        rc = await self.app.push_screen_wait(OperationLogModal(...))
```

When a method is `@work`-decorated, call it as a plain function — never wrap it in `run_worker()`:

```python
# ✓ Correct call sites
def on_button_pressed(self, event):
    self.action_toggle_devmode()

def on_adw_switch_row_changed(self, event):
    self.action_toggle_devmode(event.value)

# ✗ Wrong — double-wrapping a @work method
self.run_worker(self.action_toggle_devmode())
```

**`run_worker(coro)` is still correct** for plain async methods (no `push_screen_wait`) like `_load()`, `_load_compression()`.

This was fixed **twice** in this codebase. Any new async method that calls `push_screen_wait` must have `@work`.

## Core / Screen Separation

All subprocess calls, file I/O, and system state live in `core/`. Screens are presentation only.

```python
# ✓ core/system.py — pure async, no Textual imports
async def get_system_info() -> SystemInfo:
    proc = await asyncio.create_subprocess_exec("bootc", "status", "--json", ...)
    ...

# ✓ screens/system.py — calls core, updates widgets
async def _load_identity(self) -> None:
    info = await get_system_info()
    self.query_one("#sys-image", AdwPropertyRow).update_value(info.full_clean_ref)
```

## Modals

Reusable modals live in `screens/_modals.py`:

```python
from bluefinctl.screens._modals import ConfirmModal, OperationLogModal, HelpModal

# Confirmation
confirmed = await self.app.push_screen_wait(ConfirmModal("Title", "Body text"))

# Running an operation with live log output
rc = await self.app.push_screen_wait(
    OperationLogModal("Enable DevMode", ["pkexec", "bash", "-c", cmds])
)

# Unified progress with ProgressParser
from bluefinctl.widgets.operation_modal import OperationModal
rc = await self.app.push_screen_wait(
    OperationModal("Activating Kit", steps=activate_bundle_steps(slug))
)
```

All modal calls require `@work(exclusive=True)` on the calling method.

## Programmatic Widget State

Use `prevent()` to suppress events when setting state programmatically, or use `set_value()` which already suppresses:

```python
# AdwSwitchRow.set_value() suppresses Changed — just call it
self.query_one("#focus-switch", AdwSwitchRow).set_value(True)

# For other widgets where you need to prevent bubbling
with self.prevent(SomeWidget.Changed):
    widget.value = new_value
```

Do NOT use a `_loading: bool` flag to skip event handlers — async ordering defeats it. `prevent()` is synchronous and reliable.

## Writing to /etc/

Use `pkexec tee` with `stdout=DEVNULL` — omitting stdout leaves the process hanging for a reader:

```python
proc = await asyncio.create_subprocess_exec(
    "pkexec", "tee", "/etc/uupd/config.json",
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.DEVNULL,   # ← required, or process hangs
    stderr=asyncio.subprocess.DEVNULL,
)
await proc.communicate(json.dumps(cfg).encode())
```

## OSC Progress and Terminal Title

```python
from bluefinctl.util.osc import set_terminal_title, emit_progress

set_terminal_title("Bluefin Control Center")   # OSC 0
emit_progress(50)   # OSC 9;4 — progress in terminal tab/titlebar (Ghostty, Ptyxis, iTerm2)
emit_progress(-1)   # clear progress
```

`OperationModal` emits OSC 9;4 automatically during operations.

## Textual CSS Constraints

| Constraint | Detail |
|------------|--------|
| `vh`/`vw` units | **Not supported** — silently ignored. Use fixed row counts or `1fr`. |
| `height: auto` on `Horizontal` | Expands to fill parent, not shrink to content. Use explicit `height: N`. |
| `Static` | Does not scroll. Wrap in `ScrollableContainer` if content may overflow. |
| `font-family: monospace` | Not supported — terminals are already monospace; use color/style to distinguish code. |
| `$background`, `$surface` in TCSS | Do not define — breaks dark/light switching. Use only in Theme builder. |

## Dark / Light Theme

The app follows GNOME `color-scheme` live. Never hardcode palette colors in TCSS:

```python
# ✓ Use theme variables — they switch with GNOME color-scheme
color: $accent;
background: $surface;

# ✗ Hardcoding breaks dark/light switching
background: #1a1a2e;
```

`app.py` starts `_watch_system_theme()` which hot-switches `app.theme` on gsettings changes. Clear `lru_cache` before re-reading live gsettings values:

```python
get_color_scheme.cache_clear()
get_accent_color.cache_clear()
```

## asyncio in Async Functions

```python
# ✓ Correct in async context
loop = asyncio.get_running_loop()

# ✗ Deprecated in Python 3.10+ when a loop is already running
loop = asyncio.get_event_loop()
```

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| `Switch` widget in ADW rows — 3 rows tall | Use `_CheckToggle` (already in `AdwSwitchRow`) |
| `@work` method wrapped in `run_worker()` | Call `@work` methods directly; they start their own worker |
| `push_screen_wait` without `@work` | Add `@work(exclusive=True)` to the calling method |
| `info.clean_image_ref` shown to users (no tag) | Use `info.full_clean_ref` for display |
| `height: auto` on Horizontal fills terminal | Use `height: N` or `height: 1fr` |
| `Console()` in Textual screen/widget | Use `self.notify()` — Console writes to stdout and garbles TUI |
| pkexec hangs | The polkit dialog is a separate GTK window — don't add timeouts |
| `bootc switch --target ref` | Wrong — positional: `["pkexec", "bootc", "switch", ref]` |
| `asyncio.get_event_loop()` in async function | Use `asyncio.get_running_loop()` |
| Rich `[code]text[/code]` for monospace | Not a valid Rich tag. Use `[bold]` or color for code-like distinction |
| OpsBar not last in compose | `dock: bottom` only works when OpsBar is the last child |
