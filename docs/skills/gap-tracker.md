---
name: gap-tracker
description: >-
  Tracks what is and isn't implemented in bluefinctl against the v1 spec.
  Use when choosing what to work on next, checking feature completeness,
  or confirming whether a screen or subsystem is done. Updated as of
  the feat/ux-completion branch (June 2026).
metadata:
  type: reference
---

# bluefinctl — Gap Tracker

Status of every v1 scope item. Pick one `[ ]` item, implement it, flip it to `[x]`, commit.

**Self-improvement loop:** Every session that touches a feature must also update the relevant `docs/skills/` file. Never a follow-up — same PR.

## Navigation

| Item | Status |
|------|--------|
| 4-screen horizontal ViewSwitcher (System · Updates · Developer · AI) | ✅ |
| Number keys 1–4 to switch screens | ✅ |
| `bctl` binary alias | ✅ |
| Command Palette (Ctrl+P) | ✅ |
| Help modal (?) | ✅ |

## Screens

### System (`screens/system.py`)

| Item | Status |
|------|--------|
| Identity card — image, boot, hostname | ✅ |
| Hardware card — GPU model, VRAM, devmode status | ✅ |
| Health card — GPU driver, systemd, Homebrew | ✅ |
| Active Kits summary | ✅ |
| Release Stream switch (testing / stable) | ✅ |
| Rollback calendar — date picker | ✅ |
| Quick Actions — real bordered accent buttons (Update All, Developer Mode, System Report, podman-tui) | ✅ |
| Update All inline (OpsBar, no modal) | ✅ |
| System Report inline (OpsBar, no modal) | ✅ |
| Update status in OpsBar on load | ✅ |
| Degraded mode for non-bootc systems | ⬜ Show "unavailable" in-place rather than crashing |

### Updates (`screens/updates.py`)

| Item | Status |
|------|--------|
| Full-width monospace image banner (stripped of transport prefix) | ✅ |
| Staged update alert bar | ✅ |
| Image signed indicator 🔒/🔓 | ✅ |
| Compression type via skopeo (zstd/gzip/zstd:chunked) | ✅ |
| Radio-style Update Schedule (Automatic / Notify only / Manual) | ✅ |
| Update Components (OS Image / Flatpaks / Homebrew) layer toggles | ✅ |
| Pause Updates (focus mode) switch + snooze buttons | ✅ |
| Release Stream section (stable/testing switch) | ✅ |
| Rollback section | ✅ |
| Update Now + Check for Updates pinned footer | ✅ |
| OpsBar for inline progress | ✅ |
| Changelog viewer | ⬜ `ChangelogViewer` widget exists as a stub; not rendered in updates screen |
| Scheduled strategy time-picker | ⬜ Deferred to v2 |

### Developer Mode (`screens/devmode.py`)

| Item | Status |
|------|--------|
| Devmode toggle (AdwSwitchRow) at top | ✅ |
| Status + Groups display | ✅ |
| **Kits tab** — kit list + detail pane | ✅ |
| **Kits tab** — per-package Install Package button | ✅ |
| **Kits tab** — Activate / Deactivate whole kit | ✅ |
| **Tools tab** — dev tool list with install status | ✅ |
| **Tools tab** — per-tool Install button | ✅ |
| **Tools tab** — Install All action | ✅ |
| **Environments tab** — Podman Desktop, Distrobox, Lima status | ✅ |
| Lima guided setup (4-step OperationModal) | ✅ |
| VSCode launch button | ✅ (wired to `launch_in_terminal(["code", "."])`) |
| DevMode relogin flow | ⬜ After enable/disable, user needs to log out. Currently just notifies. `core/operations.py` state machine exists but unused — should persist `needs-relogin` state and show banner on next launch. |
| Lima VM status from `limactl list --format json` | ⬜ Current check is superficial (`shutil.which("limactl")`) |
| Tools tab category filter | ⬜ Tools grouped by label rows but no filtering UI |

### AI (`screens/ai.py`)

| Item | Status |
|------|--------|
| GPU detection card (NVIDIA CDI / AMD KFD) | ✅ |
| Stack catalog ListView + detail pane | ✅ |
| Category filter bar (All / Serve / Dev / Train) | ✅ |
| Bundled quadlet catalog (nvidia/ and amd/) | ✅ |
| Deploy flow (preflight → confirm → copy quadlet → daemon-reload → pull → start) | ✅ |
| Stop / Remove stack | ✅ |
| Stack logs | ✅ |
| NGC auth check + prompt | ✅ |
| Clickable port links (OSC 8) | ⬜ Ports shown as text; OSC 8 hyperlinks not emitted |
| AI Tools tab — install kit | ✅ |
| AI Tools registry completeness | ⬜ `AI_TOOL_REGISTRY` has 6 entries; `ai-tools.Brewfile` has 21+ tools — see `docs/skills/ai-stacks.md` |
| VRAM badge greying (stack exceeds available VRAM) | ⬜ Warning shown but no greying in catalog |

