"""Tests for DevMode tool inventory and interactive tools tab."""

from __future__ import annotations

import pytest
from textual.widgets import ListView

from bluefinctl.app import BluefinCtl
from bluefinctl.core.devmode import get_dev_tools_status
from bluefinctl.screens.devmode import DevModeScreen, ToolsTab


def test_dev_tools_status_uses_shutil_which(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tool status comes from command availability."""
    monkeypatch.setattr(
        "bluefinctl.core.devmode.shutil.which",
        lambda command: "/usr/bin/kind" if command == "kind" else None,
    )

    tools = {tool.slug: tool for tool in get_dev_tools_status()}

    assert tools["kind"].installed is True
    assert tools["dive"].installed is False


def test_devmode_enter_binding_exists() -> None:
    """Enter is wired to install the selected tool."""
    bindings = {(binding.key, binding.action) for binding in DevModeScreen.BINDINGS}
    assert ("enter", "install_selected_tool") in bindings


@pytest.mark.asyncio
async def test_tools_tab_is_interactive_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tools tab renders a selectable ListView, not a static label."""
    monkeypatch.setattr("bluefinctl.app._is_bootc_system", lambda: False)
    monkeypatch.setattr("bluefinctl.core.devmode.shutil.which", lambda _command: None)

    app = BluefinCtl(start_screen="devmode")
    async with app.run_test() as pilot:
        await pilot.pause()
        tools_tab = app.screen.query_one(ToolsTab)
        assert isinstance(tools_tab.query_one("#tools-list", ListView), ListView)
