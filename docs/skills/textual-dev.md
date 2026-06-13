---
name: textual-dev
description: "Textual/Python patterns, pitfalls, and conventions specific to bluefinctl. Use when writing screens, widgets, modals, or core modules — covers the non-obvious Textual behaviors that have already been discovered the hard way."
metadata:
  type: reference
---

# Textual Development Patterns

Conventions and pitfalls specific to bluefinctl. The Copilot CLI skill (`.agents/skills/bluefinctl-dev/`) covers the full workflow; this file records discovered workarounds and non-obvious requirements.

## Contents
- [Core / Screen Separation](#core--screen-separation)
- [Modals](#modals)
- [Programmatic Widget State](#programmatic-widget-state)
- [Writing to /etc/](#writing-to-etc)
- [OSC 9;4 Progress](#osc-94-progress)
- [Textual CSS Constraints](#textual-css-constraints)
- [Tree Nodes](#tree-nodes)
- [asyncio in Async Functions](#asyncio-in-async-functions)
- [Common Pitfalls](#common-pitfalls)

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