## Cross-cutting

### Progress & Operations

| Item | Status |
|------|--------|
| `OperationModal` — unified progress widget | ✅ |
| `OperationLogModal` — raw log output modal | ✅ |
| `OpsBar` — persistent bottom bar | ✅ |
| `SegmentedProgressBar` — multi-stage bar | ✅ |
| `core/progress.py` — ProgressParser protocol | ✅ |
| OSC 9;4 progress in terminal tab/titlebar | ⬜ `util/osc.py` exists but OperationModal doesn't emit it yet |
| `core/operations.py` — resumable state machine | ⬜ Defined, never used |

### Help & UX

| Item | Status |
|------|--------|
| Help modal (?) with shortcut reference | ✅ (basic) |
| Footer shortcuts update per screen | ⬜ Footer shows global bindings but not per-screen ones |
| Toast notifications for key operations | ✅ (`self.notify()`) |

### Testing

| Item | Status |
|------|--------|
| pytest suite — 43 tests | ✅ |
| `test_app_acceptance.py` — 4-screen registration | ✅ |
| `test_commands.py` — PackageProvider, NavigationProvider | ✅ |
| `test_devmode.py` — tool inventory, Tools tab interactive | ✅ |
| `test_bundles.py`, `test_operations.py`, `test_progress.py`, `test_ai.py` | ✅ |
| Snapshot tests (SVG per screen) | ⬜ `pilot.export_screenshot()` not yet wired |
| CLI integration tests (`typer.testing.CliRunner`) | ⬜ |

### Headless CLI completeness

| Command | Status |
|---------|--------|
| `bctl` / `bluefinctl` (TUI launch) | ✅ |
| `bctl status` | ✅ |
| `bctl update` / `bctl update --check` | ✅ |
| `bctl devmode on/off/status` | ✅ |
| `bctl kit list` / `bctl kit install <name>` | ✅ |
| `bctl install brew:<pkg>` | ✅ |
| `bctl install flatpak:<app-id>` | ✅ |
| `bctl ai list/deploy/stop` | ✅ |
| `bctl focus on/off` | ⬜ |
| `bctl kit remove <name>` | ⬜ |

### Degraded mode (non-bootc systems)

| Item | Status |
|------|--------|
| System screen shows "unavailable" for bootc rows | ⬜ Currently may show errors/blanks |
| Updates screen explains bootc controls unavailable | ⬜ |
| Developer, AI screens remain fully functional | ✅ (don't depend on bootc) |

## Widget inventory

| Widget | File | Status |
|--------|------|--------|
| `AdwPreferencesGroup` | `widgets/adw.py` | ✅ |
| `AdwPropertyRow` | `widgets/adw.py` | ✅ |
| `AdwSwitchRow` + `_CheckToggle` | `widgets/adw.py` | ✅ |
| `AdwButtonRow` (with subtitle) | `widgets/adw.py` | ✅ |
| `AdwButtonsRow` | `widgets/adw.py` | ✅ |
| `AdwComboRow` | `widgets/adw.py` | ✅ |
| `AdwExpanderRow` | `widgets/adw.py` | ✅ |
| `OpsBar` | `widgets/ops_bar.py` | ✅ |
| `SegmentedProgressBar` | `widgets/segmented_progress.py` | ✅ |
| `RollbackCalendar` | `widgets/rollback_calendar.py` | ✅ |
| `OperationModal` | `widgets/operation_modal.py` | ✅ |
| `ChangelogViewer` | `widgets/changelog.py` | ⬜ stub — not shown in any screen |

## Known bugs / quirks

| Bug | Status |
|-----|--------|
| `toolkit.py` still exists on disk (not routed from nav) | ⬜ Harmless dead file — can delete |
| `core/operations.py` resumable state machine defined but never wired to any screen | ⬜ |
| `get_event_loop()` in `core/updates.py` and `core/system.py` — deprecated in 3.10+ | ⬜ Should be `get_running_loop()` |
| Updates screen `_load()` calls `run_worker(self._load(), exclusive=True)` after channel switch inside a `@work` method — double worker nesting | ⬜ Works but noisy |
