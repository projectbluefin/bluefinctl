"""Progress parsing protocol and implementations.

Every long-running operation in bluefinctl routes through a ProgressParser
that extracts structured progress from raw subprocess output.

Protocol:
    parser.parse_line(line) -> ProgressUpdate | None

Implementations:
    - MultiStepParser      — for wizard flows (Lima setup, devmode enable)
    - PodmanPullParser     — parses layer download percentages
    - BrewInstallParser    — counts formula installs against total
    - BootcSwitchParser    — stage detection (downloading, staging, complete)
    - IndeterminateParser  — fallback that never reports a percentage
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProgressUpdate:
    """A structured progress update extracted from subprocess output."""

    percent: float | None = None  # None = indeterminate
    step: int | None = None
    total_steps: int | None = None
    message: str = ""


class ProgressParser(Protocol):
    """Protocol for extracting progress from subprocess output lines."""

    def parse_line(self, line: str) -> ProgressUpdate | None:
        """Parse a line of output, returning a ProgressUpdate if meaningful."""
        ...


class IndeterminateParser:
    """Fallback parser that passes through messages without progress percentage."""

    def parse_line(self, line: str) -> ProgressUpdate | None:
        stripped = line.strip()
        if stripped:
            return ProgressUpdate(message=stripped)
        return None


class MultiStepParser:
    """Parser for multi-step wizard flows.

    Tracks step progression and reports percentage based on step count.

    Usage:
        parser = MultiStepParser(total_steps=5)
        parser.advance("Checking KVM access...")
        # -> ProgressUpdate(percent=0.0, step=1, total_steps=5, message="...")
    """

    def __init__(self, total_steps: int) -> None:
        self._total = total_steps
        self._current = 0

    @property
    def current_step(self) -> int:
        return self._current

    @property
    def total_steps(self) -> int:
        return self._total

    def advance(self, message: str = "") -> ProgressUpdate:
        """Advance to the next step and return an update."""
        self._current += 1
        percent = ((self._current - 1) / self._total) * 100
        return ProgressUpdate(
            percent=percent,
            step=self._current,
            total_steps=self._total,
            message=message,
        )

    def complete(self, message: str = "Done") -> ProgressUpdate:
        """Mark all steps complete."""
        self._current = self._total
        return ProgressUpdate(
            percent=100.0,
            step=self._total,
            total_steps=self._total,
            message=message,
        )

    def parse_line(self, line: str) -> ProgressUpdate | None:
        """Parse a line — looks for 'Step N/M:' patterns."""
        match = re.match(r"Step\s+(\d+)/(\d+):\s*(.*)", line.strip())
        if match:
            step = int(match.group(1))
            total = int(match.group(2))
            msg = match.group(3)
            self._current = step
            self._total = total
            percent = ((step - 1) / total) * 100
            return ProgressUpdate(percent=percent, step=step, total_steps=total, message=msg)
        return None


class PodmanPullParser:
    """Parse podman/docker pull output for layer download progress.

    Handles output like:
        Copying blob sha256:abc123  [====>    ] 50.2MiB / 100.4MiB
        Getting image source signatures
        Writing manifest to image destination
    """

    _BLOB_RE = re.compile(
        r"Copying blob.*?(\d+(?:\.\d+)?)\s*[A-Za-z]+\s*/\s*(\d+(?:\.\d+)?)\s*[A-Za-z]+",
    )
    _LAYERS_DONE = 0
    _LAYERS_TOTAL = 0

    def parse_line(self, line: str) -> ProgressUpdate | None:
        stripped = line.strip()

        # Track layer-level progress
        blob_match = self._BLOB_RE.search(stripped)
        if blob_match:
            current = float(blob_match.group(1))
            total = float(blob_match.group(2))
            if total > 0:
                percent = (current / total) * 100
                return ProgressUpdate(percent=percent, message=f"Pulling: {stripped}")

        if "Writing manifest" in stripped:
            return ProgressUpdate(percent=95.0, message="Writing manifest...")

        if "Storing signatures" in stripped:
            return ProgressUpdate(percent=98.0, message="Storing signatures...")

        if "Getting image source" in stripped:
            return ProgressUpdate(percent=None, message="Getting image source...")

        if stripped:
            return ProgressUpdate(message=stripped)
        return None


class BrewInstallParser:
    """Parse brew bundle/install output to count installed packages.

    Handles output like:
        ==> Installing ripgrep
        ==> Pouring ripgrep--14.1.1.x86_64_linux.bottle.tar.gz
        Using rustup-init
        Homebrew Bundle complete! 12 Brewfile dependencies now installed.
    """

    _INSTALL_RE = re.compile(r"==> Installing (.+)")
    _COMPLETE_RE = re.compile(r"(\d+) Brewfile dependenc")

    def __init__(self, total_packages: int = 0) -> None:
        self._total = total_packages
        self._installed = 0

    def parse_line(self, line: str) -> ProgressUpdate | None:
        stripped = line.strip()

        install_match = self._INSTALL_RE.match(stripped)
        if install_match:
            self._installed += 1
            pkg = install_match.group(1)
            percent = (self._installed / self._total) * 100 if self._total > 0 else None
            return ProgressUpdate(
                percent=percent,
                step=self._installed,
                total_steps=self._total or None,
                message=f"Installing {pkg}",
            )

        complete_match = self._COMPLETE_RE.search(stripped)
        if complete_match:
            return ProgressUpdate(percent=100.0, message="Bundle complete")

        if "Using " in stripped or "Pouring " in stripped:
            return ProgressUpdate(message=stripped)

        return None


class BootcSwitchParser:
    """Parse bootc switch/upgrade output for stage progress.

    Handles output like:
        Pulling manifest...
        Importing: 45% (120/267 MB)
        Staging deployment...
        Queued for next boot.
    """

    _IMPORT_RE = re.compile(r"Importing.*?(\d+)%")
    _FETCH_RE = re.compile(r"Fetching.*?(\d+)%")

    def parse_line(self, line: str) -> ProgressUpdate | None:
        stripped = line.strip()

        import_match = self._IMPORT_RE.search(stripped)
        if import_match:
            percent = float(import_match.group(1))
            return ProgressUpdate(percent=percent, message="Importing image layers...")

        fetch_match = self._FETCH_RE.search(stripped)
        if fetch_match:
            percent = float(fetch_match.group(1))
            return ProgressUpdate(percent=percent, message="Fetching image...")

        if "Pulling manifest" in stripped:
            return ProgressUpdate(percent=5.0, message="Pulling manifest...")

        if "Staging" in stripped:
            return ProgressUpdate(percent=90.0, message="Staging deployment...")

        if "Queued for next boot" in stripped or "Deployment staged" in stripped:
            return ProgressUpdate(percent=100.0, message="Complete — reboot to apply")

        if stripped:
            return ProgressUpdate(message=stripped)
        return None
