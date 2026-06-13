---
name: textual-dev
description: "Textual/Python patterns, pitfalls, and conventions specific to bluefinctl. Use when writing screens, widgets, modals, or core modules — covers the non-obvious Textual behaviors that have already been discovered the hard way."
metadata:
  type: reference
---

# Textual Development Patterns

Conventions and pitfalls specific to bluefinctl. The Copilot CLI skill (`.agents/skills/bluefinctl-dev/`) covers the full workflow; this file records discovered workarounds and non-obvious requirements.

## Contents
- [ADW Widget Library](#adw-widget-library)
- [Core / Screen Separation](#core--screen-separation)
- [Modals](#modals)
- [Programmatic Widget State](#programmatic-widget-state)
- [Writing to /etc/](#writing-to-etc)
- [OSC 9;4 Progress](#osc-94-progress)
- [Textual CSS Constraints](#textual-css-constraints)
- [Tree Nodes](#tree-nodes)
- [asyncio in Async Functions](#asyncio-in-async-functions)
- [Dark / Light Theme](#dark--light-theme)
- [Common Pitfalls](#common-pitfalls)

---

## ADW Widget Library

All screens use GNOME HIG-compliant widgets from `widgets/adw.py`. Never build raw card
layouts with `Static` + borders — use these instead.

### Widget reference

| Widget | HIG equivalent | Usage |
|---|---|---|
| `AdwPreferencesGroup(title, *rows)` | AdwPreferencesGroup | Bordered group with muted heading above |
| `AdwActionRow(title, subtitle, trailing)` | AdwActionRow | Generic row with trailing widget |
| `AdwSwitchRow(title, subtitle, value, id=)` | AdwSwitchRow | Toggle row — fires `AdwSwitchRow.Changed` |
| `AdwComboRow(title, subtitle, choices, value)` | AdwComboRow | Cycling value row — fires `AdwComboRow.Changed` |
| `AdwButtonRow(title, variant)` | AdwButtonRow | Full-width action row — fires `AdwButtonRow.Pressed` |
| `AdwPropertyRow(key, value)` | Property row | Read-only key: value display |
| `AdwExpanderRow(title, subtitle)` | AdwExpanderRow | Collapsible row with child rows |

### Usage pattern

```python
from bluefinctl.widgets.adw import (
    AdwButtonRow, AdwPreferencesGroup, AdwPropertyRow, AdwSwitchRow
)

# In screen compose():
yield AdwPreferencesGroup(
    "Update Layers",
    AdwSwitchRow("OS Image", subtitle="Include bootc image updates", id="layer-os"),
    AdwSwitchRow("Flatpaks", subtitle="Include Flatpak app updates", id="layer-flatpak"),
)
yield AdwPreferencesGroup(
    "Actions",
    AdwButtonRow("Update Now", variant="primary", id="btn-update"),
)

# Event handlers:
def on_adw_switch_row_changed(self, event: AdwSwitchRow.Changed) -> None:
    if event.row.id == "layer-os":
        ...  # event.value is True/False

def on_adw_button_row_pressed(self, event: AdwButtonRow.Pressed) -> None:
    if event.row.id == "btn-update":
        self.run_worker(self._do_update())

def on_adw_combo_row_changed(self, event: AdwComboRow.Changed) -> None:
    if event.row.id == "strategy-row":
        ...  # event.value is the selected string
```

### Setting values programmatically

```python
# Switch — use set_value() to avoid firing Changed
self.query_one("#layer-os", AdwSwitchRow).set_value(True)

# Combo — use set_value() to avoid firing Changed
self.query_one("#strategy-row", AdwComboRow).set_value("Automatic")

# Property — always use update_value()
self.query_one("#channel-info", AdwPropertyRow).update_value("stable")
```

### Content area — always use #adw-content

All screens use `ScrollableContainer(id="adw-content")` as the main content area.
The CSS for `#adw-content` is defined in `bluefin.tcss` with `overflow-y: auto; padding: 1 2`.

```python
def compose(self) -> ComposeResult:
    yield Sidebar(active="myscreen")
    with ScrollableContainer(id="adw-content"):
        yield AdwPreferencesGroup("Group 1", ...)
        yield AdwPreferencesGroup("Group 2", ...)
```

### HIG rules to follow

- **Heading above box**: `AdwPreferencesGroup` title is rendered above the border, not inside
- **Action widget on right**: controls go on the RIGHT side of every row
- **One control per row** (two is the HIG maximum)
- **Heading uses sentence case, muted color** — handled automatically by widget CSS
- **Destructive actions**: `AdwButtonRow("Delete…", variant="destructive")`
- **Primary suggested action**: `AdwButtonRow("Apply", variant="primary")`

---

## Core / Screen Separation

All subprocess calls, file I/O, and system state live in `core/`. Screens only call core functions and present results. Never import Textual inside `core/`.

Every operation has two paths:
1. **Headless CLI** — `bluefinctl <subcommand>` (via `cli.py` / Typer)
2. **TUI interactive** — same core logic, presented in Textual screens

---

## Modals

Always use `push_screen_wait()` from `screens/_modals.py` for destructive or long-running actions:

```python
# Confirmation dialog
confirmed = await self.app.push_screen_wait(ConfirmModal("Title", "Are you sure?"))
if confirmed: ...

# Text input
value = await self.app.push_screen_wait(
    InputModal("Add Package", "Package name", placeholder="e.g. htop")
)
if value is not None: ...

# Streaming subprocess (shows live output, blocks until done)
rc = await self.app.push_screen_wait(
    OperationLogModal("Install Bundle", ["brew", "bundle", "install", "--file=..."])
)
if rc == 0: ...
```

`OperationLogModal` disables Close until the process exits and never swallows errors.

---

## Programmatic Widget State

Setting Switch or RadioButton values from a worker fires `Changed` events. A `_loading` guard is defeated by async event ordering — the flag clears before the event drains. Use `prevent()` instead:

```python
with self.prevent(Switch.Changed):
    self.query_one("#layer-os", Switch).value = os_on
    self.query_one("#layer-flatpak", Switch).value = flatpak_on

with self.prevent(RadioSet.Changed):
    buttons[idx].value = True
```

**`RadioSet.action_select_button()` does not exist in Textual 1.0.** Set `RadioButton.value = True` directly inside `prevent()`.

---

## Writing to /etc/

Files under `/etc/` require elevated privileges. Pipe JSON through `pkexec tee`:

```python
proc = await asyncio.create_subprocess_exec(
    "pkexec", "tee", "/etc/uupd/config.json",
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.DEVNULL,  # REQUIRED — omitting hangs the process
    stderr=asyncio.subprocess.DEVNULL,
)
await proc.communicate(json.dumps(cfg, indent=2).encode())
if proc.returncode != 0:
    raise RuntimeError(f"pkexec tee failed (exit {proc.returncode})")
```

`stdout=DEVNULL` is mandatory — omitting it leaves the process hanging for a reader.

pkexec auth dialog appears in a separate GTK window over Ghostty — this is expected. Do not add a timeout to pkexec calls.

---

## OSC 9;4 Progress

Always write to `/dev/tty` — NOT `sys.stdout` (Textual owns stdout):

```python
from bluefinctl.util.osc import osc_progress, osc_progress_clear, osc_progress_indeterminate
osc_progress_indeterminate()   # pulsing (unknown duration)
osc_progress(50)               # 0-100
osc_progress_clear()           # remove indicator
```

`LogView` and `OperationLogModal` call these automatically.

---

## Textual CSS Constraints

- `vh`/`vw` units are **not supported** — use fixed terminal row counts (`max-height: 45`)
- `Static` does **not scroll** — wrap in `ScrollableContainer` when content may overflow
- `overflow-y: auto` on `Static` is silently ignored
- **Never hardcode `$background`, `$surface`, etc. in TCSS** — these come from the active
  `Theme` object. Hardcoding them overrides the theme and breaks dark/light switching.

---

## Dark / Light Theme

The app follows the GNOME system theme live via `gsettings monitor`.

### How it works

`theme/accent.py` provides:
- `get_color_scheme() → "dark" | "light"` — reads `org.gnome.desktop.interface color-scheme`
- `get_accent_color() → str` — reads `org.gnome.desktop.interface accent-color`
- `build_theme(scheme, accent_name) → Theme` — builds a Textual Theme with the correct
  GNOME palette (dark: Dark 4/3/2; light: Light 2/1/3)

Both functions use `@lru_cache` — call `.cache_clear()` before re-reading after a live change.

`app.py` starts a background worker `_watch_system_theme()` that streams
`gsettings monitor org.gnome.desktop.interface` and calls `_apply_system_theme()`
on any `color-scheme` or `accent-color` line.

### GNOME palette reference

| Role | Dark hex | Light hex |
|---|---|---|
| background | `#241f31` (Dark 4) | `#f6f5f4` (Light 2) |
| surface | `#3d3846` (Dark 3) | `#ffffff` (Light 1) |
| panel | `#5e5c64` (Dark 2) | `#deddda` (Light 3) |
| success | `#33d17a` (Green 3) | `#26a269` (Green 5) |
| warning | `#e5a50a` (Yellow 5) | `#c64600` (Orange 5) |
| error | `#ed333b` (Red 2) | `#c01c28` (Red 4) |

Accent uses Blue 3 (`#3584e4`) in dark mode, Blue 4 (`#1c71d8`) in light mode for contrast.

### Testing theme switching

Monkeypatch targets must be in `bluefinctl.app` namespace (where the functions are imported),
not `bluefinctl.theme.accent`:

```python
monkeypatch.setattr("bluefinctl.app.get_color_scheme", lambda: "light")
monkeypatch.setattr("bluefinctl.app.get_accent_color", lambda: "blue")
```

---

## Tree Nodes

Always store structured data on tree leaf nodes. Label text is fragile to parse:

```python
# Store name directly on the node
pod_node.add_leaf(f"  {icon} {name}  ({image})  [{state}]", data=name)

# In action handlers — read from data, not label
ct_name = node.data
```

---

## asyncio in Async Functions

Use `asyncio.get_running_loop()` (not `get_event_loop()`) inside async functions. `get_event_loop()` is deprecated in Python 3.10+ when a loop is already running.

---

## Common Pitfalls

| Pitfall | Fix |
|---|---|
| **Worker race** | Always init mutable attrs in `__init__`, not just at end of a worker |
| **Console() in core** | Never use `rich.Console` inside Textual — output is hidden. Use `self.notify()` for toasts or `OperationLogModal` for streaming |
| **Tree refresh** | Call `tree.root.remove_children()` then re-run the load worker with `exclusive=True` |
| **bootc switch** | Takes a positional target: `["pkexec", "bootc", "switch", ref]` — not `--target` |
| **Switch/RadioSet state** | Set programmatically with `value = True/False` inside `prevent()` — see section above |
| **Hardcoded CSS vars** | Never define `$background`, `$surface`, etc. in TCSS — they must come from the Theme object or dark/light switching breaks |
| **lru_cache + live updates** | Functions decorated with `@lru_cache` must have `.cache_clear()` called before re-reading a changed gsettings value |


---

## Core / Screen Separation

All subprocess calls, file I/O, and system state live in `core/`. Screens only call core functions and present results. Never import Textual inside `core/`.

Every operation has two paths:
1. **Headless CLI** — `bluefinctl <subcommand>` (via `cli.py` / Typer)
2. **TUI interactive** — same core logic, presented in Textual screens

---

## Modals

Always use `push_screen_wait()` from `screens/_modals.py` for destructive or long-running actions:

```python
# Confirmation dialog
confirmed = await self.app.push_screen_wait(ConfirmModal("Title", "Are you sure?"))
if confirmed: ...

# Text input
value = await self.app.push_screen_wait(
    InputModal("Add Package", "Package name", placeholder="e.g. htop")
)
if value is not None: ...

# Streaming subprocess (shows live output, blocks until done)
rc = await self.app.push_screen_wait(
    OperationLogModal("Install Bundle", ["brew", "bundle", "install", "--file=..."])
)
if rc == 0: ...
```

`OperationLogModal` disables Close until the process exits and never swallows errors.

---

## Programmatic Widget State

Setting Switch or RadioButton values from a worker fires `Changed` events. A `_loading` guard is defeated by async event ordering — the flag clears before the event drains. Use `prevent()` instead:

```python
with self.prevent(Switch.Changed):
    self.query_one("#layer-os", Switch).value = os_on
    self.query_one("#layer-flatpak", Switch).value = flatpak_on

with self.prevent(RadioSet.Changed):
    buttons[idx].value = True
```

**`RadioSet.action_select_button()` does not exist in Textual 1.0.** Set `RadioButton.value = True` directly inside `prevent()`.

---

## Writing to /etc/

Files under `/etc/` require elevated privileges. Pipe JSON through `pkexec tee`:

```python
proc = await asyncio.create_subprocess_exec(
    "pkexec", "tee", "/etc/uupd/config.json",
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.DEVNULL,  # REQUIRED — omitting hangs the process
    stderr=asyncio.subprocess.DEVNULL,
)
await proc.communicate(json.dumps(cfg, indent=2).encode())
if proc.returncode != 0:
    raise RuntimeError(f"pkexec tee failed (exit {proc.returncode})")
```

`stdout=DEVNULL` is mandatory — omitting it leaves the process hanging for a reader.

pkexec auth dialog appears in a separate GTK window over Ghostty — this is expected. Do not add a timeout to pkexec calls.

---

## OSC 9;4 Progress

Always write to `/dev/tty` — NOT `sys.stdout` (Textual owns stdout):

```python
from bluefinctl.util.osc import osc_progress, osc_progress_clear, osc_progress_indeterminate
osc_progress_indeterminate()   # pulsing (unknown duration)
osc_progress(50)               # 0-100
osc_progress_clear()           # remove indicator
```

`LogView` and `OperationLogModal` call these automatically.

---

## Textual CSS Constraints

- `vh`/`vw` units are **not supported** — use fixed terminal row counts (`max-height: 45`)
- `Static` does **not scroll** — wrap in `ScrollableContainer` when content may overflow
- `overflow-y: auto` on `Static` is silently ignored

---

## Tree Nodes

Always store structured data on tree leaf nodes. Label text is fragile to parse:

```python
# Store name directly on the node
pod_node.add_leaf(f"  {icon} {name}  ({image})  [{state}]", data=name)

# In action handlers — read from data, not label
ct_name = node.data
```

---

## asyncio in Async Functions

Use `asyncio.get_running_loop()` (not `get_event_loop()`) inside async functions. `get_event_loop()` is deprecated in Python 3.10+ when a loop is already running.

---

## Common Pitfalls

| Pitfall | Fix |
|---|---|
| **Worker race** | Always init mutable attrs in `__init__`, not just at end of a worker |
| **Console() in core** | Never use `rich.Console` inside Textual — output is hidden. Use `self.notify()` for toasts or `OperationLogModal` for streaming |
| **Tree refresh** | Call `tree.root.remove_children()` then re-run the load worker with `exclusive=True` |
| **bootc switch** | Takes a positional target: `["pkexec", "bootc", "switch", ref]` — not `--target` |
| **Switch/RadioSet state** | Set programmatically with `value = True/False` inside `prevent()` — see section above |
