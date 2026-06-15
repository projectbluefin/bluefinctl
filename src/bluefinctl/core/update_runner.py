"""Update orchestration — runs all system update stages.

Stage order:
    1. bootc upgrade  (sequential · needs sudo · feeds --progress-fd for JSON events)
    2. Parallel:  flatpak update  ·  brew upgrade  ·  distrobox upgrade -a

bootc --progress-fd JSON schema (per event line):
    {
      "type":        "ProgressSteps" | "ProgressBytes",
      "task":        "pulling" | "importing" | "staging",
      "description": "human-readable stage label",
      "steps":       <int>,          # current layer count (ProgressSteps)
      "stepsTotal":  <int>,          # total layer count
      "bytes":       <int>,          # bytes transferred (ProgressBytes)
      "bytesTotal":  <int>           # total bytes for current layer
    }

Stage → OSC-percent mapping (mirrors uupd PROGRESS_STAGES):
    pulling   0 – 80 %
    importing 80 – 90 %
    staging   90 – 100 %
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from collections.abc import AsyncIterator
from dataclasses import dataclass

# ── Data types ────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class BootcEvent:
    """Structured progress event from bootc --progress-fd."""

    type: str         # "ProgressSteps" | "ProgressBytes"
    task: str         # "pulling" | "importing" | "staging"
    description: str = ""
    steps: int = 0
    steps_total: int = 0
    bytes_: int = 0
    bytes_total: int = 0


@dataclass(slots=True)
class ImageInfo:
    """Booted bootc image metadata."""

    ref: str = ""          # full image ref
    version: str = ""      # ostree version string
    digest: str = ""       # sha256 digest of booted image


# ── Image metadata ────────────────────────────────────────────────────────────

def get_image_info() -> ImageInfo:
    """Query bootc status --format=json for the booted image reference."""
    try:
        result = subprocess.run(
            ["bootc", "status", "--format=json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ImageInfo()

        data = json.loads(result.stdout)
        booted = data.get("status", {}).get("booted", {})
        image = booted.get("image", {}).get("image", {})
        ref = image.get("image", "")
        version = booted.get("ostree", {}).get("version", "")
        digest = image.get("digest", "")
        return ImageInfo(ref=ref, version=version, digest=digest)
    except Exception:
        return ImageInfo()


def check_for_update() -> bool:
    """Return True if a bootc upgrade is available (exit 11 = update available)."""
    try:
        result = subprocess.run(
            ["bootc", "upgrade", "--check"],
            capture_output=True,
            timeout=60,
        )
        # bootc exits 11 when an update is available, 0 when already current
        return result.returncode == 11
    except Exception:
        return False


# ── Stage runners ─────────────────────────────────────────────────────────────

async def run_bootc_upgrade() -> AsyncIterator[BootcEvent]:
    """Run ``sudo bootc upgrade --quiet --progress-fd N``.

    Yields :class:`BootcEvent` objects as JSON lines arrive on the progress pipe.
    Falls back silently to an empty iterator if the pipe or subprocess fails.
    """
    r_fd, w_fd = os.pipe()

    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "bootc", "upgrade", "--quiet",
            "--progress-fd", str(w_fd),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            pass_fds=(w_fd,),
        )
    except Exception:
        os.close(r_fd)
        os.close(w_fd)
        return

    # Close write end in parent — EOF on the pipe when bootc exits
    os.close(w_fd)

    # Wrap the read fd in an asyncio StreamReader
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    r_file = os.fdopen(r_fd, "rb", buffering=0)
    transport, _ = await loop.connect_read_pipe(lambda: protocol, r_file)

    try:
        async for raw_line in reader:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                yield BootcEvent(
                    type=data.get("type", ""),
                    task=data.get("task", "").lower(),
                    description=data.get("description", ""),
                    steps=data.get("steps", 0),
                    steps_total=data.get("stepsTotal", 0),
                    bytes_=data.get("bytes", 0),
                    bytes_total=data.get("bytesTotal", 0),
                )
            except (json.JSONDecodeError, KeyError):
                pass
    finally:
        transport.close()
        await proc.wait()


async def run_flatpak_update() -> tuple[bool, str]:
    """Run ``flatpak update -y --noninteractive``.

    Returns ``(success, human_summary)``.
    """
    proc = await asyncio.create_subprocess_exec(
        "flatpak", "update", "-y", "--noninteractive",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode("utf-8", errors="replace")

    if "Nothing to do" in output or "nothing to do" in output.lower():
        return True, "already up to date"

    updated = sum(
        1 for ln in output.splitlines()
        if ln.strip().startswith("Updating ") or "Updated" in ln
    )
    if updated:
        return proc.returncode == 0, f"{updated} app{'s' if updated != 1 else ''} updated"

    return proc.returncode == 0, "done" if proc.returncode == 0 else "failed"


async def run_brew_update() -> tuple[bool, str]:
    """Run ``brew update`` then ``brew upgrade``.

    Returns ``(success, human_summary)``.
    """
    # Fetch formula index first
    fetch = await asyncio.create_subprocess_exec(
        "brew", "update",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await fetch.wait()

    # Upgrade installed formulae / casks
    proc = await asyncio.create_subprocess_exec(
        "brew", "upgrade",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode("utf-8", errors="replace")

    if "Already up-to-date" in output or not output.strip():
        return True, "already up to date"

    upgraded = sum(
        1 for ln in output.splitlines()
        if ln.startswith(("==> Upgrading ", "Upgrading "))
    )
    if upgraded:
        noun = "formulae" if upgraded != 1 else "formula"
        return proc.returncode == 0, f"{upgraded} {noun} upgraded"

    return proc.returncode == 0, "done" if proc.returncode == 0 else "failed"


async def run_distrobox_update() -> tuple[bool, str]:
    """Run ``distrobox upgrade -a`` (all containers for current user).

    Returns ``(success, human_summary)``.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "distrobox", "upgrade", "-a",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        return proc.returncode == 0, "done" if proc.returncode == 0 else "failed"
    except FileNotFoundError:
        return True, "not installed"


def get_autoupdate_containers() -> list[str]:
    """Return names of containers with ``io.containers.autoupdate`` label set.

    These are eligible for ``podman auto-update``.  Distrobox containers appear
    here if the user has configured autoupdate labels on them.
    """
    try:
        result = subprocess.run(
            ["podman", "ps",
             "--filter", "label=io.containers.autoupdate",
             "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        return [n.strip() for n in result.stdout.strip().splitlines() if n.strip()]
    except Exception:  # noqa: BLE001
        return []


async def run_container_autoupdate() -> tuple[bool, str]:
    """Run ``podman auto-update`` for labeled containers.

    Returns ``(success, human_summary)``.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "podman", "auto-update",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace")
        data_lines = [
            ln for ln in output.splitlines()
            if ln.strip() and not ln.startswith("UNIT")
        ]
        updated = sum(1 for ln in data_lines if ln.strip().endswith("true"))
        if updated:
            noun = "containers" if updated != 1 else "container"
            return proc.returncode == 0, f"{updated} {noun} updated"
        return proc.returncode == 0, "already up to date" if proc.returncode == 0 else "failed"
    except FileNotFoundError:
        return True, "podman not available"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
