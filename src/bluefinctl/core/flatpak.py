"""Core business logic — Flatpak package management."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(slots=True)
class FlatpakResult:
    """A Flatpak app found via search."""

    app_id: str
    name: str
    description: str = ""


async def search_packages(query: str) -> list[FlatpakResult]:
    """Search Flatpak remotes for packages matching query."""
    if not query or len(query) < 2:
        return []

    try:
        proc = await asyncio.create_subprocess_exec(
            "flatpak", "search", "--columns=application,name,description", query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
    except FileNotFoundError:
        return []

    if proc.returncode != 0 or not stdout:
        return []

    results: list[FlatpakResult] = []
    for line in stdout.decode().splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            app_id = parts[0].strip()
            name = parts[1].strip()
            description = parts[2].strip() if len(parts) > 2 else ""
            if app_id:
                results.append(FlatpakResult(
                    app_id=app_id,
                    name=name,
                    description=description,
                ))

    return results[:30]


async def install_package(app_id: str) -> bool:
    """Install a Flatpak app from flathub."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "flatpak", "install", "--noninteractive", "flathub", app_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0
    except FileNotFoundError:
        return False


async def remove_package(app_id: str) -> bool:
    """Remove a Flatpak app."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "flatpak", "uninstall", "--noninteractive", app_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0
    except FileNotFoundError:
        return False
