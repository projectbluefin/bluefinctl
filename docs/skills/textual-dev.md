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

All screens use `layout: vertical`. The `ViewSwitcher` sits at the top, followed by a
`ScrollableContainer(id="adw-content")` that fills the remaining height.
The CSS for `#adw-content` is in `bluefin.tcss` (`overflow-y: auto; padding: 0 1`).

```python
from bluefinctl.screens._viewswitcher import ViewSwitcher

def compose(self) -> ComposeResult:
    yield ViewSwitcher("myscreen")
    with ScrollableContainer(id="adw-content"):
        yield AdwPreferencesGroup("Group 1", ...)
        yield AdwPreferencesGroup("Group 2", ...)
```

Screens that need a different content ID (DevMode, Toolkit, AI) define the CSS in `DEFAULT_CSS`
with `layout: vertical` on the screen and `padding: 0 1` on the content container.

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
confirmed = await self.app.push_screen_wait(ConfirmModal("Title", "Are you sure?"))
if confirmed: ...

value = await self.app.push_screen_wait(
    InputModal("Add Package", "Package name", placeholder="e.g. htop")
)
if value is not None: ...

rc = await self.app.push_screen_wait(
    OperationLogModal("Install Bundle", ["brew", "bundle", "install", "--file=..."])
)
if rc == 0: ...
```

`OperationLogModal` disables Close until the process exits and never swallows errors.

---

## Programmatic Widget State

Setting Switch values from a worker fires `Changed` events. A `_loading` guard is defeated by async event ordering. Use `prevent()` instead:

```python
with self.prevent(Switch.Changed):
    self.query_one("#layer-os", Switch).value = os_on

# For AdwSwitchRow / AdwComboRow use their typed set_value() which calls prevent() internally:
self.query_one("#layer-os", AdwSwitchRow).set_value(True)
self.query_one("#strategy-row", AdwComboRow).set_value("Automatic")
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
```

`stdout=DEVNULL` is mandatory. pkexec auth dialog appears in a separate GTK window — do not add timeouts.

---

## OSC Progress and Terminal Title

Always write to `/dev/tty` — NOT `sys.stdout` (Textual owns stdout):

```python
from bluefinctl.util.osc import osc_progress, osc_progress_clear, osc_progress_indeterminate, set_terminal_title

set_terminal_title("Bluefin Control Center")  # called on app mount
osc_progress_indeterminate()   # pulsing
osc_progress(50)               # 0-100
osc_progress_clear()           # remove indicator
```

`OperationLogModal` / `OperationModal` call the progress helpers automatically.

---

## Textual CSS Constraints

- `vh`/`vw` units are **not supported** — use fixed row counts (`max-height: 30`)
- `Static` does **not scroll** — wrap in `ScrollableContainer`
- `overflow-y: auto` on `Static` is silently ignored
- **Never hardcode `$background`, `$surface`, etc. in TCSS** — they come from the active Theme. Hardcoding breaks dark/light switching.
- **ADW row heights are compact**: `AdwPropertyRow` and `AdwButtonRow` are `height: 1`; action/switch/combo rows are `min-height: 2` with no inner padding. Do not restore `padding: 1 0` on row content — groups would overflow one full screen per group.

---

## Dark / Light Theme

`theme/accent.py` provides:
- `get_color_scheme() → "dark" | "light"` — reads `org.gnome.desktop.interface color-scheme`
- `get_accent_color() → str` — reads `org.gnome.desktop.interface accent-color`
- `build_theme(scheme, accent_name) → Theme` — builds a Textual Theme with the correct GNOME palette

Both use `@lru_cache` — call `.cache_clear()` before re-reading after a live change.

`app.py` starts `_watch_system_theme()` which streams `gsettings monitor org.gnome.desktop.interface` and calls `_apply_system_theme()` on any `color-scheme` or `accent-color` line.

Monkeypatch targets must be in `bluefinctl.app` namespace:
```python
monkeypatch.setattr("bluefinctl.app.get_color_scheme", lambda: "light")
monkeypatch.setattr("bluefinctl.app.get_accent_color", lambda: "blue")
```

---

## Tree Nodes

Always store structured data on tree leaf nodes. Label text is fragile to parse:

```python
pod_node.add_leaf(f"  {icon} {name}  ({image})  [{state}]", data=name)
ct_name = node.data  # in action handlers — read from data, not label
```

---

## asyncio in Async Functions

Use `asyncio.get_running_loop()` (not `get_event_loop()`) inside async functions. `get_event_loop()` is deprecated in Python 3.10+ when a loop is already running.

---

## Common Pitfalls

| Pitfall | Fix |
|---|---|
| **Worker race** | Always init mutable attrs in `__init__`, not just at end of a worker |
| **Console() in core** | Never use `rich.Console` inside Textual — use `self.notify()` or `OperationLogModal` |
| **Tree refresh** | Call `tree.root.remove_children()` then re-run the load worker with `exclusive=True` |
| **bootc switch** | Takes a positional target: `["pkexec", "bootc", "switch", ref]` — not `--target` |
| **ADW `id` arg** | `A002` (shadowing builtin `id`) is suppressed in `pyproject.toml` — it's standard Textual API |
| **Hardcoded CSS vars** | Never define `$background`/`$surface`/etc. in TCSS — they must come from the Theme object |
| **lru_cache + live updates** | Call `.cache_clear()` before re-reading a changed gsettings value |
| **Tab widget `_name`** | Textual's `Widget` uses `_name` internally (`str | None`). Use a different attribute name (e.g. `_tab_name`) in subclasses to avoid mypy errors |
