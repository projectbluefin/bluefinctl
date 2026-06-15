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
    - /gnome/libadwaita
    - /websites/developer_gnome
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
| 1 | `screens/system.py` | `core/system.py` | 2-col; left: Image/System/Health; right: Update All → Testing switch → Rollback calendar |
| 2 | `screens/updates.py` | `core/updates.py` | Full-width image banner; radio schedule; staged-update alert; OpsBar footer |
| 3 | `screens/devmode.py` | `core/devmode.py` | Full-width DevMode toggle at top; 2-col grid of install rows below (no reboot for tools) |
| 4 | `screens/ai.py` | `core/ai.py` | GPU-gated; hidden when no GPU detected |

Navigation items: **System · Updates · Developer** (number keys 1–3). AI screen (key 4) only shown when GPU is detected.

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

Every custom Screen **must** set `overflow: hidden hidden` in DEFAULT_CSS.
The `Screen` base class has `overflow-y: auto`, which causes the Screen itself to scroll
instead of the inner `ScrollableContainer`.

```python
class MyScreen(Screen[None]):
    DEFAULT_CSS = """
    MyScreen { layout: vertical; overflow: hidden hidden; }
    .adw-cols { height: auto; }
    .adw-col  { width: 1fr; height: auto; padding: 0 2; }  /* height: auto required */
    #adw-content { height: 1fr; }
    """

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

**ViewSwitcher height: 2, OpsBar height: 2.** Don’t increase them — chrome eats content rows.

**App-level `Header`/`Footer` are dead chrome** when all screens are `push_screen`’d.
Pushed screens render over the app’s base layer. Remove them from `App.compose()`.

## system_notify — zero in-app toasts

```python
from bluefinctl.core.notify import system_notify
system_notify("Operation complete", "Details here")
system_notify("Failed", "brew exited 1", urgency="critical")
```

Never use `self.notify()` anywhere in the app. All user-facing notifications go to
`notify-send` via `system_notify()`. The in-app Textual Toast system is **disabled**.

## OpsBar — animated block progress bar

The redesigned OpsBar (height: 3, dock: bottom) shows animated Unicode block bars.
New API beyond the basics:

```python
ops.set_running("Installing Docker…", step=1, total=4)   # block bar + spinner
ops.add_completed("Docker")                               # adds ✓ Docker to ticker
ops.set_running("Installing Lima…",  step=2, total=4)
ops.set_complete("✓  Done — 2 tools installed")          # full green bar
ops.set_error("✗  Failed — brew install: exit 1")        # red
```

The `stage=` keyword still works (backward compat alias for `step=`).
The `add_completed(name)` method scrolls `✓ name` into the left ticker strip.

## Feature Portal pattern — devmode screen

The Developer screen is now a feature portal: each `AdwActionRow` presents a named
capability with a subtitle pitch + inline Install button as the `trailing=` widget.

```python
AdwActionRow(
    "Docker",
    subtitle="The Bluefin DX ships Docker with compose, lazydocker, and dive.",
    trailing=Button("Install", id="install-docker", variant="primary"),
    id="tool-docker",
)
```

Install state is detected on mount via background workers and buttons are updated:
- Not installed → `"Install"` button enabled, `variant="primary"`
- Installed → `"Installed ✓"` button disabled, `variant="success"`

Install operations stream `ProgressUpdate` objects to OpsBar directly — **no modals**.

## `display: flex` is invalid in Textual CSS

Textual only accepts `display: block` or `display: none`. Using `flex` throws
`StylesheetParseError` at runtime. To make a widget visible/hidden:

```css
.visible { display: block; }   /* ✓ correct */
.visible { display: flex;  }   /* ✗ invalid */
```

## Smart Reboot strategy — systemd user units

Reboot strategies write systemd **user** units to `~/.config/systemd/user/`.
Always run `systemctl --user daemon-reload` after writing or removing unit files.
Timer units need `systemctl --user enable --now <name>.timer` to activate.
Safety gate: always check `systemd-inhibit --list --no-pager | grep -qE 'audio|video|idle'`
before any auto-reboot — skip and log to `~/.local/share/bluefinctl/reboot-skipped.log`.


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

## AdwButtonRow — updating displayed text

`AdwButtonRow` renders via `render()` from `self._title`. Use the public method added in 0.1.0:

```python
row = self.query_one("#my-row", AdwButtonRow)
row.update_title("● Active")   # ✓ public API
# row._title = "● Active"; row.refresh()  ✗ fragile private access
```

## App-level action delegation pattern

Actions registered in `ActionsProvider` (`commands.py`) are called via `app.run_action(name)`. If the action is defined on a specific `Screen` subclass rather than the `App`, it won't dispatch correctly when a different screen is active.

**Pattern:** define the action on `App`, navigate to the target screen, then call the screen method:

```python
# In app.py
def action_toggle_devmode(self) -> None:
    self.switch_screen("system")
    self.call_after_refresh(self._trigger_toggle_devmode)

