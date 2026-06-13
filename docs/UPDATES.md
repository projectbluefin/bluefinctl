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
│ enable/disable│ │ config.json │ │ mask/    │ │ --target     │
│ uupd.timer    │ │ modules.*   │ │ unmask   │ │              │
└───────────────┘ └─────────────┘ └──────────┘ └──────────────┘
        │              │              │              │
        └──────────────┴──────────────┴──────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │       uupd       │
                    │  (update daemon) │
                    └──────────────────┘
```

## Configuration Targets

### 1. uupd Timer State

| Strategy | Timer State | Effect |
|----------|------------|--------|
| Automatic | `enabled + active` | uupd runs on schedule |
| Notify | `enabled + active` | uupd runs but only stages |
| Manual | `disabled + inactive` | Nothing runs until user triggers |
| Scheduled | `enabled + active` with drop-in | Runs in specific window |

Commands:
```bash
# Enable automatic
systemctl enable --now uupd.timer

# Disable (manual)
systemctl disable --now uupd.timer

# Focus mode (temporary disable)
systemctl mask uupd.timer

# Release focus mode
systemctl unmask uupd.timer
systemctl enable --now uupd.timer
```

### 2. uupd Config (`/etc/uupd/config.json`)

```json
{
  "modules": {
    "bootc": {
      "disable": false
    },
    "flatpak": {
      "disable": false
    },
    "brew": {
      "disable": false
    }
  },
  "checks": {
    "hardware": {
      "cpu_max_percent": 50,
      "memory_min_available_mb": 1024,
      "battery_min_percent": 20
    }
  }
}
```

bluefinctl reads this, presents it in the UI, and writes back changes via pkexec.

### 3. Schedule Drop-in

When strategy is "Scheduled", write:
```ini
# /etc/systemd/system/uupd.timer.d/bluefinctl-schedule.conf
[Timer]
OnCalendar=
OnCalendar=*-*-* 02:00:00
RandomizedDelaySec=1h
```

Predefined schedules:
- **Night Owl** — 2-5 AM
- **Early Bird** — 5-7 AM
- **Lunch Break** — 12-1 PM
- **Custom** — user picks time

### 4. Channel (`bootc switch`)

```bash
# Switch to testing
bootc switch --target ghcr.io/projectbluefin/bluefin:testing

# Switch back to stable
bootc switch --target ghcr.io/projectbluefin/bluefin:latest

# Pin to specific build
bootc switch --target ghcr.io/projectbluefin/bluefin:41-20240601
```

All require reboot to take effect. The UI must make this clear.

---

## Focus Mode — Implementation

Focus mode is the "do not disturb" for system updates.

### State Machine

```
         activate
Normal ──────────► Focus Active
  ▲                    │
  │                    │ (expiry OR manual deactivate)
  └────────────────────┘
         deactivate
```

### Storage

Focus mode state lives in `~/.config/bluefinctl/state.json`:
```json
{
  "focus_mode": {
    "active": true,
    "activated_at": "2024-06-13T10:00:00Z",
    "expires_at": "2024-06-13T22:00:00Z",
    "reason": "Training run"
  }
}
```

### Activation

```python
async def activate_focus(duration_hours: int | None = None, reason: str = ""):
    # 1. Mask the timer
    await run("systemctl", "mask", "uupd.timer")
    
    # 2. Record state
    state.focus_mode = FocusState(
        active=True,
        activated_at=now(),
        expires_at=now() + timedelta(hours=duration_hours) if duration_hours else None,
        reason=reason,
    )
    
    # 3. If duration set, schedule unmask
    if duration_hours:
        await schedule_unmask(state.focus_mode.expires_at)
```

### Expiry

Use a systemd user timer:
```ini
# ~/.config/systemd/user/bluefinctl-focus-expire.timer
[Timer]
OnCalendar=2024-06-13 22:00:00
Persistent=false

[Install]
WantedBy=timers.target
```

```ini
# ~/.config/systemd/user/bluefinctl-focus-expire.service
[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl unmask uupd.timer
ExecStart=/usr/bin/systemctl start uupd.timer
ExecStartPost=rm ~/.config/bluefinctl/focus-lock
```

### 7-Day Nag

If focus mode has been active > 7 days, bluefinctl shows a persistent warning:
```
⚠ Focus mode active for 8 days — your system hasn't updated since June 5.
  [Deactivate] [Snooze reminder]
```

---

## Deferral (Snooze)

Different from Focus Mode. Snooze is for when an update notification arrives and the user says "not now."

| Snooze | Implementation |
|--------|---------------|
| 1 hour | mask timer + one-shot unmask in 1h |
| Tonight | mask timer + unmask at 2 AM |
| Tomorrow | mask timer + unmask in 24h |
| Skip version | Add target image ref to skip-list |

### Skip List

```json
// ~/.config/bluefinctl/state.json
{
  "skipped_versions": [
    "ghcr.io/projectbluefin/bluefin@sha256:abc123..."
  ]
}
```

When uupd stages an update and bluefinctl sees it matches a skipped version, it doesn't notify. On the *next* new version, the skip list is cleared.

---

## Health Checks

Run automatically on first login after a new deployment boots.

```python
HEALTH_CHECKS = [
    HealthCheck(
        name="GPU Driver",
        command=["nvidia-smi"] if nvidia else ["rocm-smi"],
        pass_exit_code=0,
        severity="critical",
    ),
    HealthCheck(
        name="System Services",
        command=["systemctl", "is-system-running"],
        pass_output=["running", "degraded"],
        severity="warning",
    ),
    HealthCheck(
        name="Homebrew",
        command=["brew", "doctor"],
        pass_exit_code=0,
        severity="info",
    ),
    HealthCheck(
        name="Flatpak",
        command=["flatpak", "list", "--app"],
        pass_exit_code=0,
        severity="info",
    ),
]
```

Results displayed on dashboard. Critical failures get a toast notification on TUI launch.

---

## Rollback

Read deployments from `bootc status --json`:

```json
{
  "status": {
    "booted": {
      "image": "ghcr.io/projectbluefin/bluefin:41-stable",
      "version": "41.20240610"
    },
    "rollback": {
      "image": "ghcr.io/projectbluefin/bluefin:41-stable",
      "version": "41.20240603"
    }
  }
}
```

UI shows:
```
Current:  41.20240610 (booted 2h ago)
Previous: 41.20240603 [← Rollback]
```

Rollback action: `pkexec bootc rollback` → prompts reboot.

---

## Privilege Model

| Operation | Privilege | Mechanism |
|-----------|-----------|-----------|
| Read uupd config | root | `pkexec cat /etc/uupd/config.json` |
| Write uupd config | root | `pkexec tee /etc/uupd/config.json` |
| Timer enable/disable | root | `pkexec systemctl ...` |
| bootc switch/rollback | root | `pkexec bootc ...` |
| Focus mode state | user | `~/.config/bluefinctl/state.json` |
| Brew operations | user | No elevation needed |
| Read bootc status | user | `bootc status` (unprivileged) |

bluefinctl prompts for auth only when writing to system config. Read operations are always unprivileged where possible.
