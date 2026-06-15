# ADR 0001 — Smart Reboot Strategies

Date: 2026-06-14
Status: Accepted (partial — future work noted)

## Context

Staged OS updates require a reboot. Interrupting a user's work for a reboot is bad UX.
We want to apply updates at moments when the user is not actively using their computer.

## Decision (1.0)

Ship three strategies:

1. **Reboot on logout** — if staged update exists and user logs out, reboot instead.
   Pairs with GDM autologin so user lands back at desktop automatically.
   Implemented as a systemd user service drop-in at
   `~/.config/systemd/user/session.target.wants/bluefinctl-reboot.service`.
   A marker file at `~/.config/bluefinctl/reboot-on-logout` tracks the enabled state.

2. **Scheduled window** — systemd user timer fires at 2am; reboots only if
   staged update + AC power + no systemd inhibitors.
   Timer: `~/.config/systemd/user/bluefinctl-reboot-window.timer`
   Service: `~/.config/systemd/user/bluefinctl-reboot-window.service`

3. **Manual** — explicit opt-out, user reboots themselves.

Safety invariant: never reboot if `systemd-inhibit --list` shows audio/video/idle
inhibitors active. Skipped reboots are logged to
`~/.local/share/bluefinctl/reboot-skipped.log`.

## Future work (not in 1.0)

### Idle reboot

Watch systemd-logind idle hint. After N configurable minutes of idle (screen locked,
no input), show a countdown notification and reboot if not cancelled. Harder to get
right — idle detection varies by compositor.

### Screen-lock reboot

Hook into `org.freedesktop.login1` Lock signal. If locked for >30 minutes and staged
update exists, reboot. 30-minute buffer prevents accidental reboot on quick
lock-screen checks.

## Alternatives considered

- Snooze timers (1h, tonight, tomorrow) — rejected, update checks are infrequent so
  snoozing is meaningless
- Always-auto-reboot — rejected, safety risk
