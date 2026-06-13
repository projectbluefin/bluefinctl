---
name: run
description: Launch bluefinctl in a Ghostty terminal for interactive testing. Use when user wants to see the app running, test the TUI, prototype, preview changes, or says "run it", "show me", "launch", "open terminal".
---

# Run bluefinctl

Launch the app in a detached Ghostty window for interactive testing.

## Quick launch

```bash
ghostty -e bluefinctl &
```

## With textual dev mode (hot-reload CSS)

```bash
ghostty -e textual run --dev src/bluefinctl/app.py &
```

## Jump to a specific screen

```bash
ghostty -e bluefinctl --screen bundles &
```

## Workflow

1. Run the launch command (detached so pi keeps control)
2. The Ghostty window appears with bluefinctl running
3. User interacts with the TUI in that window
4. Come back to pi to make code changes
5. Re-launch to see updates (or use `textual run --dev` for CSS hot-reload)

## Notes

- Ghostty is at `/usr/bin/ghostty`
- The app is installed editable (`pip install -e .`) so code changes apply on next launch
- Use `--screen` flag to jump directly to: system, bundles, packages, updates, containers
- For CSS-only changes, `textual run --dev` hot-reloads without restart
- Kill previous instance before re-launching if testing fresh state
