---
name: bluefinctl-dev
description: Development patterns and conventions for the bluefinctl Textual TUI project. Use when working in /var/home/jorge/src/bbrew, adding screens, wiring actions, creating modals, or modifying the theme/bundle system.
---

# bluefinctl Development

## Quick start

```bash
cd /var/home/jorge/src/bbrew
pip install -e ".[dev]"          # editable install
ghostty -e bluefinctl &          # launch TUI
ghostty -e textual run --dev src/bluefinctl/app.py &  # hot-reload CSS
```

## Architecture

```
core/          Business logic only — NO Textual imports, fully testable
screens/       One Screen subclass per panel, thin presentation layer
widgets/       Reusable Textual widgets (LogView, etc.)
theme/         GNOME accent color reader + bluefin.tcss
util/          OSC escape sequences, Ghostty detection
```

**Rule:** All subprocess calls, file I/O, and system state live in `core/`. Screens only call core functions and present results.

## Five panels

| Key | Screen file | Core module |
|-----|-------------|-------------|
| 1 | screens/system.py | core/system.py |
| 2 | screens/bundles.py | core/bundles.py |
| 3 | screens/packages.py | core/brew.py |
| 4 | screens/updates.py | core/updates.py |
| 5 | screens/containers.py | (podman subprocess) |

## Reusable modals (screens/_modals.py)

Use `push_screen_wait()` for every destructive or long-running action:

```python
# Confirmation
confirmed = await self.app.push_screen_wait(
    ConfirmModal("Title", "Are you sure?")
)
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

`OperationLogModal` disables Close until the process exits. Never swallows errors.

## Bundle system

Bundles are the curated Brewfile collections at `/usr/share/ublue-os/homebrew/*.Brewfile`.  
State is inferred by cross-referencing Brewfile contents against `brew list` + `flatpak list`.

States: `BASE` (cli — always on) / `ACTIVE` / `PARTIAL` / `AVAILABLE`

```python
from bluefinctl.core.bundles import get_bundles, activate_bundle, deactivate_bundle
bundles = await get_bundles()          # returns List[Bundle] with state
await activate_bundle("k8s-tools")     # brew bundle install
await deactivate_bundle("k8s-tools")   # removes orphaned packages only
```

Adding a new bundle: add an entry to `BUNDLE_REGISTRY` in `core/bundles.py`.

## OSC 9;4 progress (Ghostty tab bar)

Always write to `/dev/tty` — NOT `sys.stdout` (Textual owns stdout):

```python
from bluefinctl.util.osc import osc_progress, osc_progress_clear, osc_progress_indeterminate
osc_progress_indeterminate()   # pulsing (unknown duration)
osc_progress(50)               # 0-100
osc_progress_clear()           # remove indicator
```

`LogView` and `OperationLogModal` call these automatically.

## GNOME accent color

Read once at startup, injected into Textual Theme:

```python
from bluefinctl.theme.accent import get_accent_hex
# Returns hex like "#3584e4" for GNOME blue
```

In `app.py`, `register_theme(Theme(name="bluefin", primary=accent, accent=accent, ...))` maps the color across all widgets. Changing accent in GNOME Settings requires a restart.

## Adding a new screen

1. Create `screens/myscreen.py` with a `MyScreen(Screen)` class
2. Add a `Sidebar("myscreen")` in its `compose()`
3. Register in `app.py` `on_mount`: `self.install_screen(MyScreen(), name="myscreen")`
4. Add to `NAV_ITEMS` in `screens/_sidebar.py`
5. Add a `Binding` in `app.py`

## Common pitfalls

- **Worker race**: always init mutable attrs in `__init__`, not just at end of worker
- **Console() in core**: never use rich Console inside Textual — output goes to stdout (hidden). Use `self.notify()` for toasts or `OperationLogModal` for streaming
- **pkexec hangs**: polkit auth dialog appears in a separate GTK window over Ghostty — this works fine. Don't add a timeout to pkexec calls
- **Switch/RadioSet state**: set programmatically with `.value = True/False` (Switch) or `.action_select_button(idx)` (RadioSet)
- **Tree refresh**: call `tree.root.remove_children()` then re-run the load worker with `exclusive=True`
