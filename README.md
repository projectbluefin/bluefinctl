# bluefinctl

> TUI control panel for Bluefin OS — manage packages, updates, containers, and developer mode from one keyboard-driven dashboard.

Built on [Textual](https://textual.textualize.io/). Replaces scattered `ujust` + `gum` interactions with a persistent, themed interface that matches your GNOME accent color.

![bluefinctl](docs/screenshot-placeholder.png)

## Install

```bash
brew install ublue-os/tap/bluefinctl
```

## Usage

```bash
bluefinctl              # Launch full TUI dashboard
bluefinctl brew         # Package management
bluefinctl update       # Trigger system update
bluefinctl status       # System status (scriptable, no TUI)
bluefinctl devmode      # Toggle developer mode
```

## Features

- **📦 Brew Management** — Layered Brewfile system (system + user), search, add/remove, bulk upgrade with progress
- **🔄 Update Control** — Strategy selector (auto/notify/manual/scheduled), per-layer toggles, Focus Mode for uninterrupted work
- **🐳 Container Status** — Podman pod health, running containers, quick actions
- **🛠️ Developer Mode** — One-toggle devmode with clear status indicator
- **🎨 GNOME Theming** — Reads your accent color, applies it live across the entire UI
- **📊 System Health** — GPU status, deployment info, post-update health checks
- **⌨️ Keyboard-First** — Vim-style navigation, command palette (Ctrl+P), quick actions

## Architecture

```
bluefinctl reads/writes to:
├── uupd (update daemon)         — /etc/uupd/config.json + systemd timers
├── bootc (image updates)        — bootc status/switch/rollback
├── Homebrew (packages)          — Brewfile layers + brew bundle
├── Podman (containers)          — pod/container status + lifecycle
└── GNOME (theming)              — gsettings accent-color
```

No RPMs. No layered packages. Everything runs in userspace via Homebrew or containers.

## Development

```bash
# Clone and setup
git clone https://github.com/projectbluefin/bluefinctl
cd bluefinctl
pip install -e ".[dev]"

# Run in dev mode (hot-reload CSS)
textual run --dev src/bluefinctl/app.py

# Run tests
pytest

# Lint
ruff check src/ tests/
mypy src/
```

## Design

See [docs/DESIGN.md](docs/DESIGN.md) for the full architecture and screen designs.

See [docs/UPDATES.md](docs/UPDATES.md) for the update management deep-dive.

## License

MIT
