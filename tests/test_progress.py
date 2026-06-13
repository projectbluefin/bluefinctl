"""Tests for core/progress.py — progress parsing."""

from bluefinctl.core.progress import (
    BootcSwitchParser,
    BrewInstallParser,
    IndeterminateParser,
    MultiStepParser,
    PodmanPullParser,
)


class TestMultiStepParser:
    def test_advance(self) -> None:
        parser = MultiStepParser(total_steps=4)
        u = parser.advance("First step")
        assert u.percent == 0.0
        assert u.step == 1
        assert u.total_steps == 4
        assert u.message == "First step"

    def test_progress_increments(self) -> None:
        parser = MultiStepParser(total_steps=4)
        parser.advance("1")
        u = parser.advance("2")
        assert u.percent == 25.0
        assert u.step == 2

    def test_complete(self) -> None:
        parser = MultiStepParser(total_steps=3)
        parser.advance("1")
        u = parser.complete("All done")
        assert u.percent == 100.0
        assert u.step == 3
        assert u.message == "All done"

    def test_parse_line_pattern(self) -> None:
        parser = MultiStepParser(total_steps=5)
        u = parser.parse_line("Step 3/5: Installing packages")
        assert u is not None
        assert u.step == 3
        assert u.total_steps == 5
        assert "Installing packages" in u.message

    def test_parse_line_no_match(self) -> None:
        parser = MultiStepParser(total_steps=5)
        u = parser.parse_line("some random output")
        assert u is None


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


class TestPodmanPullParser:
    def test_blob_line(self) -> None:
        parser = PodmanPullParser()
        u = parser.parse_line(
            "Copying blob sha256:abc123  [====>    ] 50.2MiB / 100.4MiB",
        )
        assert u is not None
        assert u.percent is not None
        assert 49 < u.percent < 51

    def test_manifest_stage(self) -> None:
        parser = PodmanPullParser()
        u = parser.parse_line("Writing manifest to image destination")
        assert u is not None
        assert u.percent == 95.0

    def test_signatures(self) -> None:
        parser = PodmanPullParser()
        u = parser.parse_line("Storing signatures")
        assert u is not None
        assert u.percent == 98.0


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
