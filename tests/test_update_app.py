"""Smoke tests for core/update_app.py — run_update_cli()."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from bluefinctl.core.update_app import run_update_cli
from bluefinctl.core.update_runner import BootcEvent


async def _empty_bootc() -> AsyncIterator[BootcEvent]:
    return
    yield  # make it an async generator


@pytest.mark.asyncio
async def test_run_update_cli_success() -> None:
    with (
        patch(
            "bluefinctl.core.update_runner.run_bootc_upgrade",
            return_value=_empty_bootc(),
        ),
        patch(
            "bluefinctl.core.update_runner.run_flatpak_update",
            new_callable=AsyncMock,
            return_value=(True, "already up to date"),
        ),
        patch(
            "bluefinctl.core.update_runner.run_brew_update",
            new_callable=AsyncMock,
            return_value=(True, "already up to date"),
        ),
    ):
        result = await run_update_cli(accent_hex="#6f8396", has_containers=False)

    assert result == "done"


@pytest.mark.asyncio
async def test_run_update_cli_bootc_failure() -> None:
    async def _failing_bootc() -> AsyncIterator[BootcEvent]:
        raise RuntimeError("bootc exploded")
        yield  # type: ignore[misc]  # unreachable — needed to make function an async generator

    with patch(
        "bluefinctl.core.update_runner.run_bootc_upgrade",
        return_value=_failing_bootc(),
    ):
        result = await run_update_cli(accent_hex="#6f8396", has_containers=False)

    assert result == "failed"
