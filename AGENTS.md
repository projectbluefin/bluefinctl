# bluefinctl — Agent & Copilot Instructions

> **You are part of an agentic operating system, built by agentic workflows.**
>
> ## Operating principle
>
> **Humans approve design, security, and merge. Everything else is automated, self-healing, and non-blocking.**

**bluefinctl** is the Textual TUI control panel for Bluefin OS — packages, updates, containers, and devmode from one keyboard-driven dashboard.

Binaries: **`bctl`** (short) and `bluefinctl` (full). Both are the same entry point.

Home repo: [projectbluefin/bluefinctl](https://github.com/projectbluefin/bluefinctl)

## Agent fast path

```
1. docs/SKILL.md               # find the skill for your task
2. docs/skills/<area>.md       # load the relevant skill before acting
3. Use Context7 for any library/API question before writing code
4. pytest && ruff check src/ tests/ && mypy src/  # before every commit
```

**Doc-only changes** (`docs/` and `AGENTS.md`) → push directly to `main`, no PR needed.
```bash
git diff --cached --name-only  # must show only docs/* or AGENTS.md
```
**Everything else** → branch + PR targeting `main`.

## Context7 — always use for library work

Use `resolve-library-id` + `query-docs` automatically whenever the task involves:
- Any named library (Textual, Typer, pytest, bootc, skopeo…)
- API syntax, method signatures, or configuration options
- Code generation using a specific library
- Setup, installation, or migration steps

Do not rely on training data for library APIs — call Context7 first.

## Four-screen navigation

| Key | Screen | File |
|-----|--------|------|
| 1 | System | `screens/system.py` |
| 2 | Updates | `screens/updates.py` |
| 3 | Developer Mode (Kits + Tools + Environments) | `screens/devmode.py` |
| 4 | AI | `screens/ai.py` |

`screens/toolkit.py` still exists on disk but is not routed — it is a dead file.

## Self-Improvement Loop

Every agent session produces two outputs:

1. **The work** — the PR, fix, or improvement
2. **The learning** — what a future agent should know

```
Agent works on task
  └─ discovers pattern / workaround / convention
       └─ writes it to the relevant skill file in docs/skills/
            └─ commits in the same PR (never a follow-up)
                 └─ next agent starts smarter → loop
```

### What counts as a learning worth writing back

| Category | Example |
|---|---|
| Upstream behaviour | "`Switch` uses `border: tall` — 3 rows tall. Use `_CheckToggle` instead." |
| Non-obvious requirement | "`push_screen_wait` requires `@work(exclusive=True)` — discovered twice." |
| Convention not obvious from code | "`image_ref` has no tag. Use `full_clean_ref` for display." |
| Trial-and-error | "`height: auto` on Horizontal fills the screen, not shrinks to content." |

**Don't write:** one-off notes, obvious knowledge, ephemeral state. Update existing skills rather than contradicting them.

### Before marking work complete

- [ ] Did I discover any workaround, non-obvious pattern, or convention?
- [ ] Is there a skill file for the area I worked in?
- [ ] If yes — did I update it?
- [ ] If no — did I create one in `docs/skills/`?
- [ ] Is the skill file committed in **this same PR**?
- [ ] Is `docs/skills/gap-tracker.md` accurate? Did I complete any `[ ]` items?

See [`docs/skills/skill-improvement.md`](docs/skills/skill-improvement.md) for the full mandate.

## Human Decision Gates

Stop and request human input at these four gates. Never guess past them.

| Gate | Stop when |
|---|---|
| **Design** | Architecture change, new subsystem, user-visible behaviour change |
| **Security** | Auth, signing, supply chain, secrets, privilege escalation paths |
| **Breakage** | Change that could break headless CLI consumers or downstream scripts |
| **Merge** | PR ready for final review — always requires human `lgtm` |

See [`docs/skills/human-gates.md`](docs/skills/human-gates.md) for how to signal a gate and evidence requirements.

## Development Standards

### Commit format

[Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <description>`

Common types: `feat` `fix` `docs` `ci` `refactor` `chore` `build` `perf` `test` `revert`

### AI attribution

Every AI-authored commit should include both trailers:

```
feat(screens): add AI stack management screen

Assisted-by: Claude Sonnet 4.5 via pi
Co-authored-by: Claude <claude@anthropic.com>
```

### PR conventions

- **Ask before opening PRs.** Prepare the branch and diff, get explicit human approval, then open.
- **One PR per feature.** Never batch unrelated changes.
- No WIP PRs.
- PR title follows Conventional Commits format.
- Max 4 open PRs at a time.

## Build and test

```bash
pip install -e ".[dev]"

pytest                        # full suite (43 tests)
pytest tests/test_brew.py     # single file
ruff check src/ tests/        # lint
mypy src/                     # type-check (strict)
bctl                          # launch TUI
textual run --dev src/bluefinctl/app.py  # hot-reload CSS
```

`ruff` line length: 100, target Python 3.12. `mypy` strict. `pytest` asyncio_mode `auto`.

## Architecture summary

```
src/bluefinctl/
├── app.py          Textual App: screen registration, keybinds, theme
├── cli.py          Typer CLI entry point (headless path for every operation)
├── core/           Business logic — NO Textual imports, fully testable
├── screens/        One Screen subclass per panel; _modals.py for shared modals
├── widgets/        Reusable Textual widgets (adw.py, ops_bar.py, …)
├── theme/          GNOME accent color reader + bluefin.tcss
├── stacks/         Bundled AI stack quadlet files (nvidia/ and amd/)
└── util/           OSC escape sequences, Ghostty detection
```

**Rule:** All subprocess calls, file I/O, and system state live in `core/`. Screens only call core functions and present results. Every operation has a headless CLI path (`cli.py`) and a TUI path (screens).

## Analysis vs. implementation

When asked an analysis question ("what's the fix?", "how should we handle X?"), **answer the question — do not implement**. Only write or change code when explicitly asked.

## Scope discipline

Read task intent literally:

- `"fix the updates screen"` = fix only what is broken in that screen
- `"do PR reviews"` = review open PRs only — do not start fix work
- If a session could involve both, confirm scope before acting

## Verification Requirements

Do not request PR review without:

- [ ] `pytest` passing
- [ ] `ruff check src/ tests/` passing
- [ ] `mypy src/` passing (strict)
- [ ] If no automated test covers the change — describe how you manually verified it
- [ ] Skill file update committed in **this same PR** (not a follow-up)
- [ ] PR title follows Conventional Commits format
- [ ] Attribution trailers on AI-authored commits

## Skill routing

For task→skill routing, see [`docs/SKILL.md`](docs/SKILL.md).
All skill docs live in [`docs/skills/`](docs/skills/).
