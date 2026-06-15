---
name: skill-improvement
description: >-
  The skill-improvement mandate — every agent session must produce a skill
  file update alongside the work. Use when completing a task and deciding
  whether to write a skill update, or when creating or updating a skill file.
  Covers what counts as a learning, Context7 documentation freshness, the
  canonical skill spec, and how to commit.
metadata:
  type: procedure
  context7-sources:
    - /addyosmani/agent-skills
---

# Skill Improvement Mandate

Every agent session produces two outputs:

1. **The work** — the PR, fix, or improvement
2. **The learning** — what a future agent should know

Output 1 without Output 2 leaves the project no smarter. **The loop only compounds if agents write back.**

## Contents

- [Before You Mark Work Complete](#before-you-mark-work-complete)
- [What Counts as a Learning Worth Writing Back](#what-counts-as-a-learning-worth-writing-back)
- [Where to Write It](#where-to-write-it)
- [Which Skill File to Update](#which-skill-file-to-update)
- [How to Commit It](#how-to-commit-it)

## Before You Mark Work Complete

Run through this checklist before closing a session or marking a task done:

- [ ] Did I discover any workaround, non-obvious pattern, or convention?
- [ ] Did I fix something that was broken or confusing?
- [ ] Is there a skill file for the area I worked in?
- [ ] If yes — did I update it?
- [ ] If no — did I create one in `docs/skills/`?
- [ ] Is the skill file update committed in **this same PR**?
- [ ] Is `docs/skills/gap-tracker.md` still accurate? Did I complete any `[ ]` items?

## What Counts as a Learning Worth Writing Back

Write it when:

| Category | Example |
|---|---|
| Upstream bug / behaviour | "Textual's `Switch` uses `border: tall` (3 rows) — use `_CheckToggle` instead" |
| Non-obvious correctness requirement | "`push_screen_wait` requires `@work` — discovered twice in this codebase" |
| Convention not obvious from code | "`image_ref` has no tag — use `full_clean_ref` for display" |
| Trial-and-error discovery | "`height: auto` on `Horizontal` expands to fill, not shrink to content" |
| API gotcha | "`bootc switch` takes a positional arg, not `--target`" |

Do **not** write:
- One-off task notes ("I changed line 42 to...")
- Obvious developer knowledge ("Python uses indentation")
- Ephemeral state ("the branch is at commit abc123")
- Contradictions of existing skills — update the skill instead

## Where to Write It

| Working in… | Write to |
|---|---|
| Textual widgets, layout, CSS | `docs/skills/textual-dev.md` |
| Screens, actions, keybindings, ADW widgets | `.agents/skills/bluefinctl-dev/SKILL.md` |
| AI screen, GPU detection, quadlet deploy | `docs/skills/ai-stacks.md` |
| Human gates, when to stop | `docs/skills/human-gates.md` |
| Core architecture, new pattern that crosses screens | `.agents/skills/bluefinctl-dev/SKILL.md` |
| Implementing a completed gap-tracker item | `docs/skills/gap-tracker.md` (flip `[ ]` to `[x]`) |

## Which Skill File to Update

Use the router (`docs/SKILL.md`) to confirm which file covers your area. When in doubt, update `.agents/skills/bluefinctl-dev/SKILL.md` — it's the broadest skill and always in context.

If no skill covers your area, create one in `docs/skills/` using this template:

```markdown
---
name: my-area
description: >-
  One sentence: what this skill covers and when to use it.
  Include specific trigger phrases.
metadata:
  type: reference
---

# My Area

## When to Use
- Trigger conditions
- When NOT to use

## Core Patterns
...

## Red Flags
...

## Verification
- [ ] Exit criteria
```

## How to Commit It

Skill updates go in the **same commit or PR** as the work — never a follow-up:

```bash
# Same PR, same commit or additional commit:
git add docs/skills/textual-dev.md
git commit -m "docs(skills): add @work pattern for push_screen_wait"
```

Commit message for skill-only updates uses `docs(skills):` prefix.

## Context7 freshness rule

Whenever a skill file you are updating covers a named library, framework, or tool, verify the technical content against current docs before committing:

```
DETECT → FETCH → EMBED → CITE
```

1. **DETECT** — what library/tool does this skill cover?
2. **FETCH** — `resolve-library-id` → `query-docs` for the specific pattern being documented
3. **EMBED** — put the verified example directly in the skill file
4. **CITE** — add `context7-sources` to the frontmatter

```yaml
metadata:
  type: reference
  context7-sources:
    - /textualize/textual
```

## Canonical skill spec

All skill files must meet the [`/addyosmani/agent-skills`](https://context7.com/addyosmani/agent-skills) standard
(benchmark score 85.67 — highest-rated skill improvement source):

```
✓ Frontmatter: name + description with "Use when" trigger phrases
✓ ## When to Use  (triggering conditions)
✓ ## When NOT to Use  (exclusions)
✓ ## Core Process  (numbered workflow)
✓ ## Common Rationalizations  (excuses + rebuttals)
✓ ## Red Flags  (concrete anti-patterns)
✓ ## Verification  (exit criteria checklist)
```

Before closing a session that updated any skill, check each file against this spec. Missing Red Flags and Verification are the most common gaps.

## Red Flags

- Session ends without any skill file change after discovering a workaround
- A bug is fixed for the second time that was already documented as a pitfall
- `gap-tracker.md` has items that were implemented but not marked `[x]`
- New screen or widget created without updating `bluefinctl-dev/SKILL.md`
