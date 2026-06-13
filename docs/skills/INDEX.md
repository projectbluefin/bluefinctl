# docs/skills — Index

Agent-agnostic skill docs for `projectbluefin/bluefinctl`. These apply to any agent (Copilot, Claude, etc.) working in this repository.

## What belongs here

Workflow knowledge, architectural context, and operational runbooks that any agent needs to work effectively in this repo. Discovered workarounds, non-obvious patterns, and conventions go here so the next agent starts smarter.

## What does NOT belong here

Agent-specific instruction files (`.github/copilot-instructions.md`, `AGENTS.md`) are loaded separately by their respective tools and are not listed here. The Copilot CLI skill (`.agents/skills/bluefinctl-dev/`) covers the interactive TUI workflow.

## Skill docs

| File | What it covers |
|---|---|
| [textual-dev.md](textual-dev.md) | Textual patterns, pitfalls, CSS constraints, modal usage, `prevent()` pattern, pkexec tee, OSC progress, tree nodes — the non-obvious Textual behaviors discovered in this codebase |
| [human-gates.md](human-gates.md) | The 4 decision gates (Design/Security/Breakage/Merge) — when to stop, how to signal, verification evidence requirement |
| [skill-improvement.md](skill-improvement.md) | The skill-improvement mandate — checklist, what counts as a learning, which file to update, how to commit it |

## Stubs — create when work surfaces content

| File | Create when... |
|---|---|
| `brew.md` | Working on `core/bundles.py`, `core/brew.py`, or Brewfile layer logic |
| `updates.md` | Working on `core/updates.py`, uupd config, systemd timer management, or focus mode |
| `bootc.md` | Working on bootc switch/rollback/status integration |
| `containers.md` | Working on Podman pod/container logic in `core/containers.py` or the containers screen |
| `testing.md` | Working on pytest fixtures, asyncio test patterns, or Textual snapshot tests |
| `cli.md` | Working on `cli.py` Typer subcommands or the headless path |

## Agent instruction files (not skills — loaded separately by tool)

| File | Purpose |
|---|---|
| [../../AGENTS.md](../../AGENTS.md) | Full operating contract — self-improvement loop, PR rules, human gates, build commands |
| [../../.github/copilot-instructions.md](../../.github/copilot-instructions.md) | Thin Copilot router — points to AGENTS.md and docs/SKILL.md |
| [../../.agents/skills/bluefinctl-dev/SKILL.md](../../.agents/skills/bluefinctl-dev/SKILL.md) | Copilot CLI interactive skill — screen patterns, bundle system, modal usage, add-a-screen checklist |
