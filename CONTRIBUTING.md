# bluefinctl development

## Setup

```bash
pip install -e ".[dev]"
```

## Run in dev mode

```bash
textual run --dev src/bluefinctl/app.py
```

## Test

```bash
pytest
ruff check src/ tests/
mypy src/
```

## Project Structure

- `src/bluefinctl/core/` — Business logic (no TUI dependency, fully testable)
- `src/bluefinctl/screens/` — Textual Screen classes (one per panel)
- `src/bluefinctl/widgets/` — Custom Textual widgets
- `src/bluefinctl/theme/` — GNOME accent color + Textual CSS
- `src/bluefinctl/util/` — Terminal integration (OSC, Ghostty)
- `src/bluefinctl/cli.py` — Typer CLI entry point
- `src/bluefinctl/app.py` — Textual App class

## Design Principle

Every operation has TWO paths:
1. **Headless CLI** — `bluefinctl <subcommand>` works without TUI (scriptable)
2. **TUI interactive** — Same logic, presented in Textual screens

The `core/` module contains ALL business logic. Screens are thin presentation layers.
