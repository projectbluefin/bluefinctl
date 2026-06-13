---
name: bluefinctl-dev
description: Development patterns and conventions for the bluefinctl Textual TUI project. Use when working in /var/home/jorge/src/bluefinctl, adding screens, wiring actions, creating modals, or modifying the theme/bundle system.
---

# bluefinctl Development

## Quick start

```bash
cd /var/home/jorge/src/bluefinctl
pip install -e ".[dev]"          # editable install
ghostty -e bluefinctl &          # launch TUI
ghostty -e textual run --dev src/bluefinctl/app.py &  # hot-reload CSS
```

## Architecture

```
core/          Business logic only — NO Textual imports, fully testable
screens/       One Screen subclass per panel, thin presentation layer
widgets/       adw.py (HIG widget library) + operation_modal.py + log_view.py
theme/         accent.py (gsettings reader + theme builder) + bluefin.tcss
util/          OSC escape sequences, Ghostty detection, terminal launcher
```

**Rule:** All subprocess calls, file I/O, and system state live in `core/`. Screens only call core functions and present results.

## Five screens

| Key | Screen file | Core module | Notes |
|-----|-------------|-------------|-------|
| 1 | screens/system.py | core/system.py | AdwPropertyRow cards, AdwButtonRow actions |
| 2 | screens/updates.py | core/updates.py | AdwSwitchRow / AdwComboRow / AdwButtonRow; snooze buttons; ChangelogViewer |
| 3 | screens/toolkit.py | core/bundles.py | ListView + scrollable detail pane |
| 4 | screens/devmode.py | core/devmode.py | 3 tabs: Overview/Tools/Environments; Lima wizard |
| 5 | screens/ai.py | core/ai.py | 2 tabs: Stacks/Tools |

All screens use `layout: vertical`. `ViewSwitcher` sits at the top; content fills the rest.

## ADW widget library — `widgets/adw.py`

All screens use GNOME HIG-compliant widgets. **Never use raw `Static` + borders for layout.**

```python
from bluefinctl.widgets.adw import (
    AdwPreferencesGroup,  # bordered group: title ABOVE box, rows inside
    AdwActionRow,         # title+subtitle left, trailing widget right
    AdwSwitchRow,         # fires AdwSwitchRow.Changed(row, value)
    AdwComboRow,          # cycling value label, fires AdwComboRow.Changed
    AdwButtonRow,         # full-width row, fires AdwButtonRow.Pressed
    AdwPropertyRow,       # read-only key: value display
    AdwExpanderRow,       # collapsible row
)

# Typical screen compose():
yield AdwPreferencesGroup(
    "Update Layers",
    AdwSwitchRow("OS Image", subtitle="Include bootc image updates", id="layer-os"),
    AdwSwitchRow("Flatpaks", subtitle="Include Flatpak app updates", id="layer-flatpak"),
)
yield AdwPreferencesGroup(
    "Actions",
    AdwButtonRow("Update Now", variant="primary", id="btn-update"),
)

# Screen event handlers:
def on_adw_switch_row_changed(self, event: AdwSwitchRow.Changed) -> None:
    if event.row.id == "layer-os":
        ...  # event.value is bool

def on_adw_button_row_pressed(self, event: AdwButtonRow.Pressed) -> None:
    if event.row.id == "btn-update":
        self.run_worker(self._do_update())

# Programmatic value setting — never triggers Changed events:
self.query_one("#layer-os", AdwSwitchRow).set_value(True)
self.query_one("#strategy", AdwComboRow).set_value("Automatic")
self.query_one("#channel", AdwPropertyRow).update_value("stable")
```

## Content area convention

Every screen uses `ScrollableContainer(id="adw-content")` as the scrollable main area:

```python
def compose(self) -> ComposeResult:
    yield Sidebar(active="myscreen")
    with ScrollableContainer(id="adw-content"):
        yield AdwPreferencesGroup("Group 1", ...)
        yield AdwPreferencesGroup("Group 2", ...)
```

`#adw-content` CSS is in `bluefin.tcss` (width 1fr, height 1fr, overflow-y auto, padding 1 2).

## Theme system — live dark/light

The app follows GNOME `color-scheme` live via `gsettings monitor`:

```python
from bluefinctl.theme.accent import build_theme, get_color_scheme, get_accent_color

# Build theme for current system settings:
theme = build_theme(get_color_scheme(), get_accent_color())
# → "bluefin-dark" or "bluefin-light", exact GNOME HIG palette
```

`app.py` starts `_watch_system_theme()` which hot-switches `app.theme` on any
`color-scheme` or `accent-color` gsettings change.

**Critical:** Never hardcode `$background`, `$surface`, etc. in TCSS. They resolve from
the active Theme. Hardcoding breaks dark/light switching.

## Unified progress system

Every operation uses `OperationModal` (widgets/operation_modal.py):

```python
from bluefinctl.core.progress import BrewInstallParser
from bluefinctl.widgets.operation_modal import OperationModal

rc = await self.app.push_screen_wait(
    OperationModal(
        "Installing Kit",
        command=["brew", "bundle", "install", "--file=..."],
        parser=BrewInstallParser(total_packages=12),
    )
)

# Async generator workflow
async def my_steps():
    yield ProgressUpdate(percent=0, step=1, total_steps=3, message="Step 1")
    yield ProgressUpdate(percent=100, message="Done")

rc = await self.app.push_screen_wait(
    OperationModal("My Operation", steps=my_steps())
)
```

## Reusable modals (screens/_modals.py)

```python
confirmed = await self.app.push_screen_wait(ConfirmModal("Title", "Are you sure?"))
value = await self.app.push_screen_wait(InputModal("Add", "Name", placeholder="e.g. htop"))
rc = await self.app.push_screen_wait(OperationLogModal("Install", ["brew", "install", "htop"]))
```

## Adding a new screen

1. Create `screens/myscreen.py` with `MyScreen(Screen[None])`
2. `DEFAULT_CSS = "MyScreen { layout: vertical; }"`
3. `compose()` yields `ViewSwitcher("myscreen")` then `ScrollableContainer(id="adw-content")`
4. Inside the container, yield `AdwPreferencesGroup(...)` groups
5. Register in `app.py` `on_mount`
6. Add to `NAV_ITEMS` in `screens/_viewswitcher.py`
7. Add a `Binding` in `app.py`

## Common pitfalls

- **Worker race**: always init mutable attrs in `__init__`, not just at end of worker
- **Console() in core**: never use rich Console inside Textual — use `self.notify()`
- **pkexec hangs**: polkit auth dialog appears in a separate GTK window — don't add timeouts
- **bootc switch**: positional target — `["pkexec", "bootc", "switch", ref]` not `--target`
- **Textual CSS**: `vh`/`vw` NOT supported; `Static` does NOT scroll (wrap in ScrollableContainer)
- **asyncio**: use `get_running_loop()` not `get_event_loop()` in async functions
- **CSS color vars**: never define `$background`/`$surface`/etc. in TCSS — they break theme switching
- **lru_cache + live updates**: call `.cache_clear()` before re-reading a changed gsettings value
- **ADW `id` arg**: `A002` (shadowing builtin) is suppressed in `pyproject.toml` — it's standard Textual API
