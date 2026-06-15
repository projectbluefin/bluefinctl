"""Tests for Command Palette providers."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from bluefinctl.core.brew import PackageType, SearchResult
from bluefinctl.core.flatpak import FlatpakResult


class TestBrewSearch:
    """Test core/brew.py search_packages function."""

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty(self) -> None:
        from bluefinctl.core.brew import search_packages

        result = await search_packages("")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_short_query_returns_empty(self) -> None:
        from bluefinctl.core.brew import search_packages

        result = await search_packages("a")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_parses_formulae_and_casks(self) -> None:
        from bluefinctl.core.brew import search_packages

        mock_output = (
            "==> Formulae\n"
            "ripgrep\n"
            "ripgrep-all\n"
            "==> Casks\n"
            "ripgrep-gui\n"
        )

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(
                return_value=(mock_output.encode(), b""),
            )
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            results = await search_packages("ripgrep")

        assert len(results) == 3
        assert results[0] == SearchResult(name="ripgrep", type=PackageType.FORMULA)
        assert results[1] == SearchResult(name="ripgrep-all", type=PackageType.FORMULA)
        assert results[2] == SearchResult(name="ripgrep-gui", type=PackageType.CASK)

    @pytest.mark.asyncio
    async def test_search_handles_failure(self) -> None:
        from bluefinctl.core.brew import search_packages

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 1
            mock_exec.return_value = mock_proc

            results = await search_packages("nonexistent")

        assert results == []


class TestFlatpakSearch:
    """Test core/flatpak.py search_packages function."""

    @pytest.mark.asyncio
    async def test_search_empty_returns_empty(self) -> None:
        from bluefinctl.core.flatpak import search_packages

        result = await search_packages("")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_parses_tab_separated(self) -> None:
        from bluefinctl.core.flatpak import search_packages

        mock_output = (
            "org.gimp.GIMP\tGIMP\tGNU Image Manipulation Program\n"
            "org.inkscape.Inkscape\tInkscape\tVector graphics editor\n"
        )

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(
                return_value=(mock_output.encode(), b""),
            )
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            results = await search_packages("gimp")

        assert len(results) == 2
        assert results[0] == FlatpakResult(
            app_id="org.gimp.GIMP",
            name="GIMP",
            description="GNU Image Manipulation Program",
        )

    @pytest.mark.asyncio
    async def test_search_handles_missing_flatpak(self) -> None:
        from bluefinctl.core.flatpak import search_packages

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            results = await search_packages("anything")

        assert results == []


class TestSearchResult:
    """Test SearchResult dataclass."""

    def test_creation(self) -> None:
        r = SearchResult(name="ripgrep", type=PackageType.FORMULA, description="fast grep")
        assert r.name == "ripgrep"
        assert r.type == PackageType.FORMULA
        assert r.description == "fast grep"

    def test_default_description(self) -> None:
        r = SearchResult(name="bat", type=PackageType.CASK)
        assert r.description == ""
