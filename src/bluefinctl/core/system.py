"""Core business logic — system information, GPU detection, image metadata."""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

IMAGE_INFO_PATH = Path("/usr/share/ublue-os/image-info.json")


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
    gpu: GpuInfo = field(default_factory=GpuInfo)
    devmode: bool = False
    hostname: str = ""

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
    """Detect GPU vendor and model."""
    # Try nvidia-smi first
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            model = parts[0] if parts else "Unknown"
            vram = int(parts[1]) if len(parts) > 1 else 0
            return GpuInfo(vendor="nvidia", model=model, vram_mb=vram)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Try rocm-smi for AMD
    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Parse AMD GPU name from rocm-smi output
            for line in result.stdout.splitlines():
                if "Card" in line or "GPU" in line:
                    return GpuInfo(vendor="amd", model=line.strip())
            return GpuInfo(vendor="amd", model="Detected")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Check lspci for Intel
    try:
        result = subprocess.run(
            ["lspci"],
            capture_output=True,
            text=True,
            timeout=5,
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
    # Check for the devmode group or flag file
    devmode_flag = Path("/etc/ublue-os/devmode")
    if devmode_flag.exists():
        return True

    # Check if user is in mock/docker groups (devmode indicators)
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

    # Get bootc status
    boot_status = "Current"
    try:
        proc = await asyncio.create_subprocess_exec(
            "bootc", "status", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            bootc_data = json.loads(stdout)
            # Parse deployment status
            if bootc_data.get("status", {}).get("staged"):
                boot_status = "Update staged (reboot pending)"
    except (FileNotFoundError, OSError):
        boot_status = "bootc unavailable"

    return SystemInfo(
        image_name=image_data.get("image-name", "unknown"),
        image_tag=image_data.get("image-tag", "unknown"),
        image_ref=image_data.get("image-ref", ""),
        boot_status=boot_status,
        gpu=gpu,
        devmode=devmode,
    )


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
