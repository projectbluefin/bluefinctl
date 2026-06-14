---
name: run
description: >-
  Launch bluefinctl in a Ghostty terminal for interactive testing. Use when
  the user wants to see the app running, test the TUI, prototype, preview
  changes, or says "run it", "show me", "launch", "open terminal".
  Use bctl (short alias) or bluefinctl.
---

# Run bluefinctl

## Quick launch

```bash
ghostty -e bctl &
```

## With hot-reload CSS (Textual dev mode)

```bash
ghostty -e textual run --dev src/bluefinctl/app.py &
```

## Jump to a specific screen

```bash
ghostty -e bctl --screen updates &
ghostty -e bctl --screen devmode &
ghostty -e bctl --screen ai &
```

## Workflow

1. Run the launch command (detached so pi keeps control)
2. The Ghostty window opens with bluefinctl running
3. Interact with the TUI in that window
4. Return to pi to make code changes
5. Re-launch to see updates, or use `textual run --dev` for CSS hot-reload

## When NOT to Use

- When running automated tests — use `pytest` directly
- When verifying CLI behaviour — use `bctl <command>` directly in the terminal

## Notes

- Ghostty is at `/usr/bin/ghostty`
- App is installed editable (`pip install -e .`) — code changes apply on next launch
- Available screens: `system` (default), `updates`, `devmode`, `ai`
- Kill a previous instance before re-launching if testing fresh state: `pkill -f bctl`

## Verification

After launch:
- [ ] ViewSwitcher shows 4 tabs: System · Updates · Developer · AI
- [ ] System screen loads identity (image ref, hostname, GPU)
- [ ] Updates screen shows image banner at top (`ghcr.io/projectbluefin/...`)
- [ ] Developer screen shows Kits / Tools / Environments tabs
- [ ] OpsBar visible at the bottom of each screen
