# bluefinctl — Agent & Copilot Instructions

> **You are part of an agentic operating system, built by agentic workflows.**
>
> ## Operating principle
>
> **Humans approve design, security, and merge. Everything else is automated, self-healing, and non-blocking.**
>
> Manual orchestration is a reliability tax. Every step that does not require human accountability is automated, and every automated step must self-heal. Agents implement; humans set direction.

**bluefinctl** is the Textual TUI control panel for Bluefin OS — packages, updates, containers, and devmode from one keyboard-driven dashboard.

Home repo: [projectbluefin/bluefinctl](https://github.com/projectbluefin/bluefinctl)

## Agent fast path

```
1. docs/SKILL.md              # find the skill for your task
2. docs/skills/<area>.md      # load the relevant skill before acting
3. pytest && ruff check src/ tests/ && mypy src/  # before every commit
```

**Doc-only changes** (`docs/` and `AGENTS.md`) → push directly to `main`, no PR needed. Before using this exception, verify all staged changes are docs-only:
```bash
git diff --cached --name-only  # must show only docs/* or AGENTS.md
```
**Everything else** → branch + PR targeting `main`.

## Self-Improvement Loop

Every agent session produces two outputs:

1. **The work** — the PR, fix, or improvement
2. **The learning** — what a future agent should know

Output 1 without Output 2 leaves the project no smarter. **The loop only compounds if agents write back.**

```
Agent works on task
  └─ discovers pattern / workaround / convention
       └─ writes it to the relevant skill file in docs/skills/
            └─ commits in the same PR (never a follow-up)
                 └─ next agent starts smarter → loop
```

### What counts as a learning worth writing back

**Write it:**

| Category | Example |
|---|---|
| Upstream bug workaround | "Textual 1.x broke RadioSet.action_select_button — set RadioButton.value directly instead" |
| Non-obvious correctness requirement | "`stdout=DEVNULL` is required on pkexec tee — omitting it leaves the process hanging for a reader" |
| Convention not obvious from code | "Use `prevent()` not a `_loading` flag for programmatic widget state — the flag is defeated by async event ordering" |
| Trial-and-error discovery | "`vh`/`vw` CSS units are silently ignored in Textual — use fixed row counts" |

**Don't write it:** one-off task notes, obvious developer knowledge, ephemeral state, contradictions of existing skills (update the skill instead).

### Where learnings live

| Working in... | Write to |
|---|---|
| `bluefinctl` | `docs/skills/` in this repo |
| Cross-cutting with projectbluefin | Local first, open a propagation issue in `projectbluefin/actions` |

### Before marking work complete — checklist

- [ ] Did I discover any workaround, non-obvious pattern, or convention?
- [ ] Is there a skill file for the area I worked in?
- [ ] If yes — did I update it?
- [ ] If no — did I create one in `docs/skills/`?
- [ ] Is the skill file committed in **this same PR**?

See [`docs/skills/skill-improvement.md`](docs/skills/skill-improvement.md) for the full mandate.

## Human Decision Gates

Stop and request human input at these four gates. Never guess past them.

| Gate | Stop when |
|---|---|
| **Design** | Architecture change, new subsystem, user-visible behavior change |
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

Implements the AI screen with GPU detection and model listing.

Assisted-by: Claude Sonnet 4.6 via GitHub Copilot
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
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

# Run full suite
pytest

# Run single test file / single test
pytest tests/test_brew.py
pytest tests/test_brew.py::test_name

# Lint and type-check
ruff check src/ tests/
mypy src/

# Hot-reload dev mode
textual run --dev src/bluefinctl/app.py
```

`ruff` line length: 100, target Python 3.12. `mypy` runs in strict mode. `pytest` asyncio_mode is `auto`.

## Architecture summary

```
src/bluefinctl/
├── app.py          Textual App: screen registration, keybinds, theme
├── cli.py          Typer CLI entry point (headless path for every operation)
├── core/           Business logic — NO Textual imports, fully testable
├── screens/        One Screen subclass per panel; _modals.py for shared modals
├── widgets/        Reusable Textual widgets
├── theme/          GNOME accent color reader + bluefin.tcss
└── util/           OSC escape sequences, Ghostty detection
```

**Rule:** All subprocess calls, file I/O, and system state live in `core/`. Screens only call core functions and present results. Every operation has a headless CLI path (`cli.py`) and a TUI path (screens).

## Analysis vs. implementation

When asked an analysis question ("what's the fix?", "how should we handle X?"), **answer the question — do not implement**. Only write or change code when explicitly asked. Discussing a solution and implementing it are separate steps.

## Scope discipline

Read task intent literally:

- `"fix the bundles screen"` = fix only what is broken in that screen
- `"do PR reviews"` = review open PRs only — do not start fix work
- If a session could involve both, confirm scope with the user before acting

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
