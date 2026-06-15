# Changelog

All notable changes to bluefinctl are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-06-15

First public release of **bluefinctl** (`bctl`) — the keyboard-driven TUI control
panel for [Bluefin OS](https://projectbluefin.io).

### Added

#### System screen (key `1`)
- Full system identity panel: bootc image ref, boot status, hostname
- Hardware detection: GPU vendor/model/VRAM, developer mode indicator
- Health panel: GPU driver, systemd status, Homebrew presence
- Active Kits display (bundles)
- Release Stream toggle — switch between `latest` and `testing` image tags
- Rollback calendar — roll back to any previous build date
- Quick Actions: Update All (runs `uupd` via pkexec)
- OpsBar shows last update check result on mount

#### Updates screen (key `2`)
- Full-width image banner with cleaned bootc ref
- Staged-update alert bar when a reboot is pending
- Image metadata: signature status, compression type, stream/tag, last-updated date
- Update Components toggles: OS Image, Flatpaks, Homebrew (persisted to `/etc/uupd/config.json`)
- Update Schedule radio — Automatic / Notify only / Manual
- Reboot Strategy: Reboot on Logout toggle, Scheduled Window (2–4 AM + AC power), Manual
- **Update Now** — full multi-phase update: bootc → Flatpak + Homebrew + Distrobox in parallel
  with live layer/byte progress and OSC terminal progress bar
- **Check for Updates** button with live Homebrew count

#### Developer screen (key `3`)
- Cloud Native Development: Podman Desktop, Lima (WSL-equivalent), Incus, Docker
- Virtualization: virt-manager + QEMU
- Editors: VS Code, JetBrains Toolbox, Zed, VSCodium, Neovim, Helix
- Per-tool install detection on mount — buttons show "Installed ✓" for existing tools
- Streaming install progress via OpsBar with step counter
- One-click retry on failure

#### App-wide
- GNOME HIG–inspired AdwPreferencesGroup / AdwActionRow / AdwSwitchRow / AdwButtonRow widget library
- Live dark/light mode — follows GNOME color-scheme via `gsettings monitor`
- GNOME accent color integration (teal, blue, green, yellow, orange, red, pink, purple, slate)
- `AdwViewSwitcher` tab bar replaces sidebar — compact, keyboard-navigable
- `OpsBar` — unified progress/status bar with running/idle/confirm/complete/error states
- `RollbackCalendar` — date-picker widget for bootc rollback
- Command Palette (`Ctrl+P`): Update all, System report, Toggle developer mode, Open podman-tui
- Package search in Command Palette: Flatpak (Flathub) and Homebrew
- Global help overlay (`?`) with per-screen keybindings
- `bctl` short alias alongside `bluefinctl`
- `bctl update` headless CLI path with rich terminal output and OSC progress

### Technical
- Python 3.12+, Textual TUI framework
- Async-first: all system calls are non-blocking; UI never freezes
- `@work(exclusive=True)` throughout — no double-trigger races
- All business logic in `core/` with no Textual imports — fully unit-testable
- 97 tests, ruff + mypy (strict) clean
- Homebrew tap: `brew tap projectbluefin/bluefinctl && brew install bluefinctl`

---

[0.1.0]: https://github.com/projectbluefin/bluefinctl/releases/tag/v0.1.0
