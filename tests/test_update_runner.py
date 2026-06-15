"""Tests for core/update_runner.py."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from bluefinctl.core.update_runner import (
    BootcEvent,
    ImageInfo,
    get_image_info,
    run_brew_update,
    run_distrobox_update,
    run_flatpak_update,
)

# ── get_image_info ────────────────────────────────────────────────────────────

class TestGetImageInfo:
    def test_returns_empty_on_failure(self) -> None:
        with patch("subprocess.run", side_effect=Exception("no bootc")):
            info = get_image_info()
        assert isinstance(info, ImageInfo)
        assert info.ref == ""

    def test_returns_empty_on_nonzero_returncode(self) -> None:
        mock = MagicMock()
        mock.returncode = 1
        mock.stdout = ""
        with patch("subprocess.run", return_value=mock):
            info = get_image_info()
        assert info.ref == ""

    def test_parses_ref_and_version(self) -> None:
        payload = {
            "status": {
                "booted": {
                    "image": {
                        "image": {
                            "image": "ghcr.io/projectbluefin/bluefin:latest",
                            "digest": "sha256:abc123",
                        }
                    },
                    "ostree": {"version": "20250610.0"},
                }
            }
        }
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps(payload)
        with patch("subprocess.run", return_value=mock):
            info = get_image_info()
        assert info.ref == "ghcr.io/projectbluefin/bluefin:latest"
        assert info.version == "20250610.0"
        assert info.digest == "sha256:abc123"


# ── run_flatpak_update ────────────────────────────────────────────────────────

class TestRunFlatpakUpdate:
    async def test_already_up_to_date(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"Nothing to do.\n", b"")
        )
        with patch(
            "bluefinctl.core.update_runner.asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            ok, summary = await run_flatpak_update()
        assert ok is True
        assert "up to date" in summary

    async def test_counts_updated_apps(self) -> None:
        output = (
            b"Updating org.gnome.Calculator/x86_64/stable\n"
            b"Updating org.mozilla.firefox/x86_64/stable\n"
        )
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(output, b""))
        with patch(
            "bluefinctl.core.update_runner.asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            ok, summary = await run_flatpak_update()
        assert ok is True
        assert "2 apps" in summary

    async def test_failure_returns_failed(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"error\n", b""))
        with patch(
            "bluefinctl.core.update_runner.asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            ok, summary = await run_flatpak_update()
        assert ok is False
        assert "failed" in summary


# ── run_brew_update ───────────────────────────────────────────────────────────

class TestRunBrewUpdate:
    async def test_already_up_to_date(self) -> None:
        mock_fetch = AsyncMock()
        mock_fetch.returncode = 0
        mock_fetch.wait = AsyncMock()

        mock_upgrade = AsyncMock()
        mock_upgrade.returncode = 0
        mock_upgrade.communicate = AsyncMock(return_value=(b"Already up-to-date.\n", b""))

        call_count = 0

        async def fake_exec(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            return mock_fetch if call_count == 1 else mock_upgrade

        with patch(
            "bluefinctl.core.update_runner.asyncio.create_subprocess_exec",
            side_effect=fake_exec,
        ):
            ok, summary = await run_brew_update()
        assert ok is True
        assert "up to date" in summary

    async def test_counts_upgraded_formulae(self) -> None:
        mock_fetch = AsyncMock()
        mock_fetch.returncode = 0
        mock_fetch.wait = AsyncMock()

        upgrade_output = b"==> Upgrading 3 outdated packages:\nripgrep 14.1.0 -> 14.1.1\n"
        mock_upgrade = AsyncMock()
        mock_upgrade.returncode = 0
        mock_upgrade.communicate = AsyncMock(return_value=(upgrade_output, b""))

        call_count = 0

        async def fake_exec2(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            return mock_fetch if call_count == 1 else mock_upgrade

        with patch(
            "bluefinctl.core.update_runner.asyncio.create_subprocess_exec",
            side_effect=fake_exec2,
        ):
            ok, _summary = await run_brew_update()
        assert ok is True


# ── run_distrobox_update ──────────────────────────────────────────────────────

class TestRunDistroboxUpdate:
    async def test_not_installed_returns_success(self) -> None:
        with patch(
            "bluefinctl.core.update_runner.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError,
        ):
            ok, summary = await run_distrobox_update()
        assert ok is True
        assert "not installed" in summary

    async def test_success(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        with patch(
            "bluefinctl.core.update_runner.asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            ok, summary = await run_distrobox_update()
        assert ok is True
        assert summary == "done"


# ── BootcEvent ────────────────────────────────────────────────────────────────

class TestBootcEvent:
    def test_defaults(self) -> None:
        ev = BootcEvent(type="ProgressSteps", task="pulling")
        assert ev.steps == 0
        assert ev.steps_total == 0
        assert ev.bytes_ == 0
        assert ev.bytes_total == 0
        assert ev.description == ""
