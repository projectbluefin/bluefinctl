"""CLI integration tests — exercises every subcommand via CliRunner."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from bluefinctl.cli import app

runner = CliRunner()


class TestStatusCommand:
    def test_status_runs(self) -> None:
        with patch("bluefinctl.core.system.print_status") as mock:
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        mock.assert_called_once()


class TestUpdateCommand:
    def test_update_check_flag_up_to_date(self) -> None:
        mock_info = MagicMock()
        mock_info.ref = "ghcr.io/projectbluefin/dakota:latest"
        with (
            patch("bluefinctl.core.update_runner.get_image_info", return_value=mock_info),
            patch("bluefinctl.core.update_runner.check_for_update", return_value=False),
            patch("bluefinctl.core.update_runner.get_autoupdate_containers", return_value=[]),
        ):
            result = runner.invoke(app, ["update", "--check"])
        assert result.exit_code == 0

    def test_update_check_flag_available(self) -> None:
        mock_info = MagicMock()
        mock_info.ref = "ghcr.io/projectbluefin/dakota:latest"
        with (
            patch("bluefinctl.core.update_runner.get_image_info", return_value=mock_info),
            patch("bluefinctl.core.update_runner.check_for_update", return_value=True),
            patch("bluefinctl.core.update_runner.get_autoupdate_containers", return_value=[]),
        ):
            result = runner.invoke(app, ["update", "--check"])
        assert result.exit_code == 0


class TestFocusCommand:
    def test_focus_status_off(self) -> None:
        mock_status = MagicMock()
        mock_status.focus_mode = None
        with patch(
                "bluefinctl.core.updates.get_update_status",
                new=AsyncMock(return_value=mock_status)
            ):
            result = runner.invoke(app, ["focus", "status"])
        assert result.exit_code == 0
        assert "off" in result.output.lower()

    def test_focus_status_active(self) -> None:
        mock_focus = MagicMock()
        mock_focus.active = True
        mock_focus.activated_at = "2026-06-01T10:00:00"
        mock_focus.is_stale = False
        mock_status = MagicMock()
        mock_status.focus_mode = mock_focus
        with patch(
                "bluefinctl.core.updates.get_update_status",
                new=AsyncMock(return_value=mock_status)
            ):
            result = runner.invoke(app, ["focus", "status"])
        assert result.exit_code == 0
        assert "active" in result.output.lower()

    def test_focus_on(self) -> None:
        with patch("bluefinctl.core.updates.activate_focus_mode", new=AsyncMock()):
            result = runner.invoke(app, ["focus", "on"])
        assert result.exit_code == 0
        assert "active" in result.output.lower()

    def test_focus_off(self) -> None:
        with patch("bluefinctl.core.updates.deactivate_focus_mode", new=AsyncMock()):
            result = runner.invoke(app, ["focus", "off"])
        assert result.exit_code == 0
        assert "deactivated" in result.output.lower()

    def test_focus_unknown_action(self) -> None:
        result = runner.invoke(app, ["focus", "maybe"])
        assert result.exit_code == 1


class TestAICommand:
    # Regression: B1 — ai deploy/stop with no stack was exit 0
    def test_ai_deploy_no_stack_exits_1(self) -> None:
        with patch("bluefinctl.core.ai.get_stacks", new=AsyncMock(return_value=(MagicMock(), []))):
            result = runner.invoke(app, ["ai", "deploy"])
        assert result.exit_code == 1
        assert "Usage" in result.output

    def test_ai_stop_no_stack_exits_1(self) -> None:
        with patch("bluefinctl.core.ai.get_stacks", new=AsyncMock(return_value=(MagicMock(), []))):
            result = runner.invoke(app, ["ai", "stop"])
        assert result.exit_code == 1
        assert "Usage" in result.output

    # Regression: B1 — ai badarg was exit 0
    def test_ai_unknown_action_exits_1(self) -> None:
        result = runner.invoke(app, ["ai", "badaction"])
        assert result.exit_code == 1

    def test_ai_list_runs(self) -> None:
        mock_gpu = MagicMock()
        mock_gpu.display = "No discrete GPU detected"
        with patch("bluefinctl.core.ai.get_stacks", new=AsyncMock(return_value=(mock_gpu, []))):
            result = runner.invoke(app, ["ai", "list"])
        assert result.exit_code == 0


class TestFocusModeResilience:
    # Regression: B3 — focus on/off crashed with FileNotFoundError when pkexec missing
    def test_focus_on_no_pkexec_exits_0(self) -> None:
        """focus on must not crash when pkexec is missing; state write still happens."""
        import asyncio
        from unittest.mock import patch as _patch

        from bluefinctl.core.updates import activate_focus_mode

        async def _run() -> None:
            with _patch(
                "asyncio.create_subprocess_exec",
                side_effect=FileNotFoundError("pkexec"),
            ):
                # Should complete without raising
                await activate_focus_mode()

        asyncio.run(_run())  # must not raise

    def test_focus_off_no_pkexec_exits_0(self) -> None:
        """focus off must not crash when pkexec is missing."""
        import asyncio
        from unittest.mock import patch as _patch

        from bluefinctl.core.updates import deactivate_focus_mode

        async def _run() -> None:
            with _patch(
                "asyncio.create_subprocess_exec",
                side_effect=FileNotFoundError("pkexec"),
            ):
                await deactivate_focus_mode()

        asyncio.run(_run())  # must not raise



    def test_devmode_launches_tui(self) -> None:
        """devmode subcommand creates app with start_screen='devmode'."""
        with patch("bluefinctl.app.BluefinCtl") as mock_app:
            mock_app.return_value.run = MagicMock()
            result = runner.invoke(app, ["devmode"])
        assert result.exit_code == 0
        mock_app.assert_called_once_with(start_screen="devmode")
