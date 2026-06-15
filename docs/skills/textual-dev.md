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
    - /python/cpython
    - /gnome/libadwaita
    - /websites/developer_gnome
---

# Textual Development Patterns

Conventions and pitfalls specific to bluefinctl. The dev skill (`.agents/skills/bluefinctl-dev/`) covers the full workflow; this file records non-obvious requirements and discovered workarounds. **Read before modifying any screen or widget.**

## Contents

- [Python / Stack Version](#python--stack-version)
- [Event Handlers — @on Decorator Pattern](#event-handlers--on-decorator-pattern)
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
- [Python 3.13 Type Annotations](#python-313-type-annotations)
- [GNOME HIG Compliance](#gnome-hig-compliance)
- [Common Pitfalls](#common-pitfalls)

## Python / Stack Version

**Python:** 3.13 (runtime) · `requires-python = ">=3.13"` · `target-version = "py313"`.  
**Textual:** 1.0.x · `textual>=1.0,<2.0`.

All source files have `from __future__ import annotations` (except empty `__init__.py`).  
All `# type: ignore` annotations are justified Textual API gaps — not sloppy avoidance.

## Event Handlers — @on Decorator Pattern

**Since Textual 0.23 / 1.0:** use `@on(Button.Pressed, "#id")` per handler instead of a single `on_button_pressed` if/elif dispatch chain. This is the canonical 1.0 pattern.

```python
from textual import on, work
from textual.widgets import Button

# ✓ Canonical — one handler per button
@on(Button.Pressed, "#btn-update-now")
def _on_update_now(self) -> None:
    self.action_update_now()

@on(Button.Pressed, "#btn-check")
def _on_check(self) -> None:
    self._check_for_updates()

@on(Button.Pressed, "#btn-op-cancel")
def _on_op_cancel(self) -> None:
    self._set_idle("Ready")

# ✗ Old pattern — replaced everywhere in this codebase
def on_button_pressed(self, event: Button.Pressed) -> None:
    if event.button.id == "btn-update-now":
        ...
    elif event.button.id == "btn-check":
        ...
```

### CSS selector support requires `control` on the message

The `@on(Msg, "#selector")` CSS filter **only works when the message class declares a
`control` property** returning the associated widget. Textual's built-in messages
(`Button.Pressed`, `Switch.Changed`, etc.) all have `control`. Project-local custom
messages (e.g. `AdwButtonRow.Pressed`, `AdwSwitchRow.Changed`) do **not** — using a CSS
selector on them raises `OnDecoratorError: The message class must have a 'control'`.

```python
# ✓ Works — Button.Pressed has control
@on(Button.Pressed, "#btn-ok")
def _ok(self) -> None: ...

# ✗ Raises OnDecoratorError at startup — AdwButtonRow.Pressed has no control
@on(AdwButtonRow.Pressed, "#btn-rollback")
def _rollback(self) -> None: ...

# ✓ Correct for custom messages — use @on without selector + check inside
@on(AdwButtonRow.Pressed)
def _on_adw_row(self, event: AdwButtonRow.Pressed) -> None:
    if event.row.id == "btn-rollback":
        self._do_rollback()
```

### Dynamic button IDs

When button IDs are generated at runtime (e.g. `id=f"install-{tool_id}"`), a CSS
selector can't match them statically. Keep `on_button_pressed` with `startswith()`:

```python
def on_button_pressed(self, event: Button.Pressed) -> None:
    btn_id = event.button.id or ""
    if btn_id.startswith("install-"):
        self._install_tool(btn_id[len("install-"):])
```

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

**`#adw-content` MUST have `height: 1fr`** or it will expand to fit content and never scroll.

**`scrollbar-gutter: stable` is not a valid Textual CSS property — do not use it.** It is silently ignored.

**The Screen base class has `overflow-y: auto`** which causes the Screen itself to scroll instead
of the inner `ScrollableContainer`. Always set `overflow: hidden hidden` on every custom Screen
subclass to prevent this:

```css
MyScreen { layout: vertical; overflow: hidden hidden; }
#adw-content { height: 1fr; }
```

For two-column layouts inside `#adw-content`, `.adw-col` **must** have explicit `height: auto`.
Without it, `Vertical` defaults to `height: 1fr`, which inside a `height: auto` Horizontal
creates a circular dependency that breaks content measurement:

```python
with ScrollableContainer(id="adw-content"):
    with Horizontal(classes="adw-cols"):
        with Vertical(classes="adw-col"):   # left
            yield AdwPreferencesGroup(...)
        with Vertical(classes="adw-col"):   # right
            yield AdwPreferencesGroup(...)
```

```css
.adw-cols { height: auto; }
.adw-col  { width: 1fr; height: auto; padding: 0 2; }  /* height: auto is required */
```

OpsBar uses `dock: bottom` and must be the last child.

### AdwActionRow with trailing install button

For feature-portal rows with an inline install button:

```python
AdwActionRow(
    "Podman Desktop",
    subtitle="Docker-compatible, zero daemon overhead.",
    trailing=Button("Install", id="install-podman", variant="primary"),
    id="tool-podman",
)
```

`AdwActionRow` uses `height: auto; min-height: 2`. If subtitles are long, they wrap and
make rows very tall. Cap them per-screen:

```css
MyScreen AdwActionRow { height: 3; }
MyScreen AdwActionRow > .adw-row-content > .adw-row-subtitle { overflow-x: hidden; }
```

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
@on(Button.Pressed, "#btn-devmode")
def _on_devmode(self) -> None:
    self.action_toggle_devmode()

def on_adw_switch_row_changed(self, event: AdwSwitchRow.Changed) -> None:
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
    proc = await asyncio.create_subprocess_exec("bootc", "status", "--format=json", ...)
    ...

# ✓ screens/system.py — calls core, updates widgets
async def _load_identity(self) -> None:
    info = await get_system_info()
    self.query_one("#sys-image", AdwPropertyRow).update_value(info.full_clean_ref)
```

**bootc JSON flag:** always use `--format=json`, not `--json`. Both work today but
`--format=json` is the canonical form and is used consistently in `update_runner.py`.

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
| `display: flex` | Invalid — Textual only accepts `block` or `none`. Use `Horizontal`/`Vertical` containers. |

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
# ✓ Correct in async context (Python 3.10+)
loop = asyncio.get_running_loop()

# ✗ Deprecated in Python 3.10+, raises RuntimeError in Python 3.14
loop = asyncio.get_event_loop()
```

`get_running_loop()` raises `RuntimeError` immediately if called outside an async
context, which makes the bug visible. `get_event_loop()` silently creates a new loop in
some Python versions and is removed entirely in 3.14.

## Python 3.13 Type Annotations

### AsyncGenerator — omit the send type

Python 3.13 added default type parameters to `AsyncGenerator`. The `None` send type
is now the default and should be omitted (ruff UP043 enforces this):

```python
# ✓ Python 3.13 — SendType defaults to None
async def my_steps() -> AsyncGenerator[ProgressUpdate]:
    ...

# ✗ Verbose — UP043 will auto-fix this
async def my_steps() -> AsyncGenerator[ProgressUpdate, None]:
    ...
```

### slots=True on value dataclasses

Value types that are instantiated in tight loops (progress events, search results) use
`@dataclass(slots=True)` for faster attribute access and lower memory:

```python
@dataclass(slots=True)
class ProgressUpdate:
    percent: float | None = None
    step: int | None = None
    total_steps: int | None = None
    message: str = ""
```

Affected classes: `ProgressUpdate`, `BootcEvent`, `ImageInfo`, `FlatpakResult`.
Do not add `slots=True` to dataclasses that participate in multiple inheritance.

### Username — prefer getpass.getuser()

`os.environ.get("USER", "")` returns an empty string when `$USER` is unset (root session,
`su`, CI). Passing `""` to `pkexec usermod -aG group ""` fails silently. Use:

```python
import getpass
username = os.environ.get("USER") or getpass.getuser()
```

`getpass.getuser()` falls back to `pwd.getpwuid(os.getuid()).pw_name` — correct on all POSIX systems.

## GNOME HIG Compliance

Source: [developer.gnome.org/hig](https://developer.gnome.org/hig/) — verified against live HIG.

### Capitalization — two rules, not one

The GNOME HIG mandates two distinct capitalization styles:

| Style | Use for | Example |
|-------|---------|--------|
| **Header caps** (Title Case) | Headings, tab titles, view titles, **button labels**, **switch labels**, menu items, tooltips | `"Update Now"`, `"Reboot on Logout"`, `"Check for Updates"` |
| **Sentence case** | Subtitles, checkboxes, radio buttons, field labels, combo labels, body/explanatory text | `"Downloads and installs automatically"`, `"bootc system image"` |

Header caps rule: capitalize all words ≥ 4 letters, all verbs (any length), all nouns (any length), always the first and last word. Prepositions < 4 letters stay lowercase.

```python
# ✓ Correct — switch label uses header caps
AdwSwitchRow("Reboot on Logout", ...)     # "on" = preposition 2 chars → lowercase
AdwSwitchRow("Opt Into Testing Stream")  # "Into" = 4 chars → uppercase

# ✓ Correct — subtitle uses sentence case
AdwSwitchRow("Reboot on Logout",
    subtitle="Will reboot when a staged update exists")  # sentence case

# ✗ Wrong — switch label in sentence case
AdwSwitchRow("Opt into testing stream", ...)  # violates header caps rule

# ✗ Wrong — subtitle in title case
AdwSwitchRow("OS Image", subtitle="Bootc System Image")  # over-capitalized
```

### Button labels

Per HIG: **imperative verbs, header capitalization, short, no icon+label combo** outside header bars.

```python
# ✓ Correct
Button("Update All",        variant="primary")   # imperative verb, title case
Button("Check for Updates",)                     # "for" = 3 chars → lowercase
Button("Roll Back",         variant="destructive")  # verb phrase
Button("Cancel")                                 # single word

# ✗ Wrong — not imperative
Button("Updates")   # noun, not verb
Button("OK / Cancel")  # combined — use separate buttons
```

### Button variants — suggested vs destructive

Per HIG: `suggested` (= `variant="primary"`) highlights an affirmative call-to-action.
`destructive` (= `variant="error"` in Textual) flags permanent/dangerous actions.

```python
Button("Update Now",   variant="primary")      # ✓ suggested — affirmative action
Button("Roll Back",    variant="error")        # ✓ destructive — can't be undone
Button("Install",      variant="primary")      # ✓ suggested — call to action
Button("Cancel",       variant="default")      # ✓ neutral
```

### Boxed-list rows — one control max, group headings above

Per HIG boxed list rules:
- Max **two** controls per row (one preferred)
- Each `AdwPreferencesGroup` title is a **heading above** the boxed area — never inside
- Clicking the row background triggers the control
- Rows that link to another view get a `→` arrow suffix
- Symbolic icons preferred over full-colour icons (lower visual footprint)

```python
# ✓ Correct — heading above the box
yield AdwPreferencesGroup(
    "Reboot Strategy",          # heading above box
    AdwSwitchRow("Reboot on Logout", ...),
    AdwButtonRow("Scheduled Window", ...),
)

# ✗ Wrong — heading inside a plain label row
yield Label("Reboot Strategy")  # not a group heading
yield AdwSwitchRow(...)
```

### Switches — describe the thing, not the action

Per HIG: switches are for binary on/off settings. The label describes **what** is toggled,
not the action of toggling it. Labels use header capitalization.

```python
# ✓ Correct — describes the thing
AdwSwitchRow("Reboot on Logout", subtitle="Reboots automatically when a staged update exists")
AdwSwitchRow("OS Image", subtitle="bootc system image")

# ✗ Wrong — describes the action
AdwSwitchRow("Enable automatic reboot on logout")  # sentence, wrong caps, too verbose
```

### HIG compliance checklist

Before adding any new widget:
- [ ] Group title: **header caps**, placed above the boxed list (`AdwPreferencesGroup`)
- [ ] Row title (switch/button/action): **header caps**, imperative verb where applicable
- [ ] Row subtitle: **sentence case**, concise explanatory text
- [ ] Button labels: **header caps**, imperative verb, no icon+label combo
- [ ] Primary action → `variant="primary"` (suggested); destructive → `variant="error"`
- [ ] Max 2 controls per row (1 preferred)
- [ ] Disabled when invalid, not hidden

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| `Switch` widget in ADW rows — 3 rows tall | Use `_CheckToggle` (already in `AdwSwitchRow`) |
| `@work` method wrapped in `run_worker()` | Call `@work` methods directly; they start their own worker |
| `push_screen_wait` without `@work` | Add `@work(exclusive=True)` to the calling method |
| `info.clean_image_ref` shown to users (no tag) | Use `info.full_clean_ref` for display |
| `height: auto` on Horizontal fills terminal | Use `height: N` or `height: 1fr` |
| `ScrollableContainer` never scrolls | Missing `height: 1fr` on `#adw-content`; or Screen has `overflow-y: auto` stealing scroll — add `overflow: hidden hidden` to Screen DEFAULT_CSS |
| `.adw-col` not sizing to content | Must set `height: auto` explicitly — `Vertical` default `height: 1fr` inside `height: auto` Horizontal creates circular dependency |
| Long `AdwActionRow` subtitles wrap — rows 4+ lines tall | Add `height: 3` + `overflow-x: hidden` on subtitle per-screen |
| `self.notify()` anywhere in the app | Banned — use `system_notify()` from `core/notify.py` |
| `Console()` in Textual screen/widget | Console writes to stdout and garbles TUI |
| pkexec hangs | The polkit dialog is a separate GTK window — don't add timeouts |
| `bootc switch --target ref` | Wrong — positional: `["pkexec", "bootc", "switch", ref]` |
| `bootc status --json` | Use `--format=json` — canonical form, consistent across all callers |
| `asyncio.get_event_loop()` in async function | Use `asyncio.get_running_loop()` |
| `AsyncGenerator[T, None]` in signature | Omit `None` — it's the default in Python 3.13 (ruff UP043) |
| `@on(CustomMsg, "#selector")` on messages without `control` | Raises `OnDecoratorError` — use `@on(CustomMsg)` + check inside |
| `on_button_pressed` if/elif for static IDs | Use `@on(Button.Pressed, "#id")` per handler |
| `os.environ.get("USER", "")` passed to pkexec | Use `os.environ.get("USER") or getpass.getuser()` |
| Switch label in sentence case | Use header caps: `"Reboot on Logout"` not `"Reboot on logout"` |
| Row subtitle in Title Case | Use sentence case: `"bootc system image"` not `"Bootc System Image"` |
| Button label that is a noun | Use imperative verb: `"Update"` not `"Updates"` |
| `variant="warning"` on primary action | Not a HIG style — use `"primary"` (suggested) or `"error"` (destructive) |
| Rich `[code]text[/code]` for monospace | Not a valid Rich tag. Use `[bold]` or color |
| OpsBar not last in compose | `dock: bottom` only works when OpsBar is the last child |
