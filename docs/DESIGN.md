# bluefinctl — Design Document

## Overview

`bluefinctl` is the unified TUI control panel for Bluefin OS. Built on [Textual](https://textual.textualize.io/), it replaces the scattered `ujust` + `gum` interactions with a persistent, keyboard-driven dashboard inspired by lazydocker.

**Replaces:** bbrew (bold-brew), devmode toggle scripts, update toggle scripts, various ujust one-shots.

**Does NOT replace:** finupdate (graphical update progress), control-center (GTK settings), ujust (backward compat layer).

## Invocation

```bash
bluefinctl              # Full TUI dashboard
bluefinctl brew         # Jump to brew screen
bluefinctl update       # Trigger update (non-interactive)
bluefinctl update --check  # Check for updates only
bluefinctl devmode      # Toggle devmode
bluefinctl ai           # AI stack management
bluefinctl status       # One-shot system status (scriptable)
```

Every subcommand works headless (no TUI) for scripting/CI. The TUI is the default interactive mode.

---

## Architecture

```
bluefinctl/
├── src/bluefinctl/
│   ├── __main__.py           # `python -m bluefinctl` entry
│   ├── cli.py                # Typer CLI entry point
│   ├── app.py                # Textual App, screen routing, keybinds
│   ├── core/                 # Business logic (TUI-independent, testable)
│   │   ├── brew.py           # Brewfile parser, bundle operations
│   │   ├── system.py         # image-info, GPU detection, bootc status
│   │   ├── updates.py        # uupd config, systemd timer management
│   │   ├── devmode.py        # Developer mode toggle logic
│   │   ├── containers.py     # Podman pod/quadlet management
│   │   └── ai.py             # AI stack deployment (nvidia/amd)
│   ├── screens/
│   │   ├── dashboard.py      # System health overview + quick actions
│   │   ├── brew.py           # Package management (Brewfile layers)
│   │   ├── updates.py        # Update strategy + settings
│   │   ├── containers.py     # Running pods/containers status
│   │   ├── ai.py             # AI workspace management (v2)
│   │   └── settings.py       # Devmode, testing channel, preferences
│   ├── widgets/
│   │   ├── status_bar.py     # Bottom bar: image version, GPU, uptime
│   │   ├── progress.py       # OSC 9;4 aware multi-step progress
│   │   ├── brewfile_tree.py  # Layered Brewfile view (system/user)
│   │   ├── service_card.py   # Systemd service status card
│   │   └── gpu_badge.py      # GPU type + VRAM indicator
│   ├── theme/
│   │   ├── accent.py         # GNOME accent color reader
│   │   └── bluefin.tcss      # Textual CSS stylesheet
│   └── util/
│       ├── osc.py            # Terminal escape sequences (OSC 9;4, etc.)
│       ├── ghostty.py        # Ghostty-specific features
│       └── subprocess.py     # Async subprocess helpers
├── tests/
│   ├── test_brew.py
│   ├── test_updates.py
│   └── snapshots/            # Textual SVG snapshot tests
├── pyproject.toml
├── README.md
└── docs/
    ├── DESIGN.md             # This file
    └── UPDATES.md            # Update panel deep-dive
```

---

## Screens

### 1. Dashboard (home)

The landing screen. At-a-glance system health.

```
┌─────────────────────────────────────────────────────────────┐
│  🐟 bluefinctl                              bluefin:41-stable │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                   │
│ ● System │  ╭─ System ──────────────────────────────╮       │
│   Brew   │  │ Image: bluefin-dx:41-stable           │       │
│   Update │  │ Boot:  Current (deployed 2h ago)      │       │
│   Pods   │  │ GPU:   NVIDIA RTX 4090 (24GB VRAM)   │       │
│   AI     │  │ Mode:  Developer                      │       │
│   Config │  ╰───────────────────────────────────────╯       │
│          │                                                   │
│          │  ╭─ Updates ─────────────────────────────╮       │
│          │  │ Strategy: Automatic                    │       │
│          │  │ OS Image: ✓ Current                    │       │
│          │  │ Flatpaks: ⟳ 3 updates available       │       │
│          │  │ Brew:     ✓ Current (42 packages)     │       │
│          │  ╰───────────────────────────────────────╯       │
│          │                                                   │
│          │  ╭─ Quick Actions ───────────────────────╮       │
│          │  │ [u] Update All  [d] Devmode  [r] Report│      │
│          │  ╰───────────────────────────────────────╯       │
│          │                                                   │
├──────────┴──────────────────────────────────────────────────┤
│ q:quit  ?:help  /:search  Tab:navigate  Enter:select        │
└─────────────────────────────────────────────────────────────┘
```

### 2. Brew Screen

Replaces bbrew. Shows layered Brewfile with provenance.

```
┌─ Packages ──────────────────────────────────────────────────┐
│ Filter: [___________]                    42 installed / 3 pending │
├─────────────────────────────────────────────────────────────┤
│ ☑ bat          🏭 system    A cat clone with wings          │
│ ☑ eza          🏭 system    Modern ls replacement           │
│ ☑ fd           🏭 system    Simple find alternative         │
│ ☑ ripgrep      👤 user      Fast grep                       │
│ ☑ lazygit      👤 user      Terminal UI for git             │
│ ☐ neovim       👤 disabled  (removed from base)            │
│                                                              │
│ ── Casks ──                                                  │
│ ☑ 1password    👤 user      Password manager               │
├─────────────────────────────────────────────────────────────┤
│ [a]dd  [r]emove  [u]pgrade all  [s]earch  [B]rewfile edit   │
└─────────────────────────────────────────────────────────────┘
```

Provenance:
- 🏭 **system** — shipped in `/usr/share/ublue-os/homebrew/*.Brewfile` (read-only)
- 👤 **user** — added to `~/.config/bluefin/Brewfile`
- ❌ **disabled** — user removed a system package via blocklist

### 3. Updates Screen

Direct interface with uupd. See [UPDATES.md](./UPDATES.md) for deep-dive.

### 4. Containers Screen

Podman pod/container status. Light management.

```
┌─ Pods & Containers ─────────────────────────────────────────┐
│                                                              │
│ ▼ pod/ai-workspace          Running    3 containers         │
│   ├─ jupyter-lab            Running    ↑ 4h    8080→8080    │
│   ├─ ollama                 Running    ↑ 4h    11434→11434  │
│   └─ open-webui             Running    ↑ 4h    3000→3000    │
│                                                              │
│ ▼ pod/dev-services          Running    2 containers         │
│   ├─ postgres               Running    ↑ 12h   5432→5432    │
│   └─ redis                  Running    ↑ 12h   6379→6379    │
│                                                              │
│ ▶ pod/media (stopped)       Exited     3 containers         │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│ [s]tart  [S]top  [r]estart  [l]ogs  [p]ull updates         │
└─────────────────────────────────────────────────────────────┘
```

### 5. AI Screen (v2)

Centralized hub for AI stack management on systems with GPU.

### 6. Settings Screen

Devmode toggle, testing channel, preferences.

---

## Update Management (uupd Integration)

### Philosophy

bluefinctl is a **policy UI** over uupd — it doesn't replace the daemon, it configures it and provides UX around its operations.

### Strategy Selector

| Strategy | Behavior | uupd State |
|----------|----------|------------|
| **Automatic** (default) | uupd handles everything silently | timer enabled, all modules active |
| **Notify** | Download + stage, notify user to reboot | timer enabled, `notify-only: true` |
| **Manual** | Only update when user triggers | timer disabled |
| **Scheduled** | Update in a specific window | timer with custom `OnCalendar=` |

### Per-Layer Control

Each layer independently toggleable:
- **OS Image** (bootc) — auto / manual / pinned
- **Flatpaks** — auto / manual
- **Brew** — auto / manual / weekly-only

Maps to uupd config `modules.*.disable` fields.

### Focus Mode 🎯

The killer feature for developers and AI users:

> "Don't touch anything until I say so."

One toggle that:
1. Masks `uupd.timer`
2. Shows a persistent indicator in the status bar
3. Optionally auto-expires after N hours (configurable)
4. Reminds user after 7 days if still active

Use cases:
- Mid-training run (don't restart GPU containers)
- Demo day (don't change anything)
- Deep work session (no reboot prompts)

### Deferral (Snooze)

When an update is available and strategy is "Notify":
- **1 hour** — mask timer, schedule one-shot unmask
- **Tonight** — unmask at 2 AM
- **Tomorrow** — unmask in 24h
- **Skip this version** — add current target to skip list until next release

### Channel Management

```
Stable (recommended)     ← ghcr.io/projectbluefin/bluefin:latest
Testing                  ← ghcr.io/projectbluefin/bluefin:testing
Pinned: 41-20240601      ← ghcr.io/projectbluefin/bluefin:41-20240601
```

Channel switch = `bootc switch --target <ref>`. Gated with confirmation dialog explaining implications.

### Rollback

Read from `bootc status --json`:
- Show current + previous deployment
- One-action rollback: `bootc rollback`
- Mark current as "known good" (informational badge)

### Health Checks (post-update)

After a new boot into a new deployment, bluefinctl runs lightweight checks:
- GPU driver loaded? (`nvidia-smi` / `rocm-smi` exit code)
- systemd services healthy? (no failed units in user slice)
- Brew still linked? (`brew doctor` exit code)
- Display results on dashboard with ✓/⚠/✗

---

## Theming

### GNOME Accent Color Integration

Read at startup:
```python
gsettings get org.gnome.desktop.interface accent-color
```

Map to hex (same table as brewlove), inject as CSS variable:

```css
/* bluefin.tcss */
$accent: #62a0ea;  /* overridden at runtime */

Screen {
    background: $surface;
}

.sidebar--highlight {
    background: $accent;
}

ProgressBar > .bar--complete {
    color: $accent;
}
```

Optionally watch live with `gsettings monitor` for real-time theme changes.

### Terminal Integration

- **OSC 9;4** — Progress in terminal tab/titlebar (Ghostty, Ptyxis, iTerm2)
- **OSC 8** — Clickable hyperlinks in log output
- **Ghostty** — Detect via `$TERM_PROGRAM=ghostty`, enable Kitty keyboard protocol for enhanced keybinds
- **systemd TTY progress** — When running headless, emit `sd_notify` style progress for integration with systemd journal

---

## Distribution

```toml
# pyproject.toml
[project]
name = "bluefinctl"
requires-python = ">=3.12"
dependencies = [
    "textual>=1.0,<2.0",
    "typer>=0.12",
    "rich>=13.0",
]

[project.scripts]
bluefinctl = "bluefinctl.cli:app"
```

Install via:
```bash
brew install ublue-os/tap/bluefinctl
# or
pipx install bluefinctl
```

**No RPMs.** This is a userspace tool in the Homebrew/pipx layer.

---

## Textual Long-Term Assessment

### Strengths for bluefinctl

| Feature | Value for Us |
|---------|-------------|
| CSS theming | Live accent color, theme variants without code changes |
| Widget library | DataTable, Tree, TabbedContent, ProgressBar, RichLog — all needed |
| Workers API | Async subprocess management for brew/podman/bootc |
| Command Palette | Ctrl+P discoverability for all actions |
| Snapshot testing | SVG renders for automated UI regression tests |
| Screen system | Natural multi-page navigation |
| Hot-reload CSS | Fast iteration on design |

### Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Textualize pivots/abandons | Low | MIT licensed, large community, can fork |
| API churn between versions | Medium | Pin to `>=1.0,<2.0`, test on upgrade |
| Python startup latency | Low | ~300ms acceptable for a dashboard app |
| Python on immutable OS | Medium | Ship via brew (manages its own Python) |
| Missing widget | Low | Textual supports custom widgets easily |

### Comparison to charm.sh (Bubbletea/Lipgloss/Gum)

| Dimension | Textual | Charm.sh ecosystem |
|-----------|---------|-------------------|
| Layout | CSS-based, automatic | Manual coordinate math |
| Theming | CSS variables, hot-reload | Code changes required |
| Widgets | 30+ built-in | ~10 in Bubbles, build the rest |
| Testing | Snapshot + pilot automation | Manual testing |
| Language | Python | Go |
| Binary size | Needs runtime (brew Python) | Single static binary |
| Dashboard suitability | Excellent (built for this) | Possible but painful |
| Startup time | ~300ms | ~50ms |
| AI integration | textual-ai, native Python | External process |

**Verdict:** Textual wins decisively for a multi-panel dashboard. Bubbletea is better for single-purpose tools (which is why brewlove works). For the "lazydocker for bluefin" vision, Textual is the right choice.

### Bling Opportunities

- **Sparkline widgets** — CPU/GPU/memory mini-graphs in dashboard header
- **Rich markdown** — Help screens rendered with full formatting
- **Animated transitions** — Screen push/pop with slide animations
- **Toast notifications** — "Update available" popups
- **Color gradients** — Progress bars with accent→complement gradient
- **ASCII art header** — Bluefin fish logo in the sidebar (small, tasteful)

---

## v1 Scope

Ship with:
1. ✅ Dashboard (system info + health)
2. ✅ Brew management (layered Brewfile, search, add/remove, upgrade)
3. ✅ Update settings (strategy, per-layer, focus mode, channel)
4. ✅ Container status (read-only pod listing)
5. ✅ Settings (devmode toggle, testing channel)
6. ✅ GNOME accent color theming
7. ✅ OSC 9;4 progress integration
8. ✅ Headless CLI for all operations

Defer to v2:
- AI stack management screen
- AI assistant integration (textual-ai)
- Container lifecycle management (start/stop/pull)
- Podman pod composition wizard
- Health check automation
- Update history/changelog viewer
