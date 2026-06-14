# bluefinctl — Gap Tracker

Status of every v1 scope item. Pick one `[ ]` item, implement it, flip it to `[x]`, commit.

**Self-improvement loop:** Every session that touches a feature must also update the relevant `docs/skills/` file with what was learned. Never a follow-up — same PR.

---

## Screens

### System (`screens/system.py`)

- [x] Identity group — image ref, boot status, hostname
- [x] Hardware group — GPU model, devmode status
- [x] Health group — GPU driver, systemd, Homebrew
- [x] Active Kits summary row
- [x] Quick Actions — Update All, Toggle Devmode, System Report, podman-tui
- [x] Release Channel — `AdwSwitchRow` "Opt into \`testing\` stream" (`bootc switch`)
- [x] Rollback group — quick `bootc rollback` button + `RollbackCalendar` widget
- [x] 2-column layout (`.adw-cols`)
- [x] OpsBar docked at bottom
- [ ] **Running Services** — pod count from `podman pod ls --format json`; show `N pods active` with podman-tui launch shortcut. See `core/system.py:get_system_info()` — add `pod_count` field.
- [ ] **Active Kits detailed** — current value is always "Loading…" or a comma list that may overflow. Needs truncation + "(+N more)" and a hover/detail path.
- [ ] **GPU VRAM in Hardware** — `sys-gpu` only shows model. Add `sys-vram` property row using `info.gpu.vram_mb // 1024` GB.
- [ ] **System Report action** — `action_system_report()` calls `ujust report` but has no progress modal. Wire `OperationLogModal("System Report", ["ujust", "report"])`.
- [ ] **RollbackCalendar image tag format** — needs verification on real hardware. Date-tagged builds may use `<channel>-YYYYMMDD` (e.g. `testing-20260610`) or `<version>-YYYYMMDD`. The `configure()` method takes `tag_prefix`; match actual registry format.

### Updates (`screens/updates.py`)

- [x] Software Updates group — status, image, last updated
- [x] Update Now button (real Button, primary) + inline uupd JSON progress
- [x] Check for Updates button
- [x] Automatic Updates — Schedule combo (Automatic/Notify/Manual)
- [x] Strategy description row (updates on combo change)
- [x] What to Update — OS Image, Flatpaks, Homebrew switches
- [x] Pause Updates — Focus Mode switch + Snooze buttons
- [x] 2-column layout
- [x] OpsBar with segmented progress (System/Brew/Flatpak)
- [x] pkexec batching (one prompt per strategy change)
- [ ] **Scheduled strategy time-picker** — design spec notes "not yet implemented". Requires a time/day-of-week picker widget. When strategy = "Scheduled", show a row asking which day/time. Store in `/etc/uupd/config.json` schedule field (check uupd docs for exact field name).
- [ ] **Focus mode expiry countdown** — status row should show "Paused until 10pm" not just "paused". Read `state.json` `expires_at` field from `core/updates.py:FocusState`.

### Toolkit (`screens/toolkit.py`)

- [x] Kit list — ListView with status badges [active]/[partial]/[available]
- [x] Kit detail pane — package list, activate/deactivate
- [x] Kit activate/deactivate via OperationModal
- [ ] **Category filter bar** — `[All] [Terminal] [AI & ML] [Editors] [K8s] [Cloud] [Fonts]`. Add `RadioSet` above kit list. Filter `self._bundles` by `bundle.meta.category`. Category derives from `BundleCategory` enum in `core/bundles.py`.
- [ ] **Disk usage estimate** — show total package size in kit detail. `brew info --json <formula>` returns `bottle.stable.cellar` size. Cache this; expensive to compute fresh.
- [ ] **Kit description** — detail pane currently shows raw package list. Add `meta.description` field to `Bundle` dataclass in `core/bundles.py` parsed from Brewfile header comments (`# Description: ...`).
- [ ] **j/k navigation** — add `Binding("j", "cursor_down")` / `Binding("k", "cursor_up")` to ToolkitScreen.
- [ ] **Command Palette install wiring** — `PackageProvider` in `commands.py` yields actions for `install brew:ripgrep` etc. but `action_install_package()` is a stub. Wire to `OperationModal(["brew", "install", pkg])`.
- [ ] **OpsBar for kit install progress** — currently uses OperationModal popup. Consider switching to OpsBar inline progress for consistency with Updates screen.

### DevMode (`screens/devmode.py`)

