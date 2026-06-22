"""Tests for core/progress.py — progress parsing."""

from bluefinctl.core.progress import (
    BootcSwitchParser,
    BrewInstallParser,
    IndeterminateParser,
)


class TestBrewInstallParser:
    def test_install_line(self) -> None:
        parser = BrewInstallParser(total_packages=10)
        u = parser.parse_line("==> Installing ripgrep")
        assert u is not None
        assert u.step == 1
        assert u.percent == 10.0
        assert "ripgrep" in u.message

    def test_multiple_installs(self) -> None:
        parser = BrewInstallParser(total_packages=4)
        parser.parse_line("==> Installing bat")
        u = parser.parse_line("==> Installing fd")
        assert u is not None
        assert u.step == 2
        assert u.percent == 50.0

    def test_complete_line(self) -> None:
        parser = BrewInstallParser()
        u = parser.parse_line("Homebrew Bundle complete! 12 Brewfile dependencies now installed.")
        assert u is not None
        assert u.percent == 100.0

    def test_unknown_total(self) -> None:
        parser = BrewInstallParser(total_packages=0)
        u = parser.parse_line("==> Installing eza")
        assert u is not None
        assert u.percent is None  # indeterminate

class TestBootcSwitchParser:
    def test_pulling_manifest(self) -> None:
        parser = BootcSwitchParser()
        u = parser.parse_line("Pulling manifest...")
        assert u is not None
        assert u.percent == 5.0

    def test_import_progress(self) -> None:
        parser = BootcSwitchParser()
        u = parser.parse_line("Importing: 45% (120/267 MB)")
        assert u is not None
        assert u.percent == 45.0

    def test_staging(self) -> None:
        parser = BootcSwitchParser()
        u = parser.parse_line("Staging deployment for next boot")
        assert u is not None
        assert u.percent == 90.0

    def test_queued_complete(self) -> None:
        parser = BootcSwitchParser()
        u = parser.parse_line("Queued for next boot.")
        assert u is not None
        assert u.percent == 100.0


class TestIndeterminateParser:
    def test_returns_message(self) -> None:
        parser = IndeterminateParser()
        u = parser.parse_line("doing something")
        assert u is not None
        assert u.percent is None
        assert u.message == "doing something"

    def test_empty_line(self) -> None:
        parser = IndeterminateParser()
        u = parser.parse_line("")
        assert u is None
