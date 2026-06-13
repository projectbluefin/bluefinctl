# bluefinctl Skill Router

Agent entry point for `projectbluefin/bluefinctl`. Load only the skill(s) that match your task.

## Task → Skill

| I need to... | Load |
|---|---|
| **Session start / orientation** | |
| Understand the full operating contract, PR rules, or gates | `AGENTS.md` |
| Know when to stop and ask a human | `docs/skills/human-gates.md` |
| **TUI development** | |
| Add a screen, wire actions, create modals, or modify the theme | `.agents/skills/bluefinctl-dev/SKILL.md` |
| Debug a Textual layout, CSS, or widget state issue | `.agents/skills/bluefinctl-dev/SKILL.md` |
| Work with the bundle system (`core/bundles.py`) | `.agents/skills/bluefinctl-dev/SKILL.md` |
| Work with OSC progress or Ghostty integration | `.agents/skills/bluefinctl-dev/SKILL.md` |
| Add a new panel or navigation item | `.agents/skills/bluefinctl-dev/SKILL.md` |
| **Core / business logic** | |
| Modify update strategy, uupd config, or systemd timers | `docs/skills/updates.md` (create if needed) |
| Work with Homebrew / Brewfile layers | `docs/skills/brew.md` (create if needed) |
| Work with bootc (switch, rollback, status) | `docs/skills/bootc.md` (create if needed) |
| Work with Podman containers or pods | `docs/skills/containers.md` (create if needed) |
| **Testing** | |
| Write or run tests (pytest, asyncio, Textual snapshots) | `docs/skills/testing.md` (create if needed) |
| **Factory and improvement** | |
| Complete a task and decide whether to write a skill update | `docs/skills/skill-improvement.md` |
| Need to know which skill file to update after work | `docs/skills/skill-improvement.md` |

## Improving skill docs

All files in `docs/skills/` are operational knowledge. They live here so any contributor can update them directly.

**When to update a skill:** any time a session surfaces a workaround, non-obvious pattern, or convention. See [`docs/skills/skill-improvement.md`](skills/skill-improvement.md) for the full mandate and checklist.

For the full catalog of skill files, see [`docs/skills/INDEX.md`](skills/INDEX.md).

## Scope rules

- **Doc tasks**: modify only `docs/` and `AGENTS.md`. Do not touch `src/` or `.github/workflows/` unless the task is explicitly implementation work.
- **Implementation tasks**: touch `src/` and update `docs/skills/` if learnings arise.
- **One PR per feature.** Never batch unrelated changes.
