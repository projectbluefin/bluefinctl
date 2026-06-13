"""Resumable operation state machine.

Operations that require reboot/logout persist state and resume on next launch.
Used by: Lima setup (KVM group), devmode enable (group changes), bootc switch/rollback.

State machine:
    preflight -> executing -> needs-relogin -> needs-reboot
              -> pending-verification -> complete | failed

Persisted to: ~/.local/state/bluefinctl/operations.json
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class OperationState(StrEnum):
    """States in the resumable operation lifecycle."""

    PREFLIGHT = "preflight"
    EXECUTING = "executing"
    NEEDS_RELOGIN = "needs-relogin"
    NEEDS_REBOOT = "needs-reboot"
    PENDING_VERIFICATION = "pending-verification"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class Operation:
    """A resumable operation that may survive reboots/logouts."""

    id: str
    kind: str  # e.g. "lima-setup", "devmode-enable", "bootc-switch"
    state: OperationState = OperationState.PREFLIGHT
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    message: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    steps_total: int = 0
    steps_completed: int = 0

    def transition(self, new_state: OperationState, message: str = "") -> None:
        """Move to a new state."""
        self.state = new_state
        self.updated_at = time.time()
        if message:
            self.message = message

    def fail(self, error: str) -> None:
        """Mark operation as failed."""
        self.state = OperationState.FAILED
        self.error = error
        self.updated_at = time.time()

    def complete(self, message: str = "") -> None:
        """Mark operation as successfully completed."""
        self.state = OperationState.COMPLETE
        self.updated_at = time.time()
        if message:
            self.message = message

    @property
    def is_terminal(self) -> bool:
        """Whether this operation is in a final state."""
        return self.state in (OperationState.COMPLETE, OperationState.FAILED)

    @property
    def needs_user_action(self) -> bool:
        """Whether this operation is waiting on a user action (reboot/relogin)."""
        return self.state in (OperationState.NEEDS_RELOGIN, OperationState.NEEDS_REBOOT)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON persistence."""
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Operation:
        """Deserialize from JSON."""
        data["state"] = OperationState(data["state"])
        return cls(**data)


def _state_path() -> Path:
    """Get the operations state file path."""
    state_dir = Path.home() / ".local" / "state" / "bluefinctl"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "operations.json"


def load_operations() -> list[Operation]:
    """Load all persisted operations."""
    path = _state_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [Operation.from_dict(op) for op in data]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def save_operations(operations: list[Operation]) -> None:
    """Persist all operations to disk."""
    path = _state_path()
    path.write_text(json.dumps([op.to_dict() for op in operations], indent=2))


def get_pending_operations() -> list[Operation]:
    """Get operations that are not in a terminal state."""
    return [op for op in load_operations() if not op.is_terminal]


def get_operations_needing_action() -> list[Operation]:
    """Get operations waiting for user action (reboot/relogin)."""
    return [op for op in load_operations() if op.needs_user_action]


def save_operation(operation: Operation) -> None:
    """Save or update a single operation in the store."""
    operations = load_operations()
    # Replace existing or append
    for i, op in enumerate(operations):
        if op.id == operation.id:
            operations[i] = operation
            save_operations(operations)
            return
    operations.append(operation)
    save_operations(operations)


def remove_operation(operation_id: str) -> None:
    """Remove an operation from the store."""
    operations = [op for op in load_operations() if op.id != operation_id]
    save_operations(operations)


def clear_completed_operations() -> int:
    """Remove all completed/failed operations. Returns count removed."""
    ops = load_operations()
    active = [op for op in ops if not op.is_terminal]
    removed = len(ops) - len(active)
    save_operations(active)
    return removed
