"""Acceptance tests for stable five-panel app navigation."""

from __future__ import annotations

import pytest

from bluefinctl.app import BluefinCtl
from bluefinctl.screens.system import SystemScreen


@pytest.mark.asyncio
async def test_all_five_screens_installed_on_non_bootc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Platform detection should not hide any primary panel."""
    monkeypatch.setattr("bluefinctl.app._is_bootc_system", lambda: False)

    app = BluefinCtl()
    async with app.run_test():
        assert app.get_screen_names() == ["system", "updates", "toolkit", "devmode", "ai"]
        assert app.is_bootc is False
        assert isinstance(app.screen, SystemScreen)
