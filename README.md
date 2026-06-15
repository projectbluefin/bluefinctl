# bluefinctl

> Keyboard-driven TUI control panel for [Bluefin OS](https://projectbluefin.io) --
> system identity, updates, developer tooling, and AI workstation management,
> all from one beautiful terminal dashboard.

Built on [Textual](https://textual.textualize.io/). Matches your GNOME accent color live.

![CI](https://github.com/projectbluefin/bluefinctl/actions/workflows/ci.yml/badge.svg)

---

## Install

```bash
brew trust --tap projectbluefin/bluefinctl && brew install bluefinctl
```

**What the formula installs:**
The formula uses Homebrew's `Language::Python::Virtualenv` helper -- it builds an
isolated Python 3.13 virtualenv under `$(brew --prefix)/opt/bluefinctl`, installs
`bluefinctl` and its dependencies (`textual`, `typer`, `rich`) into that virtualenv,
and symlinks `bctl` and `bluefinctl` into `$(brew --prefix)/bin`. No pre/post-install
hooks, no elevated-privilege scripts.

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
> The TUI runs anywhere; most core actions need a running Bluefin system.

---

## Usage

```bash
bctl                          # Launch TUI  (bctl is an alias for bluefinctl)
bctl --screen updates         # Jump to a screen on launch

# Headless subcommands -- scriptable, no TUI required
bctl status                   # Print system info
bctl update                   # Full system update: OS, Flatpak, Brew, Containers
bctl update --check           # Check for available updates, exit 0/1
bctl devmode on|off|status    # Toggle developer mode
```

---

## Screens

Navigate with the tab bar at the top (libadwaita AdwViewSwitcher style) or number keys **1-3**.

| # | Screen | What it does |
|---|--------|-------------|
| 1 | **System** | Image identity, GPU, health, rollback calendar, quick actions |
| 2 | **Updates** | Strategy, focus mode, channel switch, rollback, staged-update banner |
| 3 | **DX Mode** | Cloud-native tools, editors, containers, virtualization |
| 4 | **GDX Mode** | Nvidia/AMD/Intel stacks based on GPUs | 

---

## `bctl update` -- the geek-fest updater

Replaces `ujust update` with a beautiful terminal ceremony:

```
  ok  System Image    [====================]  19/19  3.2 GB  staged -- reboot when ready  0:05:43
  ok  Flatpak         [====================]   4/4   4 apps updated                       0:00:23
  ok  Homebrew        [====================]   1/1   2 formulae upgraded                  0:01:12
  ok  Containers      [====================]   1/1   already up to date                   0:00:03
```

- **bootc `--progress-fd`** -- machine-readable JSON layer progress: layer count and bytes transferred across all pulled layers
- **Parallel second phase** -- Flatpak, Brew, and Containers run concurrently after the OS image; each row resolves independently
- **Rich Progress bars** -- each task row updates in-place via cursor-up; no scroll, no mess, correct width on any terminal
- **OSC 9;4** -- progress bar in your terminal tab (Ghostty, Ptyxis, iTerm2, WezTerm)
- **OSC title** -- tab title tracks the current stage

---

## Architecture

```
src/bluefinctl/
├── app.py               Textual App -- screens, theme, keybinds
├── cli.py               Typer CLI -- headless path for every operation
├── core/                Business logic -- NO Textual imports, fully testable
│   ├── updates.py       bootc status, strategy, focus mode, reboot
│   ├── update_runner.py bctl update orchestration (bootc + parallel stages)
│   ├── update_app.py    Rich Progress CLI renderer for bctl update
│   ├── devmode.py       developer tooling, Lima, group management
│   ├── brew.py          Brewfile management
│   ├── flatpak.py       Flatpak search/install
│   └── ai.py            GPU-accelerated stack management
├── screens/             One Screen per panel (system, updates, devmode, ai)
├── widgets/             adw.py (HIG library), ops_bar.py, rollback_calendar.py
├── theme/               GNOME accent color reader + bluefin.tcss
└── util/                OSC escape sequences, Ghostty detection
```

**Strict separation:** all subprocess calls, file I/O, and system state live in `core/`.
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

1. Read `AGENTS.md` -- it has the full operating contract, PR rules, and human gates
2. Pick an issue labeled `queue/agent-ready`
3. Branch from `main`, use [Conventional Commits](https://www.conventionalcommits.org/)
4. `pytest && ruff check src/ tests/ && mypy src/` must pass before requesting review
5. One PR per feature. No WIP PRs.

### Maintainers

See [AGENTS.md](AGENTS.md) for the full agent and human operating contract.
PRs require review from [@projectbluefin/maintainers](https://github.com/orgs/projectbluefin/teams/maintainers).

---

## Docs

| File | Contents |
|------|---------|
| [AGENTS.md](AGENTS.md) | Full agent/copilot operating contract, PR rules, and human gates |
| [docs/DESIGN.md](docs/DESIGN.md) | Architecture and screen design decisions |
| [docs/UPDATES.md](docs/UPDATES.md) | Update management internals |
| [docs/skills/](docs/skills/) | Per-area skill files for AI-driven development |

---

## License

[MIT](LICENSE)