- [x] OverviewTab — status, runtime health, quick actions
- [x] ToolsTab — dev tool list with install status
- [x] EnvironmentsTab — Podman, Distrobox, Lima status
- [x] Lima wizard (4-step OperationModal via `lima_setup_steps()`)
- [x] Install All dev tools action
- [x] OpsBar
- [ ] **DevMode relogin flow** — after `enable_devmode()` succeeds, the user needs to log out for group membership to apply. Currently just notifies. Should use `core/operations.py` to persist `needs-relogin` state and show a banner on next launch. See `operations.py` — state machine is defined but never used.
- [ ] **EnvironmentsTab Lima check** — Lima detection is superficial. Should check `limactl list --format json` for actual VM status, not just `shutil.which("limactl")`.
- [ ] **VSCode launch** — "Open VSCode" button in Quick Actions tab calls a stub. Wire to `launch_in_terminal(["code", "."])` or `xdg-open vscode://...`.
- [ ] **Category filter on ToolsTab** — tools are grouped by category label rows (non-selectable). No filtering. Add filter similar to Toolkit category filter.

### AI (`screens/ai.py`)

- [x] StacksTab — GPU card, category filter, stack list with VRAM badges
- [x] Stack detail pane — description, VRAM/disk, auth status, port list
- [x] Context-aware action buttons (Deploy/Start/Stop/Remove/Logs/Browser)
- [x] Pre-deploy NGC/HF auth gates
- [x] ToolsTab — AI tool inventory
- [x] Bundled quadlet catalog (7 NVIDIA + 6 AMD stacks)
- [x] OpsBar
- [ ] **OSC 8 port links** — "Open in browser" shows `http://localhost:<port>` but it's not a clickable OSC 8 hyperlink. Use `util/osc.py:osc_hyperlink(url, text)` to emit `\x1b]8;;url\x1b\\text\x1b]8;;\x1b\\`. Render in the stack detail pane ports section.
- [ ] **AI Tools registry completeness** — `AI_TOOL_REGISTRY` has 6 entries but `ai-tools.Brewfile` has 21+ tools. Add: aichat, opencode, block-goose-cli (goose), crush, gemini-cli, kimi-cli, llmfit, mistral-vibe, qwen-code, ramalama, linux-mcp-server, lm-studio, claude-code, codex, copilot-cli, antigravity, Jan (flatpak). Each needs `slug`, `command`, `name`, `description`, `category`.
- [ ] **Stack category filter persistence** — category selection resets when `_load()` re-runs. Store `self._active_category` and re-apply after reload.
- [ ] **GPU card VRAM** — shows `<vendor> <model>` but not VRAM. `GpuDetection.vram_gb` is available; add to display string.
- [ ] **RollbackCalendar image tag verification** — same issue as System screen item above.

---

## Cross-cutting

### Progress & Operations

- [x] `OperationModal` — title + ProgressBar + collapsible log
- [x] `SegmentedProgressBar` — multi-stage bar driven by uupd JSON
- [x] `UupdJsonParser` — parses uupd `--json` output into stage-indexed updates
- [x] `OpsBar` — shared persistent bottom bar (dock: bottom, all screens)
- [ ] **`operations.py` resumable state machine** — defined in `core/operations.py` but never instantiated. Used for reboot/relogin flows (DevMode enable, bootc switch). On next launch, `app.py:on_mount` should call `OperationStateManager.load()` and surface any pending operations with a banner. States: `needs-relogin`, `needs-reboot`, `pending-verification`, `complete`, `failed`.
- [ ] **OSC 9;4 progress in OpsBar** — `util/osc.py` has `osc_progress()` but OpsBar never calls it. Add `osc_progress(pct)` calls in `SegmentedProgressBar.advance()` / `complete()`.

### Help & UX

- [x] ViewSwitcher navigation (number keys 1-5)
- [x] Sub-tab styling (TabbedContent active tab = bold + accent tint)
- [x] AdwButtonRow `›` chevron (left-aligned, clearly actionable)
- [x] `_CheckToggle` widget (checkbox visual instead of horizontal slider)
- [ ] **Help modal content** — `HelpModal` in `_modals.py` exists but shows placeholder text. Fill with actual shortcut table grouped by Global / Screen-specific. Reference `BINDINGS` from each screen.
- [ ] **Footer bar dynamic hints** — Textual `Footer` shows bindings of the focused widget. Currently the app yields `Footer()` in `app.py` compose but it's covered by pushed screens. Either use a custom footer per screen or make the `ViewSwitcher` show context hints. Lowest-effort: add a `Label` row at the bottom of each screen's `compose()` showing screen-specific shortcuts.
- [ ] **Toast notifications with context** — `self.notify()` is used but expiry countdowns ("Focus mode expires in 1h") aren't shown. Add `_schedule_focus_expiry_toast()` in UpdatesScreen that fires a notify at the expiry time.

### Testing

