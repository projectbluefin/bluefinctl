---
name: human-gates
description: >-
  Defines the four human decision gates for bluefinctl: Design, Security,
  Breakage, and Merge. Use when deciding whether to stop and ask a human,
  how to signal a blocked state, or what evidence is required before
  requesting PR review.
metadata:
  type: procedure
---

# Human Decision Gates

Stop and request human input at these four gates. Never guess past them.

## Contents
- [The Four Gates](#the-four-gates)
- [How to Signal a Gate](#how-to-signal-a-gate)
- [Verification Evidence Requirement](#verification-evidence-requirement)
- [When in Doubt](#when-in-doubt)

## The Four Gates

### 1. Design Gate

**Stop when:** The change involves a new subsystem, an architecture decision, or user-visible behaviour that wasn't explicitly requested.

Examples:
- Adding a fifth screen
- Changing the navigation model
- Changing how OpsBar state is managed globally
- Any change to `DESIGN.md`

**Signal:** Post a description of the proposed design change and wait for explicit approval before implementing.

**Do not:** Implement a design change speculatively and include it in a PR without prior discussion.

### 2. Security Gate

**Stop when:** The change touches auth, signing, privilege escalation, secrets, or supply chain.

Examples:
- Adding or changing pkexec commands
- Handling NGC API keys, HuggingFace tokens, or cosign verification
- Changing how Podman secrets are managed
- Any change to `trust.json` or how project trust is evaluated

**Signal:** Post what you're proposing to change and why, with the specific privilege paths involved. Do not implement until approved.

### 3. Breakage Gate

**Stop when:** The change could break headless CLI consumers or downstream scripts.

Examples:
- Changing `cli.py` command signatures or exit codes
- Removing or renaming a `core/` function that CLI paths call
- Changing JSON output format from `--json` flags
- Removing a `bctl` subcommand

**Signal:** List the affected CLI paths and confirm the change is intentional before merging.

### 4. Merge Gate

**Stop when:** Your PR is ready for final review and merge.

This gate is always human. CI passing + `lgtm` from a human reviewer is required before merge. Agents never self-merge.

## How to Signal a Gate

When you hit a gate, post a message in this format:

```
GATE: [Design|Security|Breakage|Merge]

What I was doing: <one sentence>
What triggered the gate: <specific condition>
What I need from you: <approval / decision / review>

Options I see:
1. <option A>
2. <option B>

Recommended: <your recommendation and reasoning>
```

Then stop. Do not continue implementing until you receive explicit direction.

## Verification Evidence Requirement

Before requesting formal review, ALL of the following must be true:

- [ ] `pytest` passing
- [ ] `ruff check src/ tests/` passing
- [ ] `mypy src/` passing (strict)
- [ ] If no automated test covers the change — describe how you manually verified it
- [ ] Skill file update committed in **this same PR** (not a follow-up)
- [ ] PR title follows Conventional Commits format (`feat:`, `fix:`, `docs:`, etc.)
- [ ] Attribution trailers on every AI-authored commit:
  ```
  Assisted-by: <Model> via GitHub Copilot
  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
  ```

Do not request review until all are checked.

## When in Doubt

If you are unsure whether a gate applies, treat it as if it does. The cost of an unnecessary check-in is low. The cost of a wrong architecture decision or security issue is high.

## Red Flags

- Implementing a feature that was never explicitly requested → Design Gate
- Calling `pkexec` with a new command that wasn't in the existing codebase → Security Gate
- Changing a `cli.py` function signature or removing a subcommand → Breakage Gate
- Opening a PR without running the full verification checklist → Merge Gate not met
