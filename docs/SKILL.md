---
name: skill-router
description: >-
  Routes agent tasks to the correct skill file for the bluefinctl project.
  Use at session start to find the right skill before acting. Covers TUI
  development, core logic, testing, AI stacks, update management, devmode,
  containers, and bootc. Also defines scope rules for doc-only vs implementation
  tasks.
---

# bluefinctl Skill Router

Agent entry point for `projectbluefin/bluefinctl`. Load only the skill(s) that match your task.

## Task → Skill

| I need to… | Load |
|---|---|
| **Session start / orientation** | |
| Understand the full operating contract, PR rules, or gates | `AGENTS.md` |
| Know when to stop and ask a human | `docs/skills/human-gates.md` |
| **TUI development** | |
| Add a screen, wire actions, create modals, or modify the theme | `.agents/skills/bluefinctl-dev/SKILL.md` |
| Debug a Textual layout, CSS, or widget state issue | `.agents/skills/bluefinctl-dev/SKILL.md` + `docs/skills/textual-dev.md` |
| Work with the kit/bundle system (`core/bundles.py`) | `.agents/skills/bluefinctl-dev/SKILL.md` |
| Work with OSC progress or Ghostty integration | `docs/skills/textual-dev.md` |
| Work with the unified progress system (OperationModal) | `docs/skills/textual-dev.md` |
| Add a new screen or navigation item | `.agents/skills/bluefinctl-dev/SKILL.md` |
| **Core / business logic** | |
| Work with AI stacks (`core/ai.py`) — GPU detection, deploy, stop | `docs/skills/ai-stacks.md` |
| Modify update strategy, uupd config, or systemd timers | `.agents/skills/bluefinctl-dev/SKILL.md` |
| Work with bootc (switch, rollback, status, image info) | `.agents/skills/bluefinctl-dev/SKILL.md` |
| Work with devmode (groups, Lima, distrobox) | `.agents/skills/bluefinctl-dev/SKILL.md` |
| **Testing** | |
| Write or run tests (pytest, asyncio, Textual snapshots) | `AGENTS.md` + `docs/skills/textual-dev.md` |
| **Gap tracking** | |
| Find what's not yet implemented, what's broken, or what to work on next | `docs/skills/gap-tracker.md` |
| **Factory and improvement** | |
| Complete a task and decide whether to write a skill update | `docs/skills/skill-improvement.md` |
| Need to know which skill file to update after work | `docs/skills/skill-improvement.md` |
| Launch the app for visual testing | `.agents/skills/run/SKILL.md` |

## Scope rules

- **Doc tasks** (`docs/` and `AGENTS.md`) → push directly to `main`, no PR needed.  
  Before using this exception, verify: `git diff --cached --name-only` must show only `docs/*` or `AGENTS.md`.
- **Implementation tasks** → branch + PR targeting `main`.
- **One PR per feature.** Never batch unrelated changes.

## Improving skill docs

All files in `docs/skills/` are operational knowledge. Update them in the **same PR** as the work — never a follow-up. See `docs/skills/skill-improvement.md` for the full mandate.
