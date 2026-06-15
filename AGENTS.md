# bluefinctl — Agent & Copilot Instructions

> **You are part of an agentic operating system, built by agentic workflows.**
>
> **Humans approve design, security, and merge. Everything else is automated, self-healing, and non-blocking.**

**bluefinctl** is the TUI control panel for [Bluefin OS](https://projectbluefin.io) — system updates, developer tooling, and AI workstation management from one keyboard-driven terminal dashboard.

Binaries: **`bctl`** (short alias) and `bluefinctl` (full name). Same entry point.

Home repo: [projectbluefin/bluefinctl](https://github.com/projectbluefin/bluefinctl)

---

## Agent fast path

```
1. docs/SKILL.md                  # skill router — find the right skill for your task
2. docs/skills/<area>.md          # load the skill before acting
3. Use Context7 for any library   # resolve-library-id → query-docs, every time
4. pytest && ruff check && mypy   # must pass before every commit
```

**Doc-only changes** (`docs/`, `AGENTS.md`, `README.md`) → push directly to `main`.
```bash
git diff --cached --name-only   # confirm only docs/* or AGENTS.md
```
**Everything else** → feature branch + PR targeting `main`.

---

## Repo layout

```
src/bluefinctl/
├── app.py               Textual App — screens, theme, keybinds
├── cli.py               Typer CLI — headless path for every operation
├── core/                Business logic — NO Textual imports, fully testable
│   ├── updates.py       bootc status, strategy, focus mode, reboot management
│   ├── update_runner.py bctl update orchestration (bootc → flatpak/brew/distrobox)
│   ├── devmode.py       developer tooling, Lima, group management
│   ├── brew.py          Brewfile management
│   ├── flatpak.py       Flatpak search/install
│   └── ai.py            GPU-accelerated AI stack management
├── screens/             One Screen per panel (system, updates, devmode, ai)
├── widgets/             adw.py (HIG library), ops_bar.py, rollback_calendar.py
├── theme/               GNOME accent color reader + bluefin.tcss
└── util/                OSC escape sequences, Ghostty detection
```

**Rule:** All subprocess calls, file I/O, and system state live in `core/`. Screens only call core functions and present results. Every operation has a headless CLI path and a TUI path.

---

## Three-screen navigation

| Key | Screen | File |
|-----|--------|------|
| 1 | System | `screens/system.py` |
| 2 | Updates | `screens/updates.py` |
| 3 | Developer | `screens/devmode.py` |
| — | AI | `screens/ai.py` (hidden, not routed in 1.0) |

`screens/toolkit.py` exists on disk but is not routed — dead file, do not touch.

---

## Context7 — mandatory for all library work

Use `resolve-library-id` + `query-docs` **before writing any code** that involves:
- Any named library (Textual, Typer, pytest, Rich, bootc, skopeo…)
- API syntax, method signatures, or configuration options
- Version migration, setup, or upgrade paths
- **Updating a skill file that covers a library** — fetch current docs before committing

Training data for library APIs is stale. Context7 has current docs. This rule is unconditional.

Note the library ID in skill frontmatter:
```yaml
metadata:
  context7-sources:
    - /textualize/textual
    - /tiangolo/typer
```

---

## Self-improvement loop

Every agent session produces two outputs:

1. **The work** — the PR, fix, or feature
2. **The learning** — what the next agent needs to know

```
work on task
  └─ discover pattern / workaround / convention
       └─ write it to the relevant docs/skills/ file
            └─ commit in the same PR (never a follow-up)
                 └─ next agent starts smarter → loop
```

### Worth writing back

| Category | Example |
|---|---|
| Upstream behaviour | "`Switch` is 3 rows tall. Use `_CheckToggle` instead." |
| Non-obvious requirement | "`push_screen_wait` requires `@work(exclusive=True)`." |
| Convention | "`image_ref` has no tag. Use `full_clean_ref` for display." |
| bootc patterns | "`--progress-fd N` yields JSON through asyncio pipe; sudo preserves fds." |

**Don't write:** one-off notes, obvious knowledge, ephemeral state.

### Before marking work complete

- [ ] Did I discover any workaround, non-obvious pattern, or convention?
- [ ] Is there a skill file for the area I worked in?
- [ ] If yes — did I update it?
- [ ] If no — did I create one in `docs/skills/`?
- [ ] Skill file committed in **this same PR** (not a follow-up)
- [ ] `docs/skills/gap-tracker.md` updated if I completed a `⬜` item

See [`docs/skills/skill-improvement.md`](docs/skills/skill-improvement.md).

---

## Human decision gates

Stop and ask at these four gates. Never guess past them.

| Gate | Stop when |
|---|---|
| **Design** | Architecture change, new subsystem, user-visible behaviour change |
| **Security** | Auth, signing, supply chain, secrets, privilege escalation |
| **Breakage** | Change that could break headless CLI consumers or downstream scripts |
| **Merge** | PR ready for final review — always requires human `lgtm` |

See [`docs/skills/human-gates.md`](docs/skills/human-gates.md).

---

## Build and test

```bash
pip install -e ".[dev]"

just run                      # reinstalls editable → launches bctl
just dev                      # hot-reload CSS (textual run --dev)
pytest                        # full suite
ruff check src/ tests/        # lint (line length 100, target 3.12)
mypy src/                     # type-check (strict)
```

---

## PR and commit conventions

### Commit format — Conventional Commits

```
feat(screens): add rollback calendar
fix(cli): handle missing bootc gracefully
docs(skills): update textual-dev with _CheckToggle pattern
```

Types: `feat` `fix` `docs` `ci` `refactor` `chore` `build` `perf` `test` `revert`

### AI attribution

Every AI-authored commit must include both trailers:

```
feat(update): replace uupd with async update_runner

Assisted-by: Claude Sonnet 4 via pi
Co-authored-by: Claude <claude@anthropic.com>
```

### PR rules

- **Ask before opening.** Prepare branch + diff, get explicit human approval first.
- **One PR per feature.** Never batch unrelated changes.
- No WIP PRs.
- PR title follows Conventional Commits.
- Max 4 open PRs at a time.
- Every PR requires review from [@projectbluefin/maintainers](https://github.com/orgs/projectbluefin/teams/maintainers).

---

## Verification checklist

Do not request PR review without all of these:

- [ ] `pytest` passing
- [ ] `ruff check src/ tests/` clean
- [ ] `mypy src/` clean (strict)
- [ ] Manual verification described if no automated test covers the change
- [ ] Skill file updated in **this same PR**
- [ ] `gap-tracker.md` updated if applicable
- [ ] PR title follows Conventional Commits
- [ ] AI attribution trailers on all AI-authored commits

---

## Skill routing

See [`docs/SKILL.md`](docs/SKILL.md) for the full task → skill table.
All skill files live in [`docs/skills/`](docs/skills/).

---

## Release process

Releases are tagged `vX.Y.Z` on `main`. The release workflow (`.github/workflows/release.yml`):
1. Runs tests
2. Builds wheel + sdist
3. Creates GitHub Release with assets attached
4. Updates `Formula/bluefinctl.rb` SHA256 automatically

To cut a release: `git tag vX.Y.Z && git push origin vX.Y.Z`

### Homebrew tap

Users can install via the tap served from this repo:
```bash
brew tap projectbluefin/bluefinctl
brew install bluefinctl
```

Formula lives at `Formula/bluefinctl.rb`. SHA256 is updated by the release workflow.

---

## Scope discipline

Read task intent literally:
- `"fix the updates screen"` = fix only what is broken in that screen
- `"do PR reviews"` = review open PRs only — do not start fix work
- If a session could involve both, confirm scope before acting

When asked an analysis question ("what's the fix?", "how should we handle X?"), **answer the question — do not implement**. Only write or change code when explicitly asked.
