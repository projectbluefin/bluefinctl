---
name: human-gates
description: "The four human decision gates — Design, Security, Breakage, and Merge — when an agent must stop and request human input. Use when uncertain whether a change requires human review, or to verify evidence requirements before opening a PR."
metadata:
  type: procedure
---

# Human Decision Gates

Agents implement autonomously **except** at these four gates. At each gate, stop work and request human input explicitly. Never guess past a gate.

## Contents
- [The Four Gates](#the-four-gates)
- [How to Signal a Gate](#how-to-signal-a-gate)
- [Verification Evidence Requirement](#verification-evidence-requirement)
- [When in Doubt](#when-in-doubt)

---

## The Four Gates

### 1. Design Gate

**Stop when:** You are about to make an architecture change, introduce a new subsystem, or change behavior that is visible to users.

Examples:
- Adding a new panel or changing the navigation model
- Changing how the headless CLI subcommands work
- Restructuring `core/` modules or changing their public API
- Changing the theme system or how GNOME accent color is applied

**Action:** Describe your proposed design clearly: what you're proposing, why, and what you're uncertain about. Ask for human approval before writing code or opening a PR.

---

### 2. Security Gate

**Stop when:** Your change touches privilege escalation, secrets handling, or supply chain.

Examples:
- Adding a new `pkexec` call or changing polkit policy interaction
- Changing how `/etc/` writes are gated
- Adding new external process invocations with user-controlled input
- Changing how bootc image references are validated before switching

**Action:** Describe exactly which security property is affected and what your proposed approach preserves or changes. Ask for explicit human approval before opening any PR.

---

### 3. Breakage Gate

**Stop when:** Your change could break headless CLI consumers, scripting users, or downstream Bluefin OS behavior.

Examples:
- Changing a `bluefinctl <subcommand>` interface or exit codes
- Changing how uupd config is written (could affect running systems)
- Modifying bundle state logic in a way that could orphan packages
- Changing default behavior of `bluefinctl status` (used in scripts)

**Action:** Identify all affected consumers before opening the PR. Confirm no consumer will silently break.

---

### 4. Merge Gate

**Stop when:** Your PR is ready for final review and merge.

This gate is always human. CI passing + `lgtm` from a human reviewer is required before merge. Agents never self-merge.

---

## How to Signal a Gate

When you hit a gate:

1. Stop. Present what you've done (branch, diff) and what decision is needed — do NOT open a PR yet.
2. Describe the gate clearly:
   ```
   Hitting the Security Gate — need human approval before opening a PR.

   Proposed change: [describe it]
   Security property affected: [what it is]
   My approach: [what you're proposing]
   ```
3. Wait for explicit human approval before opening a PR.

---

## Verification Evidence Requirement

Before requesting formal review, ALL of the following must be true:

- [ ] `pytest` passing
- [ ] `ruff check src/ tests/` passing
- [ ] `mypy src/` passing (strict)
- [ ] If no automated test covers the change — describe how you manually verified it
- [ ] Skill file update committed in **this same PR** (not a follow-up)
- [ ] PR title follows Conventional Commits format (`feat:`, `fix:`, `docs:`, etc.)
- [ ] Both attribution trailers on every AI-authored commit:
  ```
  Assisted-by: <Model> via GitHub Copilot
  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
  ```

Do not request review until all are checked.

---

## When in Doubt

If you are uncertain whether something hits a gate — it does. Describe what you're doing and what you're uncertain about, and ask. A short human answer costs less than a wrong implementation.
