"""Tests for core/operations.py — resumable operation state machine."""

from bluefinctl.core.operations import (
    Operation,
    OperationState,
    clear_completed_operations,
    load_operations,
    remove_operation,
    save_operation,
    save_operations,
)


def test_operation_lifecycle() -> None:
    """Operation transitions through states correctly."""
    op = Operation(id="test-1", kind="devmode-enable")
    assert op.state == OperationState.PREFLIGHT
    assert not op.is_terminal
    assert not op.needs_user_action

    op.transition(OperationState.EXECUTING, "Installing...")
    assert op.state == OperationState.EXECUTING
    assert op.message == "Installing..."

    op.transition(OperationState.NEEDS_RELOGIN, "Log out to apply group changes")
    assert op.needs_user_action
    assert not op.is_terminal

    op.complete("Done")
    assert op.is_terminal
    assert op.state == OperationState.COMPLETE


def test_operation_failure() -> None:
    """Operation can fail with error message."""
    op = Operation(id="test-2", kind="lima-setup")
    op.transition(OperationState.EXECUTING)
    op.fail("KVM not available")
    assert op.is_terminal
    assert op.state == OperationState.FAILED
    assert op.error == "KVM not available"


def test_operation_serialization() -> None:
    """Operations round-trip through JSON."""
    op = Operation(
        id="test-3",
        kind="bootc-switch",
        metadata={"target_ref": "ghcr.io/projectbluefin/bluefin:43-stable"},
    )
    op.transition(OperationState.NEEDS_REBOOT, "Reboot to apply")

    data = op.to_dict()
    restored = Operation.from_dict(data)

    assert restored.id == "test-3"
    assert restored.kind == "bootc-switch"
    assert restored.state == OperationState.NEEDS_REBOOT
    assert restored.metadata["target_ref"] == "ghcr.io/projectbluefin/bluefin:43-stable"


def test_persistence(tmp_path, monkeypatch) -> None:
    """Operations persist to and load from disk."""
    state_file = tmp_path / "operations.json"
    monkeypatch.setattr(
        "bluefinctl.core.operations._state_path", lambda: state_file,
    )

    op = Operation(id="persist-1", kind="test")
    save_operation(op)

    loaded = load_operations()
    assert len(loaded) == 1
    assert loaded[0].id == "persist-1"

    # Update existing
    op.transition(OperationState.COMPLETE)
    save_operation(op)
    loaded = load_operations()
    assert len(loaded) == 1
    assert loaded[0].state == OperationState.COMPLETE


def test_remove_operation(tmp_path, monkeypatch) -> None:
    """Can remove a specific operation."""
    state_file = tmp_path / "operations.json"
    monkeypatch.setattr(
        "bluefinctl.core.operations._state_path", lambda: state_file,
    )

    op1 = Operation(id="rm-1", kind="test")
    op2 = Operation(id="rm-2", kind="test")
    save_operations([op1, op2])

    remove_operation("rm-1")
    loaded = load_operations()
    assert len(loaded) == 1
    assert loaded[0].id == "rm-2"


def test_clear_completed(tmp_path, monkeypatch) -> None:
    """Clear completed removes only terminal operations."""
    state_file = tmp_path / "operations.json"
    monkeypatch.setattr(
        "bluefinctl.core.operations._state_path", lambda: state_file,
    )

    op1 = Operation(id="c-1", kind="test")
    op1.complete()
    op2 = Operation(id="c-2", kind="test")  # still in preflight

    save_operations([op1, op2])
    removed = clear_completed_operations()
    assert removed == 1

    loaded = load_operations()
    assert len(loaded) == 1
    assert loaded[0].id == "c-2"
