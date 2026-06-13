"""Tests for bundle lifecycle safety."""

from __future__ import annotations

import pytest

from bluefinctl.core import bundles


@pytest.mark.asyncio
async def test_deactivation_preview_keeps_shared_packages_out_of_removable(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Packages shared with another active bundle must not be removed."""
    (tmp_path / "target.Brewfile").write_text(
        'brew "unique"\n'
        'brew "shared"\n'
        'brew "missing"\n',
    )
    (tmp_path / "other.Brewfile").write_text('brew "shared"\n')

    monkeypatch.setattr(bundles, "SYSTEM_BREWFILES", tmp_path)
    monkeypatch.setattr(bundles, "_get_installed_formulae", lambda: {"unique", "shared"})
    monkeypatch.setattr(bundles, "_get_installed_flatpaks", lambda: set())

    preview = await bundles.preview_bundle_deactivation("target")

    assert preview.removable_packages == ("unique",)
    assert preview.shared_packages == ("shared",)
    assert preview.missing_packages == ("missing",)
