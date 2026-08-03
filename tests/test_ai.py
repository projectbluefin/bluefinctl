"""Tests for AI stack/tool screen wiring."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from textual.widgets import ListView

from bluefinctl.app import BluefinCtl
from bluefinctl.screens.ai import AIScreen, ToolsTab


def test_lemonade_quadlet_v11_uses_unprivileged_cache_paths() -> None:
    """Lemonade v11 needs writable cache mounts owned by its non-root user."""
    container = (
        Path(__file__).parents[1] / "src/bluefinctl/stacks/amd/lemonade/lemonade.container"
    ).read_text()

    assert "Image=ghcr.io/lemonade-sdk/lemonade-server:v11.0.0" in container
    assert (
        "Volume=%h/ai-workspaces/lemonade/cache:/opt/lemonade/.cache/huggingface:z,U"
        in container
    )
    assert (
        "Volume=%h/ai-workspaces/lemonade/config:/opt/lemonade/.cache/lemonade:z,U"
        in container
    )
    assert "/root/.cache" not in container


def test_ai_screen_has_no_filter_placeholder() -> None:
    """The placeholder category filter binding/action was removed."""
    assert all(binding.key != "f" for binding in AIScreen.BINDINGS)
    assert not hasattr(AIScreen, "action_filter_category")


@pytest.mark.asyncio
async def test_ai_tools_tab_is_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """AI tools render as an interactive list."""
    monkeypatch.setattr("bluefinctl.app._is_bootc_system", lambda: False)
    monkeypatch.setattr("bluefinctl.core.ai.shutil.which", lambda _command: None)

    async def fake_get_stacks():
        from bluefinctl.core.ai import GpuDetection

        return GpuDetection(), []

    monkeypatch.setattr("bluefinctl.core.ai.get_stacks", fake_get_stacks)

    app = BluefinCtl(start_screen="ai")
    async with app.run_test() as pilot:
        await pilot.pause()
        tools_tab = app.screen.query_one(ToolsTab)
        assert isinstance(tools_tab.query_one("#ai-tools-list", ListView), ListView)


def test_deploy_action_uses_core_deploy_workflow() -> None:
    """The screen delegates stack deploy to the core progress workflow."""
    source = inspect.getsource(AIScreen.action_deploy_stack)
    assert "deploy_stack_steps" in source
    assert '"systemctl"' not in source
