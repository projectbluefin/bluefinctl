---
name: gap-tracker
description: >-
  Tracks what is and isn't implemented in bluefinctl against the v1 spec.
  Use when choosing what to work on next, checking feature completeness,
  or confirming whether a screen or subsystem is done. Updated June 2026
  (1.0 release prep session).
metadata:
  type: reference
---

# bluefinctl — Gap Tracker

Status of every v1 scope item. Pick one `⬜` item, implement it, flip it to `✅`, commit.

**Self-improvement loop:** Every session that touches a feature must also update the relevant `docs/skills/` file. Never a follow-up — same PR.

## Navigation

| Item | Status |
|------|--------|
| 3-screen horizontal ViewSwitcher (System · Updates · Developer) | ✅ |
| AI tab hidden for 1.0 | ✅ |
| Number keys 1–3 to switch screens | ✅ |
| `bctl` / `just run` to launch | ✅ |
| Command Palette (Ctrl+P) | ✅ |
| Help modal (?) | ✅ |

## Screens

### System (`screens/system.py`)

| Item | Status |
|------|--------|
| Identity card — image (full_clean_ref with tag), boot, hostname | ✅ |
| Hardware card — GPU model, VRAM, devmode status | ✅ |
| Health card — GPU driver, systemd, Homebrew | ✅ |
| Active Kits summary | ✅ |
| Release Stream switch (testing / stable) | ✅ |
| Rollback calendar — date picker with available snapshots | ✅ |
| Quick Actions — Update All only (bottom right) | ✅ |
| Scrollbar — `#adw-content { height: 1fr }` | ✅ |
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
| Smart Reboot Strategy group | ✅ |
| — Reboot on Logout (systemd user service + autologin hint) | ✅ |
| — Scheduled Window (2am timer, AC power + inhibitor check) | ✅ |
| — Manual (explicit opt-out) | ✅ |
| Snooze / Focus mode | ✅ Removed — snooze was meaningless given infrequent update checks |
| Release Stream section | ✅ Removed — on System screen |
| Rollback section | ✅ Removed — on System screen |
| Update Now + Check for Updates pinned footer | ✅ |
| Scrollbar — `#adw-content { height: 1fr }` | ✅ |
| OpsBar for inline progress | ✅ |
| Changelog viewer | ⬜ `ChangelogViewer` widget stub exists; not rendered |
| Scheduled strategy time-picker (let user change 2am window) | ⬜ Deferred to v2 |
| Future: Idle reboot (logind idle hint + countdown) | ⬜ ADR 0001 documents this |
| Future: Screen-lock reboot (login1 Lock signal, 30-min buffer) | ⬜ ADR 0001 documents this |

### Developer (`screens/devmode.py`)

| Item | Status |
|------|--------|
| Feature portal — no tabs, no devmode switch, no modals | ✅ |
| Two-column layout (Cloud Native left, Editors + Virt right) | ✅ |
| Scrollbar — `#adw-content { height: 1fr }` | ✅ |
| AdwActionRow height capped at 3, subtitle overflow-x: hidden | ✅ |
| Silent `dx-group` provisioning on mount | ✅ |
| **Cloud Native Development** group | ✅ |
| — Podman Desktop (CNCF, top tier) | ✅ |
| — The Bluefin WSL Experience (Lima/CNCF, top tier, preselects VS Code) | ✅ |
| — Incus (homebrew, third tier, fully supported) | ✅ |
| — Docker | ✅ |
| **Editors** group (VS Code, VSCodium, Zed, JetBrains, Neovim, Helix) | ✅ |
| **Virtualization** group (virt-manager + QEMU) | ✅ |
| Install state detection (concurrent, on mount) | ✅ |
| OpsBar streaming install progress | ✅ |
| `add_completed(name)` ticker after each tool | ✅ |
| Lima install chains VS Code automatically | ✅ |
| Incus: `brew install incus` + `pkexec usermod -aG incus-admin` | ✅ |
| Lima VM status from `limactl list --format json` | ⬜ Detection uses `limactl list --json`; could be richer |
| Remove/uninstall actions | ⬜ Only Install supported; no Remove button yet |

### AI (`screens/ai.py`)