def _trigger_toggle_devmode(self) -> None:
    from bluefinctl.screens.system import SystemScreen
    try:
        screen = self.get_screen("system")
        if isinstance(screen, SystemScreen):
            screen.action_toggle_devmode()
    except Exception:  # noqa: BLE001
        pass
```

All four command-palette actions (`action_update_now`, `action_system_report`, `action_toggle_devmode`, `action_launch_podman_tui`) follow this pattern.

## DevMode screen — toggle at top, tools below

The Developer screen has a full-width `AdwSwitchRow` at the top for group membership
(docker, mock, lxd — requires reboot). The tool install rows below it do NOT require a reboot.
This separation is intentional and must stay clear to the user.

**Idempotent toggle pattern** — read actual state first, sync switch if already in desired state:

```python
@work(exclusive=True)
async def _toggle_devmode(self, enable: bool) -> None:
    loop = asyncio.get_running_loop()
    state = await loop.run_in_executor(None, _check_devmode_active)
    if state.active == enable:          # already in desired state
        self.query_one("#devmode-switch", AdwSwitchRow).set_value(enable)
        return
    # ... prompt + pkexec ...
    # On cancel/failure — revert the switch:
    self.query_one("#devmode-switch", AdwSwitchRow).set_value(not enable)
```

Use `set_value()` (not direct assignment) to change a switch without firing `Changed`.
Load initial state in a separate worker on mount so the switch reflects reality:

```python
def on_mount(self) -> None:
    self.run_worker(self._load_devmode_state(), exclusive=False)

async def _load_devmode_state(self) -> None:
    state = await loop.run_in_executor(None, _check_devmode_active)
    self.query_one("#devmode-switch", AdwSwitchRow).set_value(state.active)
```

Do NOT call `pkexec` in `on_mount` — it fires a polkit auth dialog on every screen switch.

## GNOME HIG Quick Reference

See `docs/skills/textual-dev.md` for the full HIG section. Summary for this codebase:

| Context | Capitalization | Example |
|---------|---------------|---------|
| Group headings (`AdwPreferencesGroup` title) | Header caps | `"Update Components"`, `"Reboot Strategy"` |
| Button labels | Header caps + imperative verb | `"Update Now"`, `"Check for Updates"`, `"Roll Back"` |
| Switch/toggle row titles (`AdwSwitchRow`) | Header caps | `"Reboot on Logout"`, `"OS Image"` |
| Row subtitles | Sentence case | `"bootc system image"`, `"Downloads automatically"` |
| Body/explanatory text in dialogs | Sentence case | `"Are you sure you want to roll back?"` |

Button variant mapping to HIG:
- `variant="primary"` → **suggested action** (affirmative, accent colour)
- `variant="error"` → **destructive action** (permanent/dangerous, red)
- `variant="default"` → neutral

## Red Flags

- `AdwSwitchRow("opt into testing stream")` — switch labels must use header caps: `"Opt Into Testing Stream"`
- Row subtitle in Title Case — subtitles use sentence case: `"bootc system image"` not `"Bootc System Image"`
- Button label that is a noun, not a verb — HIG requires imperative: `"Update"` not `"Updates"`
- `variant="warning"` on a Button — not a standard HIG style; use `"primary"` (suggested) or `"error"` (destructive)
- `variant="success"` for primary call-to-action — use `"primary"` (suggested); `"success"` is for confirmation states only
- `from textual.widgets import Switch` in any file — should be `_CheckToggle`
- `self.notify()` anywhere — banned; use `system_notify()` from `core/notify.py`
- `self.run_worker(self.action_something())` on a `@work`-decorated method
- `async def action_*` that calls `push_screen_wait` without `@work`
- `info.clean_image_ref` used as display string (missing tag)
- `height: auto` on `Horizontal` containers (expands to fill, not shrink)
- `ScrollableContainer` that never scrolls — missing `height: 1fr` on `#adw-content`
- Screen has no `overflow: hidden hidden` in DEFAULT_CSS — `Screen` base class has `overflow-y: auto`; pushed screens steal scroll from the inner container
- `.adw-col` without explicit `height: auto` — `Vertical` defaults to `height: 1fr`; inside a `height: auto` Horizontal this creates a circular dependency and breaks content measurement
- `scrollbar-gutter: stable` in any CSS — not a Textual property, silently ignored
- App-level `Header`/`Footer` in `App.compose()` when all screens are `push_screen`’d — they live behind the screen stack and are never visible; pure dead chrome
- `AdwActionRow` subtitles wrapping to 4+ lines — add `height: 3` + `overflow-x: hidden`
- Hardcoded color variables (`$background`, `$surface`) in TCSS
- `asyncio.get_event_loop()` — use `get_running_loop()` inside async functions
- Rich `Console()` inside Textual screen/widget — Console writes to stdout and garbles TUI
- `Widget` subclass with BOTH `render()` AND `compose()` — children overlap render text
- `KitsTab(Static)` with `layout: horizontal` CSS — use `KitsTab(Horizontal)` directly