- [ ] **Snapshot tests** — zero exist. Textual supports `pilot.export_screenshot()` for SVG snapshots. Add one per screen in `tests/test_snapshots.py`. Run with `pytest --snapshot-update` to regenerate.
- [ ] **CLI headless tests** — `cli.py` has `status`, `update`, `devmode`, `kit` commands. Add integration tests in `tests/test_cli.py` using `typer.testing.CliRunner`.

### Headless CLI completeness

- [x] `bluefinctl status` — prints system info
- [x] `bluefinctl update` — triggers uupd
- [x] `bluefinctl devmode on|off|status`
- [x] `bluefinctl kit install/list`
- [ ] `bluefinctl focus on [--hours=N]` — maps to `activate_focus_mode()`
- [ ] `bluefinctl focus off` — maps to `deactivate_focus_mode()`
- [ ] `bluefinctl ai deploy <stack>` — maps to `deploy_stack()`
- [ ] `bluefinctl ai list` — maps to `get_stacks()`
- [ ] `bluefinctl ai stop <stack>` — maps to `stop_stack()`
- [ ] `bluefinctl ai ngc-auth <key>` — creates `ngc-api-key` podman secret
- [ ] `bluefinctl rollback` — maps to `bootc rollback`
- [ ] `bluefinctl channel testing|stable` — maps to `bootc switch`
- [ ] `--json` flag on `status` — already has `print_status()` but not JSON-formatted

### Degraded mode

- [ ] When `bootc` is missing → System/Updates screens show "not a bootc system" banner, not errors
- [ ] When `brew` is missing → Toolkit kit list shows install prompt for Homebrew
- [ ] When `podman-tui` is missing → System Quick Actions shows disabled "Install podman-tui" button
- [ ] When `lima` is missing → DevMode Environments tab shows install prompt
- [ ] When `skopeo` AND `podman` are both missing → RollbackCalendar shows "Install skopeo to verify image availability" message

---

## Widget inventory

| Widget | File | Status | Notes |
|--------|------|--------|-------|
| `AdwPreferencesGroup` | `widgets/adw.py` | ✅ | Bordered group; no separators |
| `AdwActionRow` | `widgets/adw.py` | ✅ | title+subtitle+trailing |
| `AdwSwitchRow` | `widgets/adw.py` | ✅ | Uses `_CheckToggle`, not Textual Switch |
| `AdwComboRow` | `widgets/adw.py` | ✅ | Cycles choices on click |
| `AdwButtonRow` | `widgets/adw.py` | ✅ | Left-aligned `title  ›` |
| `AdwButtonsRow` | `widgets/adw.py` | ✅ | Real Textual Buttons side-by-side |
| `AdwPropertyRow` | `widgets/adw.py` | ✅ | Read-only key: value |
| `AdwExpanderRow` | `widgets/adw.py` | ✅ | Collapsible children |
| `OpsBar` | `widgets/ops_bar.py` | ✅ | Docked bottom bar; all 5 screens |
| `SegmentedProgressBar` | `widgets/segmented_progress.py` | ✅ | Multi-stage; ✓/▶/· states |
| `RollbackCalendar` | `widgets/rollback_calendar.py` | ✅ | Month grid; skopeo verification; 24h cache |
| `OperationModal` | `widgets/operation_modal.py` | ✅ | Title+progress+log modal |
| `ChangelogViewer` | `widgets/changelog.py` | ✅ | Reads `/usr/share/ublue-os/changelog.md` |
| `_CheckToggle` | `widgets/adw.py` | ✅ | `[✓]`/`[ ]` checkbox; private |

---

## Known bugs / quirks

1. **`uupd.service` start-limit** — the service has `StartLimitBurst=3`. After 3 manual triggers in 10 minutes, it fails with exit 1. The `_check_for_updates()` method handles `bootc upgrade --check` but not this limit. Workaround: run `pkexec systemctl reset-failed uupd.service` before retrying.
2. **RollbackCalendar on non-Bluefin** — `skopeo inspect` against `ghcr.io` will succeed even on a non-bootc system, showing dates that can't actually be applied. The calendar should check `/run/ostree-booted` before rendering.
3. **`set_value()` race** — calling `AdwSwitchRow.set_value()` before the widget is fully mounted (e.g. in `_load()` before `on_mount` fires) silently fails. Always guard with `with contextlib.suppress(NoMatches)` or check `is_mounted`.
4. **`AdwComboRow` first-click** — the first click cycles FROM the initial value, so if `value="Automatic"` is set and the user hasn't interacted, the first click shows "Notify" (the next item). The combo starts at the index of the initial value correctly, so this is expected — document it for users.
5. **OpsBar `dock: bottom`** — in Textual, `dock: bottom` inside a Screen with `layout: vertical` reserves space at the bottom. But if the screen has `height: auto` children that overflow, the docked widget may overlap content. Ensure `#adw-content` has `height: 1fr` so it compresses correctly.
