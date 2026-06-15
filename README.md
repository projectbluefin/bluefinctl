# bluefinctl

> Keyboard-driven TUI control panel for [Bluefin OS](https://projectbluefin.io) —
> system identity, updates, developer tooling, and AI workstation management
> from one terminal dashboard.

Built on [Textual](https://textual.textualize.io/). Matches your GNOME accent color live.

![CI](https://github.com/projectbluefin/bluefinctl/actions/workflows/ci.yml/badge.svg)

---

## Install

```bash
brew trust --tap projectbluefin/bluefinctl && brew tap projectbluefin/bluefinctl && brew install bluefinctl
```

The formula builds an isolated Python 3.13 virtualenv and symlinks `bctl` and `bluefinctl`
into `$(brew --prefix)/bin`. No elevated-privilege scripts.

You can read the formula at
[`bluefinctl.rb`](https://github.com/projectbluefin/homebrew-bluefinctl/blob/main/bluefinctl.rb)
before tapping.

### From source

```bash
git clone https://github.com/projectbluefin/bluefinctl
cd bluefinctl
pip install -e .
```

> **Requirements:** Python >= 3.13, Linux, a bootc-managed system (Bluefin, Aurora, uCore...).
> The TUI runs anywhere; most actions require a running Bluefin system.

---

## Usage

```bash
bctl                          # Launch TUI  (bctl is the short alias)
bctl --screen updates         # Jump to a specific screen on launch

# Headless subcommands — scriptable, no TUI required
bctl status                   # Print system info
bctl update                   # Full system update: OS, Flatpak, Brew, Containers
bctl update --check           # Check for available updates, exit 0/1
bctl devmode on|off|status    # Toggle developer mode groups
```

---

## Screens

Navigate with the tab bar at the top or number keys **1–3**.

| # | Screen | What it does |
|---|--------|-------------|
| 1 | **System** | Image, channel, boot status · hostname, GPU · health checks · Update All, Testing stream toggle, rollback calendar |
| 2 | **Updates** | Update strategy, focus mode, staged-update banner, schedule |
| 3 | **Developer** | Developer mode toggle (groups, reboot required) · cloud-native tools, editors, virtualization (no reboot) |
| 4 | **AI** | Nvidia/AMD/Intel GPU stack management — only shown when a GPU is detected |

---

## `bctl update` — the full-system updater

```
  ok  System Image    [====================]  19/19  3.2 GB  staged — reboot when ready  0:05:43
  ok  Flatpak         [====================]   4/4   4 apps updated                       0:00:23
  ok  Homebrew        [====================]   1/1   2 formulae upgraded                  0:01:12
  ok  Containers      [====================]   1/1   already up to date                   0:00:03
```

- **bootc `--progress-fd`** — machine-readable JSON layer progress
- **Parallel second phase** — Flatpak, Brew, and Containers run concurrently after the OS image
- **Rich Progress bars** — each task row updates in-place; correct width on any terminal
- **OSC 9;4** — progress indicator in your terminal tab (Ghostty, Ptyxis, WezTerm)

---

## Architecture

```
src/bluefinctl/
├── app.py               Textual App — screens, theme, keybinds
├── cli.py               Typer CLI — headless path for every operation
├── core/                Business logic — NO Textual imports, fully testable
│   ├── updates.py       bootc status, strategy, focus mode, reboot
│   ├── update_runner.py bctl update orchestration (bootc + parallel stages)
│   ├── devmode.py       developer tooling, Lima, group management
│   ├── brew.py          Brewfile management
│   ├── flatpak.py       Flatpak search/install
│   └── ai.py            GPU-accelerated stack management
├── screens/             One Screen per panel (system, updates, devmode, ai)
├── widgets/             adw.py (HIG library), ops_bar.py, rollback_calendar.py
├── theme/               GNOME accent color reader + bluefin.tcss
└── util/                OSC escape sequences, Ghostty detection
```

All subprocess calls, file I/O, and system state live in `core/`.
Screens only call core functions and render results. Every action has both a CLI and TUI path.

---

## Development

```bash
git clone https://github.com/projectbluefin/bluefinctl
cd bluefinctl
pip install -e ".[dev]"

just run          # reinstalls editable + launches bctl
just dev          # hot-reload CSS (textual run --dev)
pytest            # full test suite
ruff check src/ tests/
mypy src/
```

### Contributing

1. Read `AGENTS.md` — full operating contract, PR rules, and human gates
2. Pick an issue labeled `queue/agent-ready`
3. Branch from `main`, use [Conventional Commits](https://www.conventionalcommits.org/)
4. `pytest && ruff check src/ tests/ && mypy src/` must pass before requesting review
5. One PR per feature. No WIP PRs.

PRs require review from [@projectbluefin/maintainers](https://github.com/orgs/projectbluefin/teams/maintainers).

---

## Docs

| File | Contents |
|------|---------|
| [AGENTS.md](AGENTS.md) | Agent/copilot operating contract, PR rules, human gates |
| [docs/DESIGN.md](docs/DESIGN.md) | Architecture and screen design decisions |
| [docs/skills/](docs/skills/) | Per-area skill files for AI-driven development |

---

## License

[MIT](LICENSE)
