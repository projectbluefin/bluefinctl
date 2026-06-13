---
name: skill-improvement
description: "The skill-improvement mandate — every agent session must produce a skill file update alongside the work. Use when completing a task and deciding whether to write a skill update, or when creating or updating a skill file."
metadata:
  type: procedure
---

# Skill Improvement Mandate

Every agent session produces two outputs:

1. **The work** — the PR, fix, or improvement
2. **The learning** — what a future agent should know

Output 1 without Output 2 leaves the project no smarter. The loop only compounds if agents write back.

## Contents
- [Before You Mark Work Complete](#before-you-mark-work-complete)
- [What Counts as a Learning Worth Writing Back](#what-counts-as-a-learning-worth-writing-back)
- [Where to Write It](#where-to-write-it)
- [Which Skill File to Update](#which-skill-file-to-update)
- [How to Commit It](#how-to-commit-it)

---

## Before You Mark Work Complete

Run this checklist before opening a PR for review or marking an issue done:

- [ ] Did I discover any workaround, non-obvious pattern, or convention?
- [ ] Is there a skill file for the area I worked in?
- [ ] If yes — did I update it?
- [ ] If no — did I create one?
- [ ] Is the skill file committed in **this same PR**? (Not a follow-up. Same PR.)

If all five are checked, you're done. If any are unchecked, finish them first.

---

## What Counts as a Learning Worth Writing Back

**Write it:**

| Category | Example |
|---|---|
| Upstream bug workaround | "Textual 1.x removed `RadioSet.action_select_button()` — set `RadioButton.value = True` directly" |
| Non-obvious correctness requirement | "`stdout=DEVNULL` is required when piping to pkexec tee — omitting it hangs the process waiting for a reader" |
| Convention not obvious from code | "Use `prevent()` not a `_loading` guard for programmatic widget state — the flag is defeated by async event ordering" |
| Trial-and-error discovery | "`vh`/`vw` CSS units are silently ignored in Textual — always use fixed terminal row counts instead" |

**Do NOT write:**

| Category | Example |
|---|---|
| One-off task note | "Use commit message `fix(bundles): reload after deactivate` for this PR" |
| Obvious developer knowledge | "Run `git status` to see changed files" |
| Ephemeral state | "The bundles screen is currently broken due to issue #42" |
| Contradiction of another skill | If a skill says X and you want to say not-X, update the skill to say not-X — don't add a new doc |

---

## Where to Write It

All learnings from work in this repo go to `docs/skills/` here. If the learning is cross-cutting (affects projectbluefin broadly), write it locally first, then open a propagation issue in `projectbluefin/actions`.

---

## Which Skill File to Update

Use the closest matching existing skill. Only create a new skill when the change introduces a new reusable domain with no existing home.

```
Changed a Textual screen or widget?    → .agents/skills/bluefinctl-dev/SKILL.md
Changed core/bundles.py?               → docs/skills/brew.md (create if absent)
Changed core/updates.py or uupd?       → docs/skills/updates.md (create if absent)
Changed bootc integration?             → docs/skills/bootc.md (create if absent)
Changed Podman/container logic?        → docs/skills/containers.md (create if absent)
Changed pytest or snapshot tests?      → docs/skills/testing.md (create if absent)
New domain entirely?                   → create docs/skills/<area>.md
```

---

## How to Commit It

The skill update goes in the **same commit or same PR** as the implementation. Not a follow-up PR. Not "I'll do it later."

```bash
# Stage both the implementation and the skill update together
git add src/bluefinctl/screens/bundles.py docs/skills/brew.md
git commit -m "feat(bundles): reload list after deactivate

Update docs/skills/brew.md with bundle state reload pattern.

Assisted-by: Claude Sonnet 4.6 via GitHub Copilot
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
