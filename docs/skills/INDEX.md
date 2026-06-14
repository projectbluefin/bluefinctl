---
name: skills-index
description: >-
  Index of all skill documentation files for bluefinctl. Use to discover
  which skill file covers a given area, or to confirm a new skill doesn't
  duplicate existing coverage.
---

# docs/skills — Index

Reference index of skill documentation files. These are knowledge files loaded on-demand. They are **not** the agent instruction files (`AGENTS.md`, `.agents/skills/`).

## What belongs here

- Non-obvious patterns, workarounds, and conventions discovered during development
- Area-specific reference docs too detailed for `AGENTS.md`
- Procedure docs (gates, mandates) that agents load when needed

## What does NOT belong here

- One-off notes or task-specific context
- Content that duplicates `AGENTS.md`
- Ephemeral state (branch names, PR numbers)

## Skill docs

| File | What it covers |
|---|---|
| [textual-dev.md](textual-dev.md) | Textual patterns: `@work`, `_CheckToggle`, ADW widgets, `height:auto`, pkexec tee, OSC progress, dark/light theme, CSS constraints, common pitfalls |
| [human-gates.md](human-gates.md) | The 4 decision gates (Design/Security/Breakage/Merge) — when to stop, how to signal, verification evidence requirement |
| [skill-improvement.md](skill-improvement.md) | The skill-improvement mandate — checklist, what counts as a learning, which file to update, how to commit it |
| [gap-tracker.md](gap-tracker.md) | v1 feature status — every screen, cross-cutting concerns, widget inventory, known bugs. Pick a `[ ]` item to work on. |
| [ai-stacks.md](ai-stacks.md) | AI stack management — GPU detection, bundled quadlet catalog, deploy flow, auth, status detection, AI_TOOL_REGISTRY gap |

## Agent instruction files (loaded separately by tool)

These are not in `docs/skills/` — they are loaded automatically by pi:

| File | Purpose |
|---|---|
| `AGENTS.md` (project root) | Project-wide agent instructions, fast path, gates summary |
| `docs/SKILL.md` | Task → skill router |
| `.agents/skills/bluefinctl-dev/SKILL.md` | Main dev skill — screens, widgets, core patterns |
| `.agents/skills/run/SKILL.md` | Launch the TUI for visual testing |

## Stubs — create when work surfaces content

The following areas don't have skill files yet. Create one when you work in the area and learn something worth writing back:

| Area | File to create |
|---|---|
| Update strategy / uupd / systemd timers | `docs/skills/updates.md` |
| Homebrew / Brewfile layer management | `docs/skills/brew.md` |
| Rollback calendar / skopeo image discovery | `docs/skills/rollback.md` |
| Headless CLI / Typer patterns | `docs/skills/cli.md` |
| Snapshot testing | `docs/skills/testing.md` |
