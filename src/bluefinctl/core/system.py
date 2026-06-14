"""Core business logic — system information, GPU detection, image metadata."""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

IMAGE_INFO_PATH = Path("/usr/share/ublue-os/image-info.json")

# Prefixes that indicate the image ref type
_SIGNED_PREFIX = "ostree-image-signed:"
_DOCKER_PREFIXES = ("ostree-image-signed:docker://", "docker://")


@dataclass
class GpuInfo:
    """Detected GPU information."""

    vendor: str = "unknown"  # nvidia, amd, intel, none
    model: str = ""
    vram_mb: int = 0

    @property
    def icon(self) -> str:
        icons = {"nvidia": "[N]", "amd": "[A]", "intel": "[I]"}
        return icons.get(self.vendor, "[-]")


@dataclass
class SystemInfo:
    """Aggregated system information for the dashboard."""

    image_name: str = "unknown"
    image_tag: str = "unknown"
    image_ref: str = ""
    boot_status: str = "unknown"
    image_staged: bool = False
    image_signed: bool = False
    gpu: GpuInfo = field(default_factory=GpuInfo)
    devmode: bool = False
    hostname: str = ""

    @property
    def clean_image_ref(self) -> str:
        """Image ref with transport/signing prefixes stripped — e.g. ghcr.io/…/dakota."""
        ref = self.image_ref
        for prefix in ("ostree-image-signed:docker://", "ostree-unverified-image:docker://",
                       "ostree-image-signed:", "docker://"):
            if ref.startswith(prefix):
                return ref[len(prefix):]
        return ref

    @property
    def full_clean_ref(self) -> str:
        """Full display reference including tag: ghcr.io/…/dakota:latest."""
        base = self.clean_image_ref
        tag  = self.image_tag
        if tag and tag != "unknown" and ":" not in base:
            return f"{base}:{tag}"
        return base

    def render(self) -> str:
        """Render as a multi-line string for the dashboard card."""
        lines = [
            f"Image:  {self.image_name}:{self.image_tag}",
            f"Boot:   {self.boot_status}",
            f"GPU:    {self.gpu.icon} {self.gpu.vendor.upper()} {self.gpu.model}",
            f"Mode:   {'Developer' if self.devmode else 'Standard'}",
        ]
        return "\n".join(lines)


def _read_image_info() -> dict[str, Any]:
    """Read /usr/share/ublue-os/image-info.json."""
    if IMAGE_INFO_PATH.exists():
        data: dict[str, Any] = json.loads(IMAGE_INFO_PATH.read_text())
        return data
    return {}


