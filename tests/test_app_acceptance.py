"""Acceptance tests for the four-panel app navigation."""

from __future__ import annotations

import pytest

from bluefinctl.app import BluefinCtl
from bluefinctl.screens.system import SystemScreen


@pytest.mark.asyncio
async def test_all_screens_installed_on_non_bootc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Platform detection should not hide any primary panel."""
    monkeypatch.setattr("bluefinctl.app._is_bootc_system", lambda: False)

    app = BluefinCtl()
    async with app.run_test():
        assert app.get_screen_names() == ["system", "updates", "devmode", "ai"]
        assert app.is_bootc is False
        assert isinstance(app.screen, SystemScreen)


@pytest.mark.asyncio
async def test_dark_mode_follows_gnome_color_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    """App should use dark theme when GNOME color-scheme is prefer-dark."""
    monkeypatch.setattr("bluefinctl.app.get_color_scheme", lambda: "dark")
    monkeypatch.setattr("bluefinctl.app.get_accent_color", lambda: "blue")

    app = BluefinCtl()
    async with app.run_test():
        assert app.theme == "bluefin-dark"


@pytest.mark.asyncio
async def test_light_mode_follows_gnome_color_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    """App should use light theme when GNOME color-scheme is default (light)."""
    monkeypatch.setattr("bluefinctl.app.get_color_scheme", lambda: "light")
    monkeypatch.setattr("bluefinctl.app.get_accent_color", lambda: "blue")

    app = BluefinCtl()
    async with app.run_test():
        assert app.theme == "bluefin-light"
