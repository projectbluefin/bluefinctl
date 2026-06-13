# bluefinctl

> Unified TUI control panel for Bluefin OS — system identity, updates, developer tooling, and AI workstation management from one keyboard-driven dashboard.

Built on [Textual](https://textual.textualize.io/). Matches your GNOME accent color live. Terminal title: **Bluefin Control Center**.

## Install

```bash
brew install ublue-os/tap/bluefinctl
```

## Usage

```bash
bluefinctl              # Launch TUI (defaults to System screen)
bluefinctl --screen updates   # Jump to a specific screen

# Headless subcommands (no TUI)
bluefinctl status       # System info
bluefinctl update       # Trigger uupd now
bluefinctl devmode on|off|status
bluefinctl kit list|install <name>
bluefinctl ai list|deploy <stack>|stop <stack>
```

## Screens

Navigation: horizontal tab bar at the top (libadwaita AdwViewSwitcher). Number keys **1–5** switch screens instantly.

| # | Screen | What it does |
|---|--------|-------------|
| 1 | **System** | Image identity, GPU, health checks, quick actions |
| 2 | **Updates** | Strategy, per-layer toggles, focus mode + snooze, channel switch, rollback, release notes |
| 3 | **Toolkit** | Kit management — activate/deactivate Brewfile-based tool collections |
| 4 | **DevMode** | Developer mode toggle, tool install status, Lima VM setup |
| 5 | **AI** | GPU-accelerated stack deploy/stop/logs, AI tool inventory |

## Features

- **GNOME Theming** — reads your accent color and color-scheme, applies live across the entire UI
- **Unified Progress** — every subprocess (brew, podman, bootc, lima) runs behind the same progress bar and collapsible log
- **Focus Mode + Snooze** — pause all updates indefinitely or for 1h / until tonight / until tomorrow morning
- **Channel Management** — switch stable ↔ testing with confirmation; roll back with one action
- **Lima WSL-equivalent** — guided 4-step setup wizard (KVM preflight → install → start VM → verify)
- **Command Palette** — `Ctrl+P` for package search (brew + flatpak), navigation, and actions
- **Headless CLI** — every TUI action has a scriptable `bluefinctl <subcommand>` path
- **OSC 9;4 progress** — progress appears in Ghostty/Ptyxis/iTerm2 tab/titlebar during operations

## Architecture

```
src/bluefinctl/
├── app.py          Textual App — screen registration, theme switching, Command Palette
├── cli.py          Typer CLI entry point (headless path for every operation)
├── core/           Business logic — NO Textual imports, fully testable
├── screens/        One Screen subclass per panel + ViewSwitcher + modals
├── widgets/        adw.py (HIG widget library) + operation_modal.py + changelog.py
├── theme/          GNOME accent color reader + bluefin.tcss
└── util/           OSC escape sequences (progress + title), Ghostty detection, terminal launcher
```

**Rule:** All subprocess calls, file I/O, and system state live in `core/`. Screens only call core functions and present results. Every operation has both a headless CLI path and a TUI path.

## Development

```bash
git clone https://github.com/projectbluefin/bluefinctl
cd bluefinctl
pip install -e ".[dev]"

textual run --dev src/bluefinctl/app.py   # hot-reload CSS
pytest                                     # 43 tests
ruff check src/ tests/
mypy src/
```

## Design

See [docs/DESIGN.md](docs/DESIGN.md) for the full architecture and screen designs.  
See [docs/UPDATES.md](docs/UPDATES.md) for update management internals.

## License

MIT
