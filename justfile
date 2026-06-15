# bluefinctl — development recipes

# Default recipe: show available commands
default:
    @just --list

# Run the TUI in a terminal
run:
    pip3 install -e . -q && bctl

# Run with hot-reload CSS (development mode)
dev:
    textual run --dev src/bluefinctl/app.py

# Run tests
test:
    python3 -m pytest tests/ -q

# Lint
lint:
    python3 -m ruff check src/ tests/

# Type check
typecheck:
    python3 -m mypy src/

# Full CI check (lint + typecheck + tests)
check: lint typecheck test

# Install in editable mode with dev dependencies
install:
    python3 -m pip install -e ".[dev]"

# Run the headless CLI status command
status:
    python3 -m bluefinctl status

# Run the headless update command
update:
    pip3 install -e . -q && python3 -m bluefinctl update

# Check for updates without applying
update-check:
    pip3 install -e . -q && python3 -m bluefinctl update --check

# Launch in Ghostty terminal (detached)
ghostty:
    ghostty -e python3 -m bluefinctl &
