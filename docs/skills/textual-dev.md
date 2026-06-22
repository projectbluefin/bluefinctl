---
name: textual-dev
description: >-
  Textual/Python patterns, pitfalls, and conventions specific to bluefinctl.
  Use when writing screens, widgets, modals, or core modules — covers the
  non-obvious Textual behaviors discovered the hard way: @work for
  push_screen_wait, _CheckToggle replacing Switch, height:auto Horizontal
  expansion, pkexec stdout, OSC progress, dark/light theming, thread workers,
  data_bind, and textual v8 breaking changes.
metadata:
  type: reference
  context7-sources:
    - /websites/textual_textualize_io
    - /textualize/textual
    - /python/cpython
    - /gnome/libadwaita
    - /websites/developer_gnome
---

# Textual Development Patterns

Conventions and pitfalls specific to bluefinctl. The dev skill
(`.agents/skills/bluefinctl-dev/`) covers the full workflow; this file
records **non-obvious requirements and discovered workarounds**.
Read before modifying any screen or widget.

Verified against: **textual 8.2.7** | **Python 3.13** | Context7 `/websites/textual_textualize_io`

---

## Contents

- [Python / Stack Version](#python--stack-version)
- [Textual v8 Breaking Changes](#textual-v8-breaking-changes)
- [Event Handlers — @on Decorator Pattern](#event-handlers--on-decorator-pattern)
- [Workers — @work and run_worker](#workers--work-and-run_worker)
- [Reactive Data Binding](#reactive-data-binding)
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
- [Thread Workers and call_from_thread](#thread-workers-and-call_from_thread)
- [Python 3.13 Type Annotations](#python-313-type-annotations)
- [Testing with run_test and pilot](#testing-with-run_test-and-pilot)
- [GNOME HIG Compliance](#gnome-hig-compliance)
- [Common Pitfalls](#common-pitfalls)

---

## Python / Stack Version

- **Python**: `>=3.13` (CI matrix is 3.13 only; `requires-python = ">=3.13"` in pyproject.toml)
- **Textual**: `>=8.2` (upgraded from `>=1.0,<2.0` in v0.2.1)
- **textual-dev**: `>=1.0` (satisfies textual `>=0.86.2`)
- CI runs `pip install -e ".[dev]"` — never add Python 3.12 back to the matrix without bumping `requires-python`

---

## Textual v8 Breaking Changes

These broke between textual v1 → v8. **All already fixed in the codebase.**

| API | Old (v1) | New (v8) | File |
|-----|----------|----------|------|
| `Select` empty sentinel | `Select.BLANK` | `Select.NULL` | — not used yet |
| `AdwSwitchRow.Changed` attribute | `.switch_row` | `.row` | `screens/devmode.py` |
| `Label()` keyword arg | `renderable=` | `content=` | — not used |
| `Static.renderable` property | `.renderable` | `.content` | — not used |
| `OptionList` separator | `Separator()` object | `None` | — not used |
| `OptionList` kwargs | `wrap=`, `tooltip=` | removed | — not used |

### AdwSwitchRow.Changed — always check `.row`, not `.switch_row`

Our `AdwSwitchRow` widget fires `AdwSwitchRow.Changed(row, value)`.
The attribute is **`.row`**:

```python
# CORRECT
def on_adw_switch_row_changed(self, event: AdwSwitchRow.Changed) -> None:
    if event.row.id == "devmode-switch":
        ...

# WRONG — mypy catches this, runtime AttributeError
if event.switch_row.id == "devmode-switch":
    ...
```

---

## Event Handlers — @on Decorator Pattern

Use `@on(Message.Type)` with a CSS selector to scope handlers to specific widgets.
This is cleaner than `on_<message_type>` name mangling for multiple widgets.

```python
from textual import on

class UpdatesScreen(Screen[None]):
    @on(Button.Pressed, "#apply-updates")
    def handle_apply(self, event: Button.Pressed) -> None:
        self.action_apply_updates()

    @on(Button.Pressed, "#cancel")
    def handle_cancel(self, event: Button.Pressed) -> None:
        self.dismiss()
```

### CSS selector support requires `control` on the message

For `@on(Msg, "#id")` to filter correctly, the message must set `control`
to the originating widget. Most built-in messages do. Custom messages must too:

```python
class Changed(Message):
    def __init__(self, row: AdwSwitchRow, value: bool) -> None:
        super().__init__()
        self.row = row
        self.value = value

    @property
    def control(self) -> AdwSwitchRow:
        return self.row
```

### Dynamic button IDs

When buttons share an `on_button_pressed` handler, check `event.button.id`:

```python
def on_button_pressed(self, event: Button.Pressed) -> None:
    match event.button.id:
        case "install": self._install()
        case "remove": self._remove()
```

---

## Workers — @work and run_worker

### Async worker (default) — for coroutines

```python
from textual import work

@work(exclusive=True)
async def fetch_status(self) -> None:
    result = await some_async_call()
    self.query_one("#status", Label).update(result)
```

### Thread worker — for blocking I/O

When you must call blocking code (subprocess, file I/O), use `thread=True`.
Use `call_from_thread` to update UI from the thread:

```python
@work(exclusive=True, thread=True)
def run_blocking_check(self) -> None:
    result = subprocess.run(["bootc", "status"], capture_output=True)
    # UI updates must go through call_from_thread
    self.call_from_thread(self._update_status, result.stdout)

def _update_status(self, data: bytes) -> None:
    self.query_one("#info", Label).update(data.decode())
```

Or use `post_message` which is thread-safe:

```python
@work(exclusive=True, thread=True)
def run_check(self) -> None:
    result = do_blocking_work()
    self.post_message(StatusReady(result))  # thread-safe
```

### run_worker — when you don't want a decorator

```python
self.run_worker(
    self.load_data(),
    exclusive=True,
    exit_on_error=False,   # suppress exceptions from crashing the app
)
```

### exclusive=True cancels the previous worker of the same group

Use `exclusive=True` for any action that replaces a prior in-flight operation
(e.g. typing in a search field, re-loading a status).

---

## Reactive Data Binding

Use `data_bind` to synchronise a reactive on a parent widget to a child.
Avoids manual watch functions for simple pass-through state:

```python
class ParentWidget(Widget):
    theme_name: reactive[str] = reactive("dark")

    def compose(self) -> ComposeResult:
        yield ChildWidget().data_bind(ParentWidget.theme_name)
```

`data_bind` accepts positional (same-name) or keyword (rename) arguments:

```python
yield clock.data_bind(clock_time=App.time)  # rename: parent.time → child.clock_time
```

Changes to the parent reactive automatically update the child's reactive.

---

## ADW Widget Library

Custom widgets in `src/bluefinctl/widgets/adw.py`. Every widget has inline CSS.

### Widget reference

| Widget | Use for |
|--------|---------|
| `AdwActionRow` | info rows with trailing widget |
| `AdwSwitchRow` | toggle rows (fires `.Changed`) |
| `AdwButtonRow` | rows with action button |
| `AdwExpanderRow` | collapsible section |
| `AdwComboRow` | dropdown selector |
| `AdwViewSwitcher` | tab navigation bar |
| `AdwStatusPage` | empty / error state |

### _CheckToggle replaces Switch

`Switch` is 3 rows tall by default. Use the private `_CheckToggle` widget
instead — it renders as a compact single-line checkbox:

```python
from textual.widgets._toggle_button import _CheckToggle

class MyRow(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label("Enable feature")
        yield _CheckToggle()
```

`_CheckToggle` fires `_CheckToggle.Changed(value=bool)`.

### Setting values programmatically (without firing Changed)

```python
# WRONG — fires Changed and may loop
switch.value = True

# CORRECT — silent set
with self.prevent(AdwSwitchRow.Changed):
    self.query_one("#my-switch", AdwSwitchRow).set_value(True)
```

Our `AdwSwitchRow.set_value(v)` already suppresses its own event; use it
instead of mutating `.value` directly.

### Content area — always use #adw-content

Every screen must have an `#adw-content` container that gets `height: 1fr`:

```python
def compose(self) -> ComposeResult:
    yield AdwHeaderBar(...)
    with VerticalScroll(id="adw-content"):
        yield AdwPreferencesGroup(...)
```

```css
#adw-content {
    height: 1fr;
}
```

Without this, content clips at the header and the scrollbar is missing.

### AdwActionRow with trailing install/remove button

One button, two modes — toggled via a `remove-mode` CSS class. Button ID stays
stable (`install-<tool_id>`) regardless of state:

```python
# At compose time
row = AdwActionRow(
    "Podman Desktop",
    subtitle="Cloud-native development",
    trailing=Button("Install", id="install-podman", variant="primary"),
    id="tool-podman",
)
yield row

# When detection confirms installed:
btn = self.query_one("#install-podman", Button)
btn.label = "Remove"
btn.variant = "error"
btn.add_class("remove-mode")

# When uninstalled:
btn.label = "Install"
btn.variant = "primary"
btn.remove_class("remove-mode")
```

Dispatch in `on_button_pressed`:
```python
if event.button.has_class("remove-mode"):
    self._remove_tool(tool_id)
else:
    self._install_tool(tool_id)
```

### HIG rules to follow

- Title case for section headings; sentence case for row labels and buttons
- Switches describe the THING, not the action: "Developer Mode", not "Enable Developer Mode"
- At most one trailing control per row
- Group headings above the boxed-list rows, not inside them

---

## Workers and push_screen_wait

`push_screen_wait` suspends the current screen until the pushed screen calls
`self.dismiss(result)`. **This requires `@work(exclusive=True)`** — without
`@work`, `push_screen_wait` deadlocks because the event loop is blocked.

```python
# CORRECT
@work(exclusive=True)
async def _toggle_devmode(self, enable: bool) -> None:
    confirmed = await self.app.push_screen_wait(
        ConfirmModal("Enable Developer Mode", "Add user to docker group?")
    )
    if confirmed:
        ...

# WRONG — deadlocks
async def _toggle_devmode(self, enable: bool) -> None:
    confirmed = await self.app.push_screen_wait(...)  # never returns
```

---

## Core / Screen Separation

**Rule:** Business logic lives in `core/`. Screens only call core functions.

```
src/bluefinctl/
├── core/          ← subprocess, file I/O, system calls (no Textual imports)
│   ├── updates.py
│   ├── devmode.py
│   └── ai.py
└── screens/       ← UI only; calls core, displays results
    ├── updates.py
    └── devmode.py
```

Every operation must have both a **headless CLI path** (`cli.py`) and a
**TUI path** (`screens/`). If you add a feature, add both.

---

## Modals

Modals live in `screens/_modals.py`. Two kinds:

### ConfirmModal — yes/no dialog

```python
confirmed = await self.app.push_screen_wait(
    ConfirmModal("Title", "Body text — what will happen?")
)
# confirmed: bool
```

### OperationLogModal — streaming subprocess output

```python
rc = await self.app.push_screen_wait(
    OperationLogModal("Installing Podman Desktop", ["pkexec", "flatpak", "install", ...])
)
# rc: int (return code)
```

Both require `@work(exclusive=True)` on the caller.

---

## Programmatic Widget State

Do not set reactive attributes in `on_mount` if they fire messages you want
to suppress on startup. Use `call_after_refresh` or `set_reactive`:

```python
def on_mount(self) -> None:
    # Fires watchers — good for initial data load
    self.call_after_refresh(self._load_state)

async def _load_state(self) -> None:
    state = await asyncio.get_running_loop().run_in_executor(None, get_devmode_state)
    with self.prevent(AdwSwitchRow.Changed):
        self.query_one("#devmode-switch", AdwSwitchRow).set_value(state.active)
```

---

## Writing to /etc/

Always use `pkexec` + a dedicated script. Never `subprocess.run(["sudo", ...])`.

```python
rc = await self.app.push_screen_wait(
    OperationLogModal(
        "Configuring network",
        ["pkexec", "bash", "-c", "echo 'nameserver 8.8.8.8' >> /etc/resolv.conf"],
    )
)
```

`pkexec` pops a polkit authentication dialog. stdout/stderr are captured by
`OperationLogModal` and streamed to the user.

---

## OSC Progress and Terminal Title

```python
from bluefinctl.util.osc import osc_set_title, osc_progress

osc_set_title("Updating system…")   # sets terminal tab title
osc_progress(42)                    # OSC 9;4;1;<n>  — Ghostty progress bar
osc_progress(100)                   # clears the progress indicator
```

Only call from the main thread (not from workers). Ghostty supports OSC 9;4;
natively; other terminals silently ignore it.

---

## Textual CSS Constraints

- **`display: flex` is invalid** — Textual CSS is not web CSS. Use `layout: horizontal` / `layout: vertical`.
- `height: auto` on a `Horizontal` container expands to fill the parent. Set `height: N` (exact rows) or `max-height: N` if you want limits.
- `scrollbar-gutter: stable` reserves space for the scrollbar even when content fits, preventing layout jump.
- `1fr` divides remaining space; `auto` sizes to content. Mix them.
- `&:focus` pseudo-class applies when the widget itself is focused; `&:focus-within` when any descendant is focused.

```css
/* Typical screen shell */
#adw-content {
    height: 1fr;          /* fill remaining space after header */
    overflow-y: auto;     /* enable scroll */
    scrollbar-gutter: stable;
}
```

---

## Dark / Light Theme

Textual v8 ships Catppuccin Frappe/Macchiato, atom-one, solarized, rosé pine.
bluefinctl reads the GNOME accent color at startup and maps it to a Textual theme:

```python
# src/bluefinctl/theme/gnome.py
from bluefinctl.theme.gnome import build_theme
app.theme = build_theme()   # called in on_mount
```

Hot-switch works: the app watches `GNOME_ACCENT_COLOR` env and can refresh
without restart. Test both modes: `textual run --dev src/bluefinctl/app.py`.

---

## asyncio in Async Functions

When you need the running loop inside a Textual `async def`:

```python
import asyncio

async def _load(self) -> None:
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, blocking_function)
```

**Never** call `asyncio.get_event_loop()` inside Textual — it may return the
wrong loop. Always `asyncio.get_running_loop()`.

---

## Thread Workers and call_from_thread

Inside a `@work(thread=True)` function, all Textual API calls must go through
`call_from_thread` — Textual is not thread-safe:

```python
@work(exclusive=True, thread=True)
def check_status(self) -> None:
    result = subprocess.run(["systemctl", "is-active", "podman"], capture_output=True)
    status = result.stdout.decode().strip()
    # safe to update UI from thread:
    self.call_from_thread(self._set_status_label, status)

def _set_status_label(self, status: str) -> None:
    self.query_one("#status", Label).update(status)
```

`post_message` is also thread-safe and preferred for complex multi-step updates:

```python
self.post_message(StatusLoaded(status))   # thread-safe
```

---

## Python 3.13 Type Annotations

### AsyncGenerator — omit the send type

```python
# CORRECT — Python 3.13 style
from collections.abc import AsyncGenerator

async def stream() -> AsyncGenerator[str]:
    yield "line"

# OLD — send type was required pre-3.13
async def stream() -> AsyncGenerator[str, None]:  # verbose, still works
    yield "line"
```

### slots=True on value dataclasses

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class BootcStatus:
    image_ref: str
    version: str
    booted: bool
```

`slots=True` gives ~40% faster attribute access and catches typos at class
definition time rather than at runtime.

### Username — prefer getpass.getuser()

```python
import getpass
username = getpass.getuser()   # works in pkexec context, unlike os.environ["USER"]
```

`os.environ.get("USER", "")` may be empty inside pkexec.

---

## Testing with run_test and pilot

All Textual app tests use `app.run_test()` as an async context manager.

```python
import pytest

@pytest.mark.asyncio
async def test_screen_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bluefinctl.app._is_bootc_system", lambda: False)
    app = BluefinCtl(start_screen="system")
    async with app.run_test() as pilot:
        await pilot.pause()           # flush pending messages
        label = app.screen.query_one("#some-label", Label)
        assert "expected" in label.renderable
```

### pilot.pause() — always call before asserting

`pilot.pause()` waits for all pending messages (including workers that post
messages on mount) to be processed. Without it, assertions may race:

```python
async with app.run_test() as pilot:
    await pilot.pause()           # flush on_mount workers
    await pilot.click("#button")
    await pilot.pause()           # flush button handler
    assert app.screen.query_one("#result").content == "done"
```

### run_test parameters

```python
async with app.run_test(
    size=(120, 40),          # terminal dimensions
    notifications=False,     # suppress notify() popups
) as pilot:
    ...
```

### Monkeypatching system calls

Every test that touches core/ functions must monkeypatch the subprocess/file
calls to avoid requiring a real bootc system:

```python
monkeypatch.setattr("bluefinctl.core.updates.run_bootc_status", AsyncMock(...))
```

---

## GNOME HIG Compliance

### Capitalization — two rules, not one

| Context | Rule | Example |
|---------|------|---------|
| Section headings, group titles, tab names | **Title Case** | "Cloud Native Development" |
| Row labels, button labels, switch labels, subtitles | **Sentence case** | "Install Podman Desktop" → "Install Podman desktop" |

Exception: proper nouns always capitalized regardless of position.

### Button labels

- Primary action: imperative verb — "Install", "Enable", "Apply"
- Destructive: "Remove", "Delete" (use `variant="error"`)
- Cancel: always "Cancel" (never "No", "Close", "Back")

### Button variants — suggested vs destructive

```python
Button("Install", variant="primary")     # suggested action (blue/accent)
Button("Remove", variant="error")        # destructive (red)
Button("Cancel", variant="default")      # neutral
```

### Switches — describe the thing, not the action

```
✓ Switch label: "Developer Mode"        (describes the state)
✗ Switch label: "Enable Developer Mode" (describes the action)
```

### HIG compliance checklist

- [ ] Section headings in Title Case
- [ ] Row labels in Sentence case
- [ ] One trailing control per row max
- [ ] Group heading above (not inside) the boxed list
- [ ] Primary action button uses `variant="primary"`
- [ ] Destructive action uses `variant="error"`

---

## Common Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `push_screen_wait` never returns | Missing `@work` on caller | Wrap caller in `@work(exclusive=True)` |
| `AttributeError: 'Changed' has no attribute 'switch_row'` | v8 renamed `.switch_row` → `.row` | Use `event.row.id` |
| `AttributeError: 'Select' has no attribute 'BLANK'` | v8 renamed `Select.BLANK` → `Select.NULL` | Use `Select.NULL` |
| Worker updates UI but nothing redraws | Calling Textual API from thread | Wrap in `call_from_thread(...)` |
| Screen content clips, no scrollbar | Missing `height: 1fr` on `#adw-content` | Add `#adw-content { height: 1fr; }` |
| `asyncio.get_event_loop()` returns wrong loop | Deprecated inside Textual | Use `asyncio.get_running_loop()` |
| `os.environ["USER"]` empty in pkexec | pkexec strips env | Use `getpass.getuser()` |
| `height: auto` Horizontal expands to full height | CSS auto behavior | Set explicit `height: N` |
| CI fails on Python 3.12 | `requires-python = ">=3.13"` | Remove 3.12 from CI matrix |
| Tests race (assert before handler runs) | Missing `await pilot.pause()` | Add `await pilot.pause()` after interactions |
| `display: flex` ignored | Not a valid Textual CSS property | Use `layout: horizontal` |
| Footer appears BELOW OpsBar | Both use `dock: bottom`; last-yielded wins | Yield `Footer()` before `OpsBar()`, override `Footer { dock: none; height: 1; }` |
| Footer/OpsBar overlap content area | Footer still docking | Add `Footer { dock: none; height: 1; background: $panel; }` to screen DEFAULT_CSS |