## RollbackCalendar — Label-based calendar grid

The `RollbackCalendar` extends `Vertical` and uses **two Label children** — `#cal-grid` and `#cal-hint` — instead of mixing `render()` with `compose()`. Mixing them causes visual overlap where children float on top of the render text. The correct pattern:

```python
class RollbackCalendar(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("", id="cal-grid")   # updated via _update_grid()
        yield Label("", id="cal-hint")   # updated via _update_hint()

    def _update_grid(self) -> None:
        self.query_one("#cal-grid", Label).update(self._build_grid_text())
```

Never add `render()` to a widget that also has children from `compose()`.

## ViewSwitcherTab centering

To reliably center the tab label text in a `Static` subclass, return `Text(self._tab_name, justify="center")` from `render()`. The CSS `content-align: center middle` aligns the content block but Rich's `justify="center"` ensures the text string itself is horizontally centered within the widget width.

```python
from rich.text import Text

class ViewSwitcherTab(Static):
    def render(self) -> Text:
        return Text(self._tab_name, justify="center")
```

## Rich Progress for CLI headless commands

For `bctl <command>` headless paths that need a live display (not a full TUI), subclass `Progress` and override `get_renderables()` to add a header Panel above the task table:

```python
class UpdateProgress(Progress):
    def __init__(self, info: ImageInfo, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._info = info

    def get_renderables(self) -> object:  # type: ignore[override]
        yield Panel(header_text, border_style="dim white", padding=(0, 0))
        yield self.make_tasks_table(self.tasks)
```

Add custom fields to tasks via kwargs (e.g., `detail=`) — reference them in `TextColumn` as `{task.fields[detail]}`.

## bootc --progress-fd JSON schema

`sudo bootc upgrade --quiet --progress-fd N` writes JSON lines to fd N:

```json
{"type": "ProgressSteps", "task": "pulling", "steps": 12, "stepsTotal": 23, "bytes": 0, "bytesTotal": 0}
{"type": "ProgressBytes", "task": "pulling", "steps": 12, "stepsTotal": 23, "bytes": 152399872, "bytesTotal": 327155712}
```

Stage → OSC% mapping (mirrors uupd): `pulling` 0–80%, `importing` 80–90%, `staging` 90–100%.

Use `os.pipe()` + `pass_fds=(w_fd,)` to pass the write fd to the subprocess. `sudo` preserves non-tty file descriptors by default — this works.

```python
r_fd, w_fd = os.pipe()
proc = await asyncio.create_subprocess_exec(
    "sudo", "bootc", "upgrade", "--quiet", "--progress-fd", str(w_fd),
    pass_fds=(w_fd,),
)
os.close(w_fd)  # parent closes write end
# wrap r_fd with loop.connect_read_pipe() for async reads
```

## Full-update stage order (bctl update)

1. `sudo bootc upgrade --quiet --progress-fd N` — sequential (needs root, large, first)
2. Parallel via `asyncio.gather()`: `flatpak update -y --noninteractive`, `brew update && brew upgrade`, `distrobox upgrade -a`

All runners live in `core/update_runner.py`. Display lives in the `update` command in `cli.py`.



When a tab widget has a two-pane horizontal layout, extend `Horizontal` directly rather than `Static` with `layout: horizontal` CSS. `Static` is for text display; `Horizontal`/`Vertical` are the correct layout containers.

```python
# Good
class KitsTab(Horizontal): ...
class ToolsTab(Vertical): ...

# Bad — Static with layout override is fragile
class KitsTab(Static):
    DEFAULT_CSS = "KitsTab { layout: horizontal; }"
```



- [ ] `pytest` passing (97 tests)
- [ ] `ruff check src/ tests/` clean
- [ ] `mypy src/` clean (strict)
- [ ] `ghostty -e bctl &` launched and affected screen visible/functional
- [ ] No `Switch` imports remain in ADW widget code
- [ ] All new async actions that call `push_screen_wait` have `@work(exclusive=True)`
- [ ] Skill file updated in same PR if new pattern discovered

## Common pitfalls

See `docs/skills/textual-dev.md` for the full pitfall catalogue.
