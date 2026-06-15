# bluefinctl — Design Document

## Overview

`bluefinctl` is the unified TUI control panel for Bluefin OS. Built on [Textual](https://textual.textualize.io/), it replaces scattered `ujust` + `gum` interactions with a persistent, keyboard-driven dashboard. It is the single pane of glass for system identity, updates, developer tooling, and AI workstation management.

**Design philosophy:** An operating system control panel that feels like it was designed for the GNOME desktop. Clean, classy, consistent. Every subprocess operation (brew, podman, bootc) is unified behind the same progress bars and visual language. No ugly terminal output leaks through.

**Replaces:** bbrew (bold-brew), `ujust devmode`, `ujust aimode`, `ujust dx-group`, update toggle scripts, various ujust one-shots.

**Does NOT replace:** Bazaar (Flatpak app store), GNOME Control Center (GTK settings), ujust (backward compat layer stays), podman-tui (full container management).

---

## Invocation

```bash
# TUI mode (interactive)
bluefinctl                    # Full TUI, System screen
bluefinctl system             # Jump to System screen
bluefinctl updates            # Jump to Updates screen
bluefinctl toolkit            # Jump to Toolkit screen
bluefinctl devmode            # Jump to DevMode screen
bluefinctl ai                 # Jump to AI screen

# Headless mode (scriptable, no TUI)
bluefinctl status             # One-shot system info (JSON output)
bluefinctl update             # Trigger update now
bluefinctl update --check     # Check for updates only
bluefinctl focus on [--hours=N]   # Enable focus mode
bluefinctl focus off              # Disable focus mode
bluefinctl kit install <name>     # Install a kit
bluefinctl kit list               # List kits and status
bluefinctl install <source>:<pkg> # Install package (brew:ripgrep, flatpak:org.gimp.GIMP)
bluefinctl ai deploy <stack>      # Deploy an AI stack
bluefinctl ai list                # List available/running stacks
bluefinctl ai stop <stack>        # Stop a running stack
bluefinctl devmode on|off         # Toggle developer mode

# Compatibility aliases (old commands map forward)
bluefinctl brew       -> bluefinctl toolkit
bluefinctl bundles    -> bluefinctl toolkit
```

Every subcommand works headless (no TUI) for scripting/CI. The TUI is the default interactive mode. JSON output uses `--json` flag; otherwise output is human-readable Rich text.

---

## Architecture

```
src/bluefinctl/
├── __main__.py              # python -m bluefinctl entry
├── cli.py                   # Typer CLI entry point (headless path for every operation)
├── app.py                   # Textual App: screen registration, theme switching, Command Palette
├── core/                    # Business logic — NO Textual imports, fully testable
│   ├── system.py            # image-info, GPU detection, bootc status
│   ├── updates.py           # uupd config, systemd timer management, focus mode state machine
│   ├── bundles.py           # Kit/bundle discovery, install/remove, Brewfile layer management
│   ├── devmode.py           # Developer mode: groups, runtime health, Lima lifecycle
│   ├── ai.py                # AI stack: discovery, preflight, deploy, lifecycle
│   ├── progress.py          # ProgressParser protocol, per-tool parsers
│   └── operations.py        # Resumable operation state machine (for reboot-required flows)
├── screens/
│   ├── system.py            # System health overview + quick actions (AdwPropertyRow/AdwButtonRow)
│   ├── updates.py           # Update strategy, focus, layers, channel, rollback (AdwSwitchRow etc.)
│   ├── toolkit.py           # Kit management — list + scrollable detail pane
│   ├── devmode.py           # Developer experience (TabbedContent: Overview/Tools/Environments)
│   ├── ai.py                # AI workstation (TabbedContent: Stacks/Tools)
│   ├── _viewswitcher.py     # Horizontal top-navigation bar (libadwaita AdwViewSwitcher)
│   └── _modals.py           # Shared modals: confirm, input, operation log, help
├── widgets/
│   ├── adw.py               # GNOME HIG widget library (AdwPreferencesGroup, AdwSwitchRow, etc.)
│   ├── operation_modal.py   # Unified progress: title + ProgressBar + collapsible log
│   └── log_view.py          # Scrollable log widget
├── theme/
│   ├── accent.py            # GNOME gsettings reader: accent color + color-scheme + build_theme()
│   └── bluefin.tcss         # Textual CSS (structural rules only — colors from Theme object)
└── util/
    ├── osc.py               # OSC 9;4 progress, OSC 8 hyperlinks
    ├── ghostty.py           # Ghostty detection
    └── terminal.py          # Launch external apps (podman-tui) in new terminal
```

### Key Architectural Rules

1. **All subprocess calls, file I/O, and system state live in `core/`.** Screens only call core functions and present results.
2. **Every operation has a headless CLI path (`cli.py`) and a TUI path (screens).** They share the same core functions.
3. **Unified progress for all operations.** No raw subprocess output shown to users. Every tool gets a `ProgressParser` that extracts progress where possible.
4. **GNOME HIG widget library.** All screens use `widgets/adw.py` — never raw `Static` + border layout. See `docs/skills/textual-dev.md` for the full widget reference.
5. **Live dark/light mode.** The app watches `gsettings monitor org.gnome.desktop.interface` and hot-switches between `bluefin-dark` and `bluefin-light` themes. TCSS never hardcodes color variables.
6. **Resumable operations.** Operations requiring reboot/logout persist state to `~/.local/state/bluefinctl/operations.json` and resume on next launch.

### Theme System

```
GNOME gsettings color-scheme → build_theme(scheme, accent) → Textual Theme
                                     ↑
           gsettings monitor stream ─┘ (live, no restart needed)

bluefin-dark:  Dark 4/3/2 palette   #241f31 / #3d3846 / #5e5c64
bluefin-light: Light 2/1/3 palette  #f6f5f4 / #ffffff / #deddda
```

### State Management

```
User action
  -> Screen dispatches to core/ function
    -> core/ returns progress updates via async generator
      -> Screen feeds updates to OperationModal widget
        -> OperationModal drives ProgressBar + optional log
          -> OSC 9;4 emitted in parallel for terminal integration
```

### Update Policy State Machine

Precedence (highest wins):
1. **Focus Mode** — masks uupd.timer entirely, stores previous strategy
2. **Snooze** — temporary mask with scheduled unmask
3. **Strategy** — Automatic/Notify/Manual/Scheduled
4. **Per-layer** — OS Image/Flatpaks/Brew independently disabled
5. **Channel/pin** — which image ref to track

Disabling Focus/Snooze restores the exact previous strategy state, not "enable timer."

### Resumable Operations

Operations that require reboot/logout use a state machine:

```
States: preflight -> executing -> needs-relogin -> needs-reboot
        -> pending-verification -> complete | failed

Persisted to: ~/.local/state/bluefinctl/operations.json
On next launch: check for pending operations, resume verification
```

Used by: Lima setup (KVM group), devmode enable (group changes), bootc switch/rollback.

---

## Screens

### Navigation

Five screens in a horizontal `ViewSwitcher` bar at the top of every screen (libadwaita `AdwViewSwitcher` pattern):

```
  System   Updates   Toolkit   DevMode   AI
 ─────────────────────────────────────────
```

Number keys 1-5 switch screens instantly. Tabs are clickable. Active tab has an accent-colored background tint.

### Platform Detection

bluefinctl ships via Homebrew and can run on any Linux (or macOS/WSL via `bluefin-cli`). Navigation is always stable: System, Updates, Toolkit, DevMode, and AI are installed and shown with keys 1-5 on every platform.

On non-bootc/non-Universal Blue systems, platform-specific panels remain visible but degrade in-place:

- **System screen** explains that bootc identity/status/rollback are unavailable.
- **Updates screen** explains that uupd/bootc update policy controls are unavailable.
- Toolkit, DevMode, and AI remain fully reachable at the same keys.
- Default home screen remains System unless a start screen is explicitly provided.

Detection still checks for `/run/ostree-booted` or `bootc status` exit code. The result controls panel content and warnings, not whether screens exist.

---

### 1. System (home)

The landing screen. `AdwPreferencesGroup` rows for identity, hardware, health, and quick actions. On non-bootc systems, bootc-specific rows show "unavailable" in-place.

**Groups:**

| Group | Widgets |
|-------|---------|
| System | Full image ref, boot status, hostname — `AdwPropertyRow` × 3 |
| Hardware | GPU model + VRAM, devmode status — `AdwPropertyRow` × 2 |
| Health | GPU driver, system services, Homebrew — `AdwPropertyRow` × 3 |
| Active Kits | Kit names summary — `AdwPropertyRow` |
| Quick Actions | Update All (primary), Devmode, Report, podman-tui — `AdwButtonRow` × 4 |

**Keybindings:** `u` update, `d` devmode, `r` report, `c` podman-tui

---

### 2. Updates

Update policy management. Single-column `ScrollableContainer`, five `AdwPreferencesGroup` sections.
Dangerous operations (channel switch, rollback) require a confirmation modal.

**Groups:**

| Group | Widgets | What it does |
|-------|---------|------|
| Update Strategy | `AdwComboRow`: Automatic / Notify / Manual | Sets uupd timer policy immediately |
| Update Layers | `AdwSwitchRow` × 3: OS Image, Flatpaks, Homebrew | Writes `/etc/uupd/config.json` via pkexec |
| Focus Mode | `AdwSwitchRow` + `AdwButtonRow` × 3: Snooze 1h / Tonight / Tomorrow | Masks/unmasks uupd.timer; snooze sets a timed expiry |
| Channel | `AdwPropertyRow` (current) + `AdwButtonRow` × 2 (stable/testing/update) | `bootc switch` after confirmation |
| Rollback | `AdwPropertyRow` (previous) + `AdwButtonRow` destructive | `bootc rollback` after confirmation |
| Release Notes | `ChangelogViewer` | Reads `/usr/share/ublue-os/changelog.md` or fetches from image tag |

**Not yet implemented:**
- Scheduled strategy time-picker

**Keybindings:** `s` stable, `t` testing, `u` update now, `R` rollback

---

### 3. Toolkit

Software kit management. Two-column layout: kit list (left) + detail pane (right).

Kit list shows use-case oriented collections:

```
  Terminal Experience     17 tools    [active]
  AI & ML Tools          24 tools    [active]
  Code Editors           12 tools    [3/12]
  Kubernetes             12 tools    [available]
  Cloud Native           89 tools    [available]
  Fonts                  12 fonts    [active]
  Swift                   3 tools    [available]
```

Select a kit -> detail pane shows:
- Description (what use case it solves)
- Full package list with install status
- Total disk usage estimate
- Activate/Deactivate action
- For deactivation: preview of packages to be removed (distinguish kit-owned vs shared)

**Kit sources:** Read from `/usr/share/ublue-os/homebrew/*.Brewfile`. Each Brewfile is one kit. Kit metadata (name, description, category) derived from filename and optional header comments.

**Interactions:**
- Arrow keys / j,k — navigate kit list
- Enter — activate or deactivate selected kit (confirmation for deactivate)
- r — refresh kit state
- Ctrl+P — open Command Palette for individual package search/install

---

### 4. DevMode

The developer experience panel. This IS the DX mode — no separate image required. TabbedContent with 3 tabs.

**Tab: Overview**

| Card | Content |
|------|---------|
| Status | "Developer Mode: ACTIVE" or setup prompt if groups not configured |
| Runtime Health | Docker: `[ok]` / Podman: `[ok]` / Lima: `[--] not set up` |
| Quick Actions | `[c]` podman-tui, `[v]` VSCode, `[l]` Lima shell |

Group management (docker/mock/lxd/incus-admin) is handled silently during "Enable Developer Mode" — the user doesn't see group commands, just a progress bar and "log out to apply."

**Tab: Tools**

ListView of developer tools with install status:

```
 -- Dev Tools --
  [ok] podman-compose    Container orchestration
  [ok] dive              Container layer explorer
  [ok] kind              Local Kubernetes
  [--] devcontainer      Devcontainer CLI (not installed)

 -- Performance --
  [ok] sysprof           System profiler
  [ok] bcc              BPF compiler collection
  [--] bpftrace         (not installed)

 -- Virtualization --
  [ok] QEMU/KVM         Hardware virtualization
  [--] Incus            Container/VM manager (not installed)
```

Actions: Select tool + Enter to install. `[a]` install all missing. Tools are sourced from the relevant Brewfiles and system packages.

**Tab: Environments**

Three-tier development environment model:

```
 Tier 1: Podman Desktop          [installed / not installed]   (status only)
 Tier 2: Distrobox               [N containers / not installed]  (status only)
 Tier 3: Lima                    [N VM(s) / not set up]  [→ Set Up Lima VM]
```

**Lima guided setup** (4-step `OperationModal` via `lima_setup_steps()` in `core/devmode.py`):
```
Step 1/4: Checking KVM support…        check /dev/kvm; add user to kvm group via pkexec if needed
Step 2/4: Installing Lima…             brew install lima (skipped if limactl already present)
Step 3/4: Starting default Lima VM…    limactl start
Step 4/4: Verifying Lima VM…           limactl list
```

If KVM group was missing: notified to log out; Lima continues with QEMU SLIRP in the meantime.

---

### 5. AI

AI workstation management — the "app store" for GPU-accelerated stacks. TabbedContent with 2 tabs.

**Tab: Stacks (default)**

GPU detection card at top:
```
 GPU: NVIDIA RTX 4090 | 24 GB VRAM | CDI: active | Driver: 560.35
```
or
```
 GPU: AMD Radeon RX 7900 XTX | 24 GB VRAM | /dev/kfd: ok | ROCm: 7.2.4
```

Category filter bar: `[All] [Serve] [Dev] [Train]`

Stack catalog (ListView with detail pane):

```
 [*] Lemonade         4 GB   serve   ROCm + Vulkan + NPU local AI server
 [*] PyTorch Lab      8 GB   dev     CUDA/ROCm + JupyterLab workspace
 [ ] NIM Phi-3.5      8 GB   nim     NVIDIA optimized small LLM
 [ ] NIM Llama3      16 GB   nim     NVIDIA optimized inference
 [-] NeMo Training   24 GB   train   (exceeds 16 GB available)
```

Legend: `[*]` running, `[ ]` available, `[-]` exceeds VRAM (greyed out, confirmation override to deploy anyway)

**Detail pane** (right side) for selected stack:
- Description
- Image ref (full OCI: `nvcr.io/nvidia/pytorch:25.06-py3`)
- VRAM requirement + disk estimate
- Ports exposed (with OSC 8 clickable links when running)
- Dependencies (NGC auth, HuggingFace token, render group)
- Deploy / Stop / Logs actions

**Deploy flow:**
1. Select stack, press Enter
2. **Preflight check** (automatic): GPU available? Driver ready? Ports free? Disk space? Auth tokens?
3. **Confirmation modal**: Shows images to pull, disk use, ports, services created
4. **Unified progress**: Copy quadlet -> daemon-reload -> pull image -> start pod
5. **Running state**: Stack appears with `[*]`, ports shown as clickable links
6. On failure: clean up copied quadlet units, show error in log

**Stack architecture:** One pod per stack. Even single-container stacks get their own pod for consistent networking, lifecycle, and future sidecar support. Stacks read from `/usr/share/ublue-os/{nvidia,amd}-stacks/`. Metadata in `stack.env`.

**Model management:** Via Lemonade (AMD) or Docker Model (NVIDIA). No Ollama.

**Tab: Tools**

AI CLI tools kit status:

```
 AI & ML Tools kit                    [active]  24 tools installed

 Coding Agents:
  [ok] goose              Block Protocol AI agent
  [ok] claude-code        Claude coding agent
  [ok] copilot-cli        GitHub Copilot terminal

 Local AI:
  [ok] lemonade           AMD-native LLM server (via stack)
  [ok] whisper-cpp        Speech-to-text
  [ok] llm                CLI for language models

 Model Tools:
  [ok] docker model       Docker model management
  [--] lm-studio          (not installed)
```

One-action install/update for the full AI tools kit. Lemonade server status shown inline when running.

---

## Unified Progress System

Every operation in bluefinctl — brew install, podman pull, bootc switch, Lima setup — uses the same visual treatment:

### OperationModal widget

```
┌─ Installing Kit: Kubernetes ─────────────────────────────┐
│                                                           │
│  Step 2/3: Installing packages via Homebrew               │
│  ████████████░░░░░░░░░░░░░░░░░░░░░  8/12 packages        │
│                                                           │
│  [l] Show log                                             │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

**Components:**
1. Title (operation name)
2. Step description (current step in multi-step operations)
3. ProgressBar — accent-colored, determinate where parseable, indeterminate otherwise
4. Collapsible raw log (hidden by default, expand with `l` or click)
5. Cancel action (Escape)

**ProgressParser protocol** (`core/progress.py`):

```python
class ProgressParser(Protocol):
    def parse_line(self, line: str) -> ProgressUpdate | None: ...

@dataclass
class ProgressUpdate:
    percent: float | None     # None = indeterminate
    step: int | None
    total_steps: int | None
    message: str
```

Per-tool implementations:
- `PodmanPullParser` — parses layer download percentages
- `BrewInstallParser` — counts formula installs against total
- `BootcSwitchParser` — stage detection (downloading, staging, complete)
- `MultiStepParser` — for wizard flows (Lima, devmode enable)

**OSC 9;4 integration:** Every ProgressBar update also emits the terminal progress escape sequence, so the terminal tab/titlebar shows progress even if the modal is not visible.

---

## Command Palette

`Ctrl+P` opens the Textual Command Palette with:

**Package operations:**
- `install brew:ripgrep` — install Homebrew formula
- `install flatpak:org.gimp.GIMP` — install Flatpak
- `remove brew:bat` — remove package
- Search results show source badges: `[brew formula]`, `[brew cask]`, `[flatpak]`

**Navigation:**
- `Go to System`, `Go to AI`, etc.
- `Open podman-tui`
- `Open changelog`

**Actions:**
- `Update all`
- `Toggle focus mode`
- `Deploy AI stack...`
- `Enable developer mode`

Results always show explicit source. Never silently choose between name conflicts.

---

## Keyboard and Mouse

### Global shortcuts (work from any screen)

| Key | Action |
|-----|--------|
| `1`-`5` | Jump to screen |
| `q` | Quit |
| `?` | Help modal (full shortcut reference) |
| `Ctrl+P` | Command Palette |
| `Tab` / `Shift+Tab` | Focus next/previous widget |
| `Escape` | Close modal / cancel operation |

### Navigation (lists, trees, tables)

| Key | Action |
|-----|--------|
| `Up` / `Down` / `j` / `k` | Move selection |
| `Enter` | Activate / drill into |
| `g` / `G` | Jump to top / bottom |
| `Home` / `End` | Jump to top / bottom |
| `/` | Focus search/filter (where available) |

### Mouse

- Click ViewSwitcher tabs — switch screen
- Click list/table items — select
- Click buttons/tabs — activate
- Scroll anywhere — scroll content
- Click card titles — expand/collapse where applicable

### Per-screen shortcuts

Shown in the footer bar. The footer updates dynamically based on the active screen and focused widget. Example footers:

```
System:    u:update  d:devmode  c:podman-tui  r:report  ?:help
Updates:   f:focus  u:update now  s:stable  t:testing  R:rollback  ?:help
Toolkit:   Enter:activate  r:refresh  Ctrl+P:install  ?:help
DevMode:   Enter:install/setup  a:install all  c:podman-tui  ?:help
AI:        Enter:deploy  s:stop  l:logs  f:filter  ?:help
```

### Help Modal (`?`)

Full-screen modal with shortcuts grouped:

```
 Global          Navigation       This Screen
 ─────────────   ──────────────   ─────────────────────
 1-5  Screens    Up/j   Move up   u  Update All
 q    Quit       Down/k Move dn   d  Toggle Devmode
 ?    Help       Enter  Select    c  podman-tui
 ^P   Palette    g/G    Top/Bot   r  System Report
 Esc  Close      /      Search
 Tab  Focus
```

---

## Theming

### GNOME Accent Color Integration

Read at startup via `gsettings get org.gnome.desktop.interface accent-color`. Map to hex palette matching libadwaita's accent colors:

| Name | Hex |
|------|-----|
| blue | `#3584e4` |
| teal | `#2190a4` |
| green | `#3a944a` |
| yellow | `#c88800` |
| orange | `#ed5b00` |
| red | `#e62d42` |
| pink | `#d56199` |
| purple | `#9141ac` |
| slate | `#6f8396` |

Injected as `$accent` CSS variable. Drives: sidebar highlights, progress bar fill, card titles, active states, button hovers, focus rings.

### Visual Language

- **Dark theme always** (`$background: #1a1a2e`, `$surface: #16213e`)
- **Cards**: `border: round $border`, accent-colored titles, generous padding
- **Status indicators**: `[ok]` (green), `[!]` (yellow), `[X]` (red), `[--]` (muted grey)
- **No emojis** — text-based Unicode indicators only
- **Full OCI refs** in detail panes (cards show abbreviated where space-constrained, detail always shows full)
- **Monospace throughout** — system font
- **GPU vendor colors**: NVIDIA `#76b900`, AMD `#ed1c24`, Intel `#0071c5`

### Terminal Integration

| Feature | Behavior |
|---------|----------|
| OSC 9;4 | Progress in terminal tab/titlebar (Ghostty, Ptyxis, iTerm2) |
| OSC 8 | Clickable hyperlinks for ports (http://localhost:8888) |
| Ghostty | Detect via `$TERM_PROGRAM=ghostty`, enable Kitty keyboard protocol |
| Headless | Emit `sd_notify` style progress for systemd journal integration |

---

## AI Stack Architecture

### Stack Discovery

Stacks read from system directories:
- NVIDIA: `/usr/share/ublue-os/nvidia-stacks/`
- AMD: `/usr/share/ublue-os/amd-stacks/`

Each stack directory contains:
- `stack.env` — metadata (name, description, VRAM, category, ports, auth requirements)
- `<name>.container` — Podman Quadlet container unit
- `<name>-network.network` — Podman Quadlet network unit

### Stack Manifest Schema (from stack.env)

```bash
STACK_ORDER=10           # Display order in catalog
STACK_NAME="Lemonade"    # Human-readable name
STACK_DESC="ROCm + Vulkan + NPU local AI server"
STACK_CATEGORY="serve"   # serve | dev | train
STACK_VRAM_GB=4          # Minimum VRAM requirement
STACK_DISK_GB=4          # Estimated disk usage
STACK_PORTS="api:13305"  # Named ports
STACK_REQUIRES_NGC_AUTH=false
STACK_REQUIRES_HF_AUTH=false
```

### Deployment Lifecycle

```
Preflight:
  1. Detect GPU vendor (NVIDIA CDI / AMD KFD)
  2. Check VRAM >= STACK_VRAM_GB (warn if not, allow override)
  3. Check ports not in use
  4. Check disk space
  5. Check auth tokens if required (prompt if missing)
  6. Check driver/runtime (CDI active? render group?)

Deploy:
  1. Copy .container + .network to ~/.config/containers/systemd/
  2. systemctl --user daemon-reload
  3. podman pull <image> (with progress parsing)
  4. systemctl --user start <pod>
  5. Verify pod is running

Failure rollback:
  - Remove copied quadlet files
  - daemon-reload to clean state
  - Report error with collapsible log

Stop:
  1. systemctl --user stop <pod>

Remove:
  1. systemctl --user stop <pod>
  2. Remove quadlet files
  3. daemon-reload
  4. Optionally: podman rmi <image>, remove volumes
```

### One Pod Per Stack

Every stack deploys as its own pod, even single-container stacks:
- Consistent lifecycle (`podman pod start/stop`)
- Network isolation per stack
- Future-proof for sidecars (metrics, proxies)
- Matches what podman-tui shows

---

## Distribution

```toml
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

**No RPMs.** Shipped via Homebrew, baked into Bluefin images. Homebrew manages its own Python runtime.

**Runtime dependencies** (expected on system):
- `podman` (for AI stacks, container status)
- `systemctl` (for uupd management, quadlet lifecycle)
- `bootc` (for channel switch, rollback, image status)
- `gsettings` (for GNOME accent color; graceful fallback to blue)
- `brew` (for kit/package management)

**Optional dependencies:**
- `podman-tui` (launched for full container management)
- `nvidia-smi` / `nvidia-ctk` (NVIDIA GPU detection)
- `lima` (WSL-equivalent VM, installed on demand)

---

## Textual Long-Term Assessment

### Strengths for bluefinctl

| Feature | Value |
|---------|-------|
| CSS theming | Live accent color injection, hot-reload during development |
| Widget library | DataTable, Tree, TabbedContent, ProgressBar, MarkdownViewer, CommandPalette |
| Workers API | Async subprocess management for brew/podman/bootc |
| Command Palette | Ctrl+P discoverability for all actions, built-in |
| Snapshot testing | SVG renders for automated UI regression tests |
| Screen system | Natural multi-page navigation |
| MarkdownViewer | Rich changelog/help rendering in-terminal |

### Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Textualize pivots/abandons | Low | MIT licensed, large community, can fork |
| API churn between versions | Medium | Pin to `>=1.0,<2.0`, test on upgrade |
| Python startup latency | Low | ~300ms acceptable for a dashboard app |
| Python on immutable OS | Medium | Ship via brew (manages its own Python) |
| Missing widget | Low | Textual supports custom widgets easily |

---

## Implementation Roadmap

Progressive implementation order. Each phase produces a working, testable increment. Later phases build on earlier ones.

### Phase 1: Foundation

1. **Update `app.py`** — 5-screen registration (System, Updates, Toolkit, DevMode, AI), number-key bindings, terminal title via OSC 0
2. **Create `_viewswitcher.py`** — Horizontal tab bar (libadwaita AdwViewSwitcher), accent-tinted active tab, clickable
3. **Implement `core/operations.py`** — Resumable operation state machine (preflight/executing/needs-relogin/needs-reboot/pending-verification/complete/failed)
4. **Implement `widgets/operation_modal.py`** — Unified OperationModal: title + step description + ProgressBar + collapsible LogView + OSC 9;4 emission
5. **Implement `core/progress.py`** — ProgressParser protocol + MultiStepParser + indeterminate fallback

### Phase 2: System Screen

6. **Rewrite `screens/system.py`** — Card-based: Identity (full OCI ref), Hardware, Health, Running Services (pod summary + podman-tui launch), Active Kits summary, Quick Actions
7. **Implement `util/terminal.py`** — Launch external app in new terminal (detect Ghostty/Ptyxis/gnome-terminal, spawn subprocess)
8. **Update `core/system.py`** — Add pod count query, kit summary query

### Phase 3: Updates Screen

9. **Rewrite `screens/updates.py`** — Focus Mode group with snooze buttons (1h/Tonight/Tomorrow), Changelog viewer at bottom
10. **Update `core/updates.py`** — `activate_focus_mode(duration_hours=N)` for timed snooze; persist state to `~/.config/bluefinctl/state.json`
11. **Add `widgets/changelog.py`** — Reads `/usr/share/ublue-os/changelog.md`; falls back to fetching from bootc image tag

### Phase 4: Toolkit Screen

12. **Create `screens/toolkit.py`** — TabbedContent with Kits tab, two-column layout (ListView + detail pane)
13. **Create `core/kits.py`** — Kit discovery from `/usr/share/ublue-os/homebrew/*.Brewfile`, install state detection, activate/deactivate via `brew bundle`
14. **Wire Command Palette** — Add package search provider (brew search + flatpak search), source badges in results, install/remove actions
15. **Remove old `screens/bundles.py` and `screens/packages.py`** — Replaced by toolkit.py

### Phase 5: DevMode Screen

16. **Create `screens/devmode.py`** — TabbedContent: Overview, Tools, Environments
17. **Update `core/devmode.py`** — Add runtime health checks (Docker socket, Podman socket, Lima status), tool install state
18. **Implement Lima guided setup** — 4-step `OperationModal` in `lima_setup_steps()`: KVM preflight → brew install lima → limactl start → verify

### Phase 6: AI Screen

21. **Create `screens/ai.py`** — TabbedContent: Stacks, Tools
22. **Create `core/ai.py`** — Stack discovery (parse stack.env from system dirs), GPU detection (NVIDIA CDI / AMD KFD), preflight checks, deploy/stop lifecycle
23. **Implement stack catalog widget** — ListView with VRAM badges, category filter, detail pane with full OCI refs and port links
24. **Implement deploy flow** — Preflight modal -> confirmation modal -> OperationModal (copy quadlet -> daemon-reload -> pull -> start -> verify)
25. **Implement stack lifecycle** — Stop, remove, view logs actions
26. **Wire Lemonade/Docker Model** status into Tools tab

### Phase 7: Polish

27. **Help modal** — Full shortcut reference grouped by Global/Navigation/Screen-specific
28. **Degraded mode** — Every screen handles missing tools gracefully (show install prompts, not crashes)
29. **Headless CLI completion** — Ensure every TUI action has a `cli.py` equivalent with JSON output support
30. **Snapshot tests** — SVG snapshot for each screen in default state
31. **OSC 8 hyperlinks** — Port numbers in AI screen link to `http://localhost:<port>`
32. **Toast notifications** — "Kit installed", "Stack deployed", "Focus mode expires in 1h"

### Phase 8: Stack Catalog Expansion

33. **Fix NVIDIA tensorflow-lab** — Pin to 25.02 or replace with Docker Hub TF image
34. **Add small NIM** — nim-phi (phi-3.5-mini, 8 GB) for common RTX GPUs
35. **Add ComfyUI stack** (AMD) — `ghcr.io/yanwenkun/comfyui-docker:rocm-torch2.6`, 8 GB
36. **Add NIM VLM** — llama-3.2-11b-vision, 24 GB tier
37. **Monitor NeMo->Megatron-Bridge transition** — Update at ngc-month 26.02

---

## Scope

### v1 — Ship with:

1. All 5 screens fully functional
2. Unified progress system for all operations
3. Command Palette with package search (brew + flatpak)
4. GNOME accent color theming
5. OSC 9;4 progress integration
6. Headless CLI for all operations
7. Help system (? modal + footer shortcuts)
8. AI stack deploy/stop/logs for existing stacks
9. Kit management (activate/deactivate all shipped kits)
10. DevMode enable/disable with guided setup
11. Lima WSL-equivalent setup wizard
12. Focus mode + snooze
13. Channel switch + rollback
14. Changelog viewer (MarkdownViewer)

### v2 — Deferred:

- AI assistant integration (textual-ai, conversational interface)
- Stack composition wizard (build custom stacks)
- Sparkline widgets (CPU/GPU/memory mini-graphs)
- Multi-GPU support (select which GPU for a stack)
- Remote machine management (SSH to other Bluefin machines)
- Auto-update of kits (scheduled brew bundle)
- Export/import machine configuration
