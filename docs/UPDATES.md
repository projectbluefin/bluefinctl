# Update Management — Deep Dive

## How bluefinctl interfaces with uupd

```
┌──────────────────────────────────────────────────────────────┐
│                    bluefinctl (TUI / CLI)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Strategy │  │ Per-Layer│  │  Focus   │  │ Channel  │    │
│  │ Selector │  │ Toggles  │  │  Mode    │  │ Switch   │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
└───────┼──────────────┼──────────────┼──────────────┼─────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌───────────────┐ ┌─────────────┐ ┌──────────┐ ┌──────────────┐
│ systemctl     │ │ /etc/uupd/  │ │ systemctl│ │ bootc switch │
│ enable/disable│ │ config.json │ │ mask/    │ │              │
│ uupd.timer    │ │ modules.*   │ │ unmask   │ │              │
└───────────────┘ └─────────────┘ └──────────┘ └──────────────┘
```

## Configuration Targets

### 1. uupd Timer State

| Strategy | Timer State | Effect |
|----------|------------|--------|
| Automatic | `enabled + active` | uupd runs on schedule |
| Notify | `enabled + active` | uupd runs but only stages |
| Manual | `disabled + inactive` | Nothing runs until user triggers |

```bash
# Enable automatic
pkexec systemctl enable --now uupd.timer

# Disable (manual)
pkexec systemctl disable --now uupd.timer

# Focus mode (temporary disable)
pkexec systemctl mask uupd.timer

# Release focus mode
pkexec systemctl unmask uupd.timer
pkexec systemctl enable --now uupd.timer
```

### 2. uupd Config (`/etc/uupd/config.json`)

```json
{
  "modules": {
    "bootc":   { "disable": false },
    "flatpak": { "disable": false },
    "brew":    { "disable": false }
  }
}
```

bluefinctl reads this, presents it as AdwSwitchRow toggles, and writes back via `pkexec tee`.

### 3. Channel (`bootc switch`)

```bash
# Switch to testing
pkexec bootc switch ghcr.io/projectbluefin/bluefin:testing

# Switch back to stable
pkexec bootc switch ghcr.io/projectbluefin/bluefin:latest
```

All require reboot to take effect. bluefinctl confirms before switching.

---

## Focus Mode

Focus mode is the "do not disturb" for system updates — masks `uupd.timer` entirely.

### State

Persisted to `~/.config/bluefinctl/state.json`:
```json
{
  "focus_mode": {
    "active": true,
    "activated_at": "2024-06-13T10:00:00",
    "expires_at": "2024-06-13T22:00:00",
    "reason": ""
  }
}
```

### Activation

```python
# Indefinite (toggle switch ON)
await activate_focus_mode()

# Timed (snooze buttons)
await activate_focus_mode(duration_hours=1)        # Snooze 1 hour
await activate_focus_mode(duration_hours=N)        # Snooze until tonight (hours until 22:00)
await activate_focus_mode(duration_hours=M)        # Snooze until tomorrow (hours until 08:00 next day)
```

`activate_focus_mode` masks the timer and writes expiry to state.json. Deactivation unmasks and re-enables. The `expires_at` field is informational — expiry is NOT enforced by a background daemon; it is checked on next app launch.

---

## Rollback

Read deployments from `bootc status --json`:

```json
{
  "status": {
    "booted":   { "image": { "image": { "image": "ghcr.io/projectbluefin/bluefin:latest" } } },
    "rollback": { "image": { "image": { "image": "ghcr.io/projectbluefin/bluefin:latest" } } }
  }
}
```

UI shows current and previous image refs. Rollback disabled when no previous deployment is present.

Rollback action: `pkexec bootc rollback` → confirmation modal → OperationLogModal.

---

## Health Checks

Displayed on System screen via `core/system.py`:

| Check | Command |
|-------|---------|
| GPU Driver | `nvidia-smi` (NVIDIA) or `rocm-smi` (AMD) |
| System Services | `systemctl is-system-running` |
| Homebrew | `brew doctor` |

Results are shown as `AdwPropertyRow` values in the Health group.

---

## Privilege Model

| Operation | Mechanism |
|-----------|-----------|
| Write uupd config | `pkexec tee /etc/uupd/config.json` |
| Timer enable/disable/mask | `pkexec systemctl ...` |
| bootc switch/rollback | `pkexec bootc ...` |
| Focus mode state | `~/.config/bluefinctl/state.json` (user-writable) |
| Brew operations | No elevation needed |
| Read bootc status | `bootc status` (unprivileged) |
