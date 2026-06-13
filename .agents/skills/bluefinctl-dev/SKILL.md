---
name: bluefinctl-dev
description: Development patterns and conventions for the bluefinctl Textual TUI project. Use when working in /var/home/jorge/src/bbrew, adding screens, wiring actions, creating modals, or modifying the theme/bundle system.
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
widgets/       Reusable Textual widgets (OperationModal, LogView)
theme/         GNOME accent color reader + bluefin.tcss
util/          OSC escape sequences, Ghostty detection, terminal launcher
```

**Rule:** All subprocess calls, file I/O, and system state live in `core/`. Screens only call core functions and present results.

## Five screens (new architecture)

| Key | Screen file | Core module | Notes |
|-----|-------------|-------------|-------|
| 1 | screens/system.py | core/system.py | bootc systems only |
| 2 | screens/updates.py | core/updates.py | bootc systems only |
| 3 | screens/toolkit.py | core/bundles.py | kit management |
| 4 | screens/devmode.py | core/devmode.py | 3 tabs: Overview/Tools/Envs |
| 5 | screens/ai.py | core/ai.py | 2 tabs: Stacks/Tools |

On non-bootc systems, System + Updates are hidden; Toolkit becomes screen 1.

## Platform detection

```python
from bluefinctl.app import _is_bootc_system
# Checks /run/ostree-booted or bootc status exit code
```

## Unified progress system

Every operation uses `OperationModal` (widgets/operation_modal.py):

```python
from bluefinctl.core.progress import BrewInstallParser
from bluefinctl.widgets.operation_modal import OperationModal

# Subprocess with progress parsing
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
    # ... do work
    yield ProgressUpdate(percent=100, message="Done")

rc = await self.app.push_screen_wait(
    OperationModal("My Operation", steps=my_steps())
)
```

Available parsers:
- `MultiStepParser(total_steps=N)` — wizard flows
- `PodmanPullParser()` — layer download percentages
- `BrewInstallParser(total_packages=N)` — formula install counting
- `BootcSwitchParser()` — bootc stage detection
- `IndeterminateParser()` — fallback (no percentage)

## Resumable operations (core/operations.py)

For operations that need reboot/logout:

```python
from bluefinctl.core.operations import Operation, OperationState, save_operation

op = Operation(id="lima-setup-1", kind="lima-setup", steps_total=5)
op.transition(OperationState.EXECUTING, "Installing Lima...")
save_operation(op)
# ... later, if reboot needed:
op.transition(OperationState.NEEDS_RELOGIN, "Log out to apply groups")
save_operation(op)
```

## Reusable modals (screens/_modals.py)

Use `push_screen_wait()` for every destructive or long-running action:

```python
# Confirmation
confirmed = await self.app.push_screen_wait(
    ConfirmModal("Title", "Are you sure?")
)

# Text input
value = await self.app.push_screen_wait(
    InputModal("Add Package", "Package name", placeholder="e.g. htop")
)

# Streaming subprocess (legacy — prefer OperationModal for new code)
rc = await self.app.push_screen_wait(
    OperationLogModal("Install", ["brew", "install", "htop"])
)
```

## Adding a new screen

1. Create `screens/myscreen.py` with a `MyScreen(Screen[None])` class
2. Add a `Sidebar("myscreen")` in its `compose()`
3. Register in `app.py` `on_mount`
4. Add to NAV_ITEMS in `screens/_sidebar.py`
5. Add a `Binding` in `app.py`

## OSC 9;4 progress (Ghostty tab bar)

Always write to `/dev/tty` — NOT `sys.stdout` (Textual owns stdout).
`OperationModal` handles this automatically.

## GNOME accent color

Read once at startup, injected into Textual Theme. Changing accent in GNOME requires a restart.

## Programmatic widget init — use `prevent()`, not a loading flag

```python
with self.prevent(Switch.Changed):
    self.query_one("#layer-os", Switch).value = os_on

with self.prevent(RadioSet.Changed):
    buttons[idx].value = True
```

## Headless CLI

Every TUI action has a headless equivalent via `cli.py`:
- `bluefinctl status` — system info
- `bluefinctl update` — trigger update
- `bluefinctl devmode on|off|status`
- `bluefinctl kit list|install <name>`
- `bluefinctl ai list|deploy|stop <stack>`

## Common pitfalls

- **Worker race**: always init mutable attrs in `__init__`, not just at end of worker
- **Console() in core**: never use rich Console inside Textual — use `self.notify()`
- **pkexec hangs**: polkit auth dialog appears in a separate GTK window — don't add timeouts
- **Tree refresh**: `tree.root.remove_children()` then re-run worker with `exclusive=True`
- **bootc switch**: positional target, not `--target`. Use `["pkexec", "bootc", "switch", ref]`
- **Textual CSS**: `vh`/`vw` units NOT supported. `Static` does NOT scroll (wrap in ScrollableContainer)
- **asyncio**: use `get_running_loop()` not `get_event_loop()` in async functions
