"""Tests for Smart Reboot strategy helpers in core/updates.py."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from bluefinctl.core.updates import (
    _REBOOT_SERVICE_UNIT,
    _REBOOT_TIMER_SERVICE_UNIT,
    get_reboot_strategy,
    set_reboot_on_logout,
    set_scheduled_reboot_window,
)

# ─── get_reboot_strategy ──────────────────────────────────────────────────────

def test_get_reboot_strategy_both_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Returns False for both strategies when marker and timer files are absent."""
    monkeypatch.setattr("bluefinctl.core.updates._REBOOT_MARKER", tmp_path / "no-marker")
    monkeypatch.setattr("bluefinctl.core.updates._TIMER_FILE", tmp_path / "no-timer")
    result = get_reboot_strategy()
    assert result == {"reboot-on-logout": False, "sched-reboot-window": False}


def test_get_reboot_strategy_marker_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Marker file present → reboot-on-logout is True."""
    marker = tmp_path / "reboot-on-logout"
    marker.touch()
    monkeypatch.setattr("bluefinctl.core.updates._REBOOT_MARKER", marker)
    monkeypatch.setattr("bluefinctl.core.updates._TIMER_FILE", tmp_path / "no-timer")
    result = get_reboot_strategy()
    assert result["reboot-on-logout"] is True
    assert result["sched-reboot-window"] is False


def test_get_reboot_strategy_timer_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Timer file present → sched-reboot-window is True."""
    timer = tmp_path / "bluefinctl-reboot-window.timer"
    timer.touch()
    monkeypatch.setattr("bluefinctl.core.updates._REBOOT_MARKER", tmp_path / "no-marker")
    monkeypatch.setattr("bluefinctl.core.updates._TIMER_FILE", timer)
    result = get_reboot_strategy()
    assert result["reboot-on-logout"] is False
    assert result["sched-reboot-window"] is True


# ─── set_reboot_on_logout ─────────────────────────────────────────────────────

@pytest.fixture
def _mock_systemctl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub out asyncio.create_subprocess_exec so systemctl calls are no-ops."""
    fake_proc = MagicMock()
    fake_proc.wait = AsyncMock(return_value=0)
    mock = AsyncMock(return_value=fake_proc)
    monkeypatch.setattr("asyncio.create_subprocess_exec", mock)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_systemctl")
async def test_set_reboot_on_logout_enable_creates_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enabling reboot-on-logout writes marker + service unit."""
    marker   = tmp_path / "reboot-on-logout"
    svc_dir  = tmp_path / "session.target.wants"
    svc_file = svc_dir / "bluefinctl-reboot.service"

    monkeypatch.setattr("bluefinctl.core.updates._REBOOT_CONFIG_DIR", tmp_path)
    monkeypatch.setattr("bluefinctl.core.updates._REBOOT_MARKER", marker)
    monkeypatch.setattr("bluefinctl.core.updates._REBOOT_SERVICE_DIR", svc_dir)
    monkeypatch.setattr("bluefinctl.core.updates._REBOOT_SERVICE", svc_file)

    await set_reboot_on_logout(True)

    assert marker.exists(), "Marker file must be created"
    assert svc_file.exists(), "Service unit file must be written"
    content = svc_file.read_text()
    assert "RemainAfterExit=yes" in content, "Service must have RemainAfterExit=yes"
    assert "ExecStart=/bin/true" in content, "Service must have ExecStart=/bin/true"
    assert "jq" in content, "Staged check must use jq"
    assert not re.search(r"grep -q.*staged", content), "grep-based staged check must be removed"


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_systemctl")
async def test_set_reboot_on_logout_disable_removes_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabling reboot-on-logout removes marker + service unit."""
    marker   = tmp_path / "reboot-on-logout"
    svc_dir  = tmp_path / "session.target.wants"
    svc_dir.mkdir()
    svc_file = svc_dir / "bluefinctl-reboot.service"
    marker.touch()
    svc_file.write_text("dummy")

    monkeypatch.setattr("bluefinctl.core.updates._REBOOT_CONFIG_DIR", tmp_path)
    monkeypatch.setattr("bluefinctl.core.updates._REBOOT_MARKER", marker)
    monkeypatch.setattr("bluefinctl.core.updates._REBOOT_SERVICE_DIR", svc_dir)
    monkeypatch.setattr("bluefinctl.core.updates._REBOOT_SERVICE", svc_file)

    await set_reboot_on_logout(False)

    assert not marker.exists(), "Marker file must be removed"
    assert not svc_file.exists(), "Service unit file must be removed"


# ─── set_scheduled_reboot_window ─────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_systemctl")
async def test_set_scheduled_reboot_window_enable_writes_units(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enabling the scheduled window writes timer + service unit files."""
    timer_file   = tmp_path / "bluefinctl-reboot-window.timer"
    service_file = tmp_path / "bluefinctl-reboot-window.service"

    monkeypatch.setattr("bluefinctl.core.updates._TIMER_FILE", timer_file)
    monkeypatch.setattr("bluefinctl.core.updates._TIMER_SERVICE_FILE", service_file)

    await set_scheduled_reboot_window(True)

    assert timer_file.exists(), "Timer unit file must be written"
    assert service_file.exists(), "Timer service unit file must be written"
    svc_content = service_file.read_text()
    assert "jq" in svc_content, "Timer service staged check must use jq"
    assert not re.search(r"grep -q.*staged", svc_content), "grep staged must be removed"
    assert "OnCalendar" in timer_file.read_text()


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_systemctl")
async def test_set_scheduled_reboot_window_disable_removes_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabling the scheduled window removes both unit files."""
    timer_file   = tmp_path / "bluefinctl-reboot-window.timer"
    service_file = tmp_path / "bluefinctl-reboot-window.service"
    timer_file.write_text("dummy-timer")
    service_file.write_text("dummy-service")

    monkeypatch.setattr("bluefinctl.core.updates._TIMER_FILE", timer_file)
    monkeypatch.setattr("bluefinctl.core.updates._TIMER_SERVICE_FILE", service_file)

    await set_scheduled_reboot_window(False)

    assert not timer_file.exists(), "Timer file must be removed when disabled"
    assert not service_file.exists(), "Timer service file must be removed when disabled"


# ─── Service unit content invariants ─────────────────────────────────────────

def test_reboot_service_unit_has_remain_after_exit() -> None:
    """_REBOOT_SERVICE_UNIT must have RemainAfterExit=yes so it fires at logout."""
    assert "RemainAfterExit=yes" in _REBOOT_SERVICE_UNIT
    assert "ExecStart=/bin/true" in _REBOOT_SERVICE_UNIT


def test_reboot_service_unit_no_grep_staged() -> None:
    """Both service units must not use grep for staged detection."""
    assert not re.search(r"grep -q.*staged", _REBOOT_SERVICE_UNIT)
    assert not re.search(r"grep -q.*staged", _REBOOT_TIMER_SERVICE_UNIT)


def test_reboot_service_unit_uses_jq() -> None:
    """Both service units use jq for staged detection (replaces false-positive grep)."""
    assert "jq" in _REBOOT_SERVICE_UNIT
    assert "jq" in _REBOOT_TIMER_SERVICE_UNIT