def _detect_gpu() -> GpuInfo:
    """Detect GPU via sysfs first (no root needed), then nvidia-smi for VRAM."""
    import contextlib
    import os

    # --- NVIDIA via nvidia-smi (userspace, no root) ---
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            model = parts[0] if parts else "Unknown"
            vram = 0
            with contextlib.suppress(IndexError, ValueError):
                vram = int(parts[1])
            return GpuInfo(vendor="nvidia", model=model, vram_mb=vram)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # --- AMD via sysfs (no root required) ---
    try:
        for entry in sorted(os.listdir("/sys/class/drm")):
            if not entry.startswith("card") or "-" in entry:
                continue
            vendor_path = f"/sys/class/drm/{entry}/device/vendor"
            uevent_path = f"/sys/class/drm/{entry}/device/uevent"
            if not os.path.exists(vendor_path):
                continue
            with open(vendor_path) as _f:
                vendor_id = _f.read().strip()
            if vendor_id != "0x1002":
                continue
            model = "AMD GPU"
            if os.path.exists(uevent_path):
                with open(uevent_path) as _f:
                    uevent_lines = _f.read().splitlines()
                for line in uevent_lines:
                    if line.startswith("PCI_ID="):
                        model = f"AMD Radeon ({line.split('=')[1]})"
            try:
                lspci_out = subprocess.run(
                    ["lspci", "-d", "1002:"],
                    capture_output=True, text=True, timeout=3,
                ).stdout
                for line in lspci_out.splitlines():
                    if "VGA" in line or "Display" in line or "3D" in line:
                        model = line.split(": ", 1)[-1]
                        break
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                pass
            vram_mb = 0
            vram_path = f"/sys/class/drm/{entry}/device/mem_info_vram_total"
            if os.path.exists(vram_path):
                with contextlib.suppress(ValueError, OSError), open(vram_path) as _f:
                    vram_mb = int(_f.read().strip()) // (1024 * 1024)
            return GpuInfo(vendor="amd", model=model, vram_mb=vram_mb)
    except (FileNotFoundError, PermissionError, OSError):
        pass

    # --- Intel via lspci ---
    try:
        result = subprocess.run(
            ["lspci"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if ("VGA" in line or "3D" in line) and "Intel" in line:
                    return GpuInfo(vendor="intel", model=line.split(": ")[-1])
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return GpuInfo()


def _check_devmode() -> bool:
    """Check if developer mode is active."""
    devmode_flag = Path("/etc/ublue-os/devmode")
    if devmode_flag.exists():
        return True
    try:
        result = subprocess.run(["groups"], capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            groups = result.stdout.strip().split()
            return "mock" in groups or "docker" in groups
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return False


async def get_system_info() -> SystemInfo:
    """Gather all system information asynchronously."""
    loop = asyncio.get_event_loop()

    image_data = await loop.run_in_executor(None, _read_image_info)
    gpu = await loop.run_in_executor(None, _detect_gpu)
    devmode = await loop.run_in_executor(None, _check_devmode)

    raw_ref = image_data.get("image-ref", "")
    image_signed = raw_ref.startswith(_SIGNED_PREFIX)

    # Bootc status — staged update + hostname
    boot_status = "Current"
    image_staged = False
    hostname = ""
    try:
        proc = await asyncio.create_subprocess_exec(
            "bootc", "status", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            bootc_data = json.loads(stdout)
            staged = bootc_data.get("status", {}).get("staged")
            if staged:
                image_staged = True
                boot_status = "Update staged — reboot to apply"
    except (FileNotFoundError, OSError):
        boot_status = "bootc unavailable"

    import socket
    hostname = socket.gethostname()

    return SystemInfo(
        image_name=image_data.get("image-name", "unknown"),
        image_tag=image_data.get("image-tag", "unknown"),
        image_ref=raw_ref,
        boot_status=boot_status,
        image_staged=image_staged,
        image_signed=image_signed,
        gpu=gpu,
        devmode=devmode,
        hostname=hostname,
    )


async def get_image_compression(clean_ref: str) -> str:
    """Detect image layer compression type via skopeo inspect --raw.

    Returns one of: 'zstd:chunked', 'zstd', 'gzip', 'unknown'.
    This is a network call — run as a background worker.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "skopeo", "inspect", "--raw", f"docker://{clean_ref}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0 or not stdout:
            return "unknown"
        data: dict[str, Any] = json.loads(stdout)
        layers = data.get("layers", [])
        if not layers:
            return "unknown"
        # Check first layer for chunked annotation (containers/storage zstd:chunked)
        first = layers[0]
        anns = first.get("annotations", {})
        if any("zstd-chunked" in k or "chunked" in k.lower() for k in anns):
            return "zstd:chunked"
        mt = first.get("mediaType", "")
        if mt.endswith("+zstd"):
            # Double-check all layers for chunked annotations (some tools set it per-layer)
            for layer in layers:
                layer_anns = layer.get("annotations", {})
                if any("zstd-chunked" in k or "chunked" in k.lower() for k in layer_anns):
                    return "zstd:chunked"
            return "zstd"
        if mt.endswith("+gzip"):
            return "gzip"
    except (FileNotFoundError, OSError, json.JSONDecodeError, KeyError):
        pass
    return "unknown"


def print_status() -> None:
    """Print system status for headless CLI mode."""
    import asyncio as _asyncio

    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    info = _asyncio.run(get_system_info())

    console.print(Panel(
        info.render(),
        title="[bold]bluefinctl[/bold] — System Status",
        border_style="blue",
    ))
