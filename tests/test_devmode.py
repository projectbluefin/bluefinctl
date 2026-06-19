"""Tests for DevMode screen and developer tool detection."""

from __future__ import annotations

import pytest

from bluefinctl.app import BluefinCtl
from bluefinctl.core.devmode import get_dev_tools_status
from bluefinctl.screens.devmode import DevModeScreen


def test_dev_tools_status_uses_shutil_which(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tool status comes from command availability."""
    monkeypatch.setattr(
        "bluefinctl.core.devmode.shutil.which",
        lambda command: "/usr/bin/kind" if command == "kind" else None,
    )

    tools = {tool.slug: tool for tool in get_dev_tools_status()}

    assert tools["kind"].installed is True
    assert tools["dive"].installed is False


def test_devmode_screen_no_old_bindings() -> None:
    """New feature-portal design has no 'enter/install', 'a/install_all', or 'c' bindings."""
    binding_actions = {binding.action for binding in DevModeScreen.BINDINGS}
    assert "install_selected_tool" not in binding_actions
    assert "install_all" not in binding_actions
    assert "launch_podman_tui" not in binding_actions


@pytest.mark.asyncio
async def test_devmode_screen_renders_install_buttons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Developer screen renders Install buttons for all known tool IDs."""
    monkeypatch.setattr("bluefinctl.app._is_bootc_system", lambda: False)
    # Mock all detectors to False (not installed)
    for detector in (
        "is_docker_installed",
        "is_podman_desktop_installed",
        "is_lima_installed",
        "is_vscode_installed",
        "is_vscodium_installed",
        "is_zed_installed",
        "is_jetbrains_installed",
        "is_neovim_installed",
        "is_helix_installed",
        "is_vms_installed",
    ):
        monkeypatch.setattr(f"bluefinctl.core.devmode.{detector}", lambda: False)

    from textual.widgets import Button

    app = BluefinCtl(start_screen="devmode")
    async with app.run_test() as pilot:
        await pilot.pause()
        buttons = app.screen.query(Button)
        # Each tool should have an Install button
        btn_ids = {btn.id for btn in buttons}
        assert "install-docker" in btn_ids
        assert "install-lima" in btn_ids
        assert "install-vscode" in btn_ids
        assert "install-vms" in btn_ids


def test_get_remove_steps_dispatcher_covers_all_tools() -> None:
    """get_remove_steps dispatches for every tool that get_install_steps handles."""
    import asyncio
    import inspect

    from bluefinctl.core.devmode import TOOL_NAMES, get_remove_steps

    async def _check() -> None:
        for tool_id in TOOL_NAMES:
            gen = get_remove_steps(tool_id)
            assert inspect.isasyncgen(gen), f"{tool_id} remove steps is not an async generator"
            await gen.aclose()

    asyncio.run(_check())


async def _run_remove(tool_id: str) -> None:
    from bluefinctl.core.devmode import get_remove_steps
    async for _ in get_remove_steps(tool_id):
        pass


def test_get_remove_steps_raises_for_unknown() -> None:
    """get_remove_steps raises ValueError for unknown tool IDs."""
    import asyncio

    import pytest

    with pytest.raises(ValueError, match="Unknown tool"):
        asyncio.run(_run_remove("nonexistent-tool"))