| Item | Status |
|------|--------|
| Hidden for 1.0 (tab removed from navigation) | ✅ |
| GPU detection card (NVIDIA CDI / AMD KFD) | ✅ |
| Stack catalog ListView + detail pane | ✅ |
| Category filter bar (All / Serve / Dev / Train) | ✅ |
| Bundled quadlet catalog (nvidia/ and amd/) | ✅ |
| Deploy / Stop / Remove / Logs | ✅ |
| NGC auth check + prompt | ✅ |
| Clickable port links (OSC 8) | ⬜ Ports shown as text only |
| AI Tools registry completeness | ⬜ 6 entries; `ai-tools.Brewfile` has 21+ |
| VRAM badge greying | ⬜ Warning shown, no greying |

## Cross-cutting

### Notifications

| Item | Status |
|------|--------|
| `system_notify()` via `notify-send` — zero in-app toasts | ✅ |
| `self.notify()` banned everywhere | ✅ All calls replaced |
| `core/notify.py` — `system_notify(title, body, urgency)` | ✅ |

### Progress & Operations

| Item | Status |
|------|--------|
| `OpsBar` — animated Unicode block bar, step counter, ✓ ticker | ✅ |
| `OperationModal` / `OperationLogModal` — no longer used (inline-only) | ✅ Removed from all screens |
| `core/progress.py` — ProgressParser, ProgressUpdate | ✅ |
| OSC 9;4 progress in terminal tab/titlebar | ⬜ `util/osc.py` exists but not wired |
| `core/operations.py` — resumable state machine | ⬜ Defined, never used |

### Help & UX

| Item | Status |
|------|--------|
| Help modal (?) with shortcut reference | ✅ (basic) |
| Footer shortcuts update per screen | ⬜ Global bindings only |

### Testing

| Item | Status |
|------|--------|
| pytest suite — 86 tests | ✅ |
| `test_reboot_strategy.py` — 10 tests for smart reboot helpers | ✅ |
| `test_app_acceptance.py` — 3-screen registration (AI hidden) | ✅ |
| `test_commands.py` — PackageProvider, NavigationProvider | ✅ |
| `test_devmode.py` — tool inventory, install detection | ✅ |
| `test_bundles.py`, `test_operations.py`, `test_progress.py` | ✅ |
| Snapshot tests (SVG per screen) | ⬜ Not wired |
| CLI integration tests (`typer.testing.CliRunner`) | ⬜ |

### Headless CLI completeness

| Command | Status |
|---------|--------|
| `bctl` / `bluefinctl` (TUI launch) | ✅ |
| `bctl status` | ✅ |
| `bctl update` / `bctl update --check` | ✅ |
| `bctl devmode on/off/status` | ✅ |
| `bctl install brew:<pkg>` / `flatpak:<app-id>` | ✅ |
| `bctl ai list/deploy/stop` | ✅ |
| `bctl focus on/off` | ⬜ |
| `bctl kit remove <name>` | ⬜ |

### Degraded mode (non-bootc systems)

| Item | Status |
|------|--------|
| System screen shows "unavailable" for bootc rows | ⬜ |
| Updates screen explains bootc controls unavailable | ⬜ |
| Developer, AI screens remain fully functional | ✅ |

## Widget inventory

| Widget | File | Status |
|--------|------|--------|
| `AdwPreferencesGroup` | `widgets/adw.py` | ✅ |
| `AdwPropertyRow` | `widgets/adw.py` | ✅ |
| `AdwActionRow` | `widgets/adw.py` | ✅ |
| `AdwSwitchRow` + `_CheckToggle` | `widgets/adw.py` | ✅ |
| `AdwButtonRow` (with subtitle) | `widgets/adw.py` | ✅ |
| `AdwComboRow` | `widgets/adw.py` | ✅ |
| `AdwExpanderRow` | `widgets/adw.py` | ✅ |
| `OpsBar` (animated block bar) | `widgets/ops_bar.py` | ✅ |
| `RollbackCalendar` | `widgets/rollback_calendar.py` | ✅ |
| `OperationModal` | `widgets/operation_modal.py` | ✅ (exists, no longer used in screens) |
| `ChangelogViewer` | `widgets/changelog.py` | ⬜ stub only |

## Known bugs / quirks

| Bug | Status |
|-----|--------|
| `toolkit.py` still exists on disk (dead file, not routed) | ⬜ Safe to delete |
| `core/operations.py` resumable state machine never wired | ⬜ |
| Updates screen double worker nesting on channel switch | ⬜ Works but noisy |
