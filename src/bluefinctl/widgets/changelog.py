"""Changelog widget — fetches and displays release notes via MarkdownViewer."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.widgets import Label, Markdown, Static


class ChangelogViewer(Static):
    """Displays release notes from the current image's changelog.

    Attempts to read release notes from:
    1. /usr/share/ublue-os/changelog.md (shipped with image)
    2. bootc status → image tag → fetch from GitHub releases
    """

    DEFAULT_CSS = """
    ChangelogViewer {
        height: auto;
        max-height: 30;
        overflow-y: auto;
        padding: 1 2;
    }
    #changelog-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Release Notes", id="changelog-title")
        yield Markdown("*Loading changelog...*", id="changelog-content")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        """Load changelog content."""
        from pathlib import Path

        content = ""

        # Try local changelog first
        local_changelog = Path("/usr/share/ublue-os/changelog.md")
        if local_changelog.exists():
            try:
                text = await asyncio.get_running_loop().run_in_executor(
                    None, local_changelog.read_text,
                )
                # Show last 50 lines (most recent release)
                lines = text.strip().splitlines()
                content = "\n".join(lines[:50])
            except OSError:
                pass

        # Try fetching from bootc image tag if no local changelog
        if not content:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "bootc", "status", "--json",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0:
                    import json

                    data = json.loads(stdout)
                    ref = (
                        data.get("status", {})
                        .get("booted", {})
                        .get("image", {})
                        .get("image", {})
                        .get("image", "")
                    )
                    if ref:
                        tag = ref.split(":")[-1] if ":" in ref else "latest"
                        content = (
                            f"## Current Image\n\n"
                            f"**Tag:** `{tag}`\n\n"
                            f"**Ref:** `{ref}`\n\n"
                            f"---\n\n"
                            f"*Full release notes available at "
                            f"[GitHub Releases]"
                            f"(https://github.com/ublue-os/bluefin/releases)*"
                        )
            except (FileNotFoundError, OSError):
                pass

        if not content:
            content = (
                "*No changelog available.*\n\n"
                "Release notes will appear here after your next image update."
            )

        self.query_one("#changelog-content", Markdown).update(content)
