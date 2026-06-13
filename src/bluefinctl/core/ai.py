"""Core business logic — AI stack management.

Handles:
- GPU detection (NVIDIA CDI / AMD KFD)
- Stack discovery from /usr/share/ublue-os/{nvidia,amd}-stacks/
- Preflight checks (VRAM, ports, auth, disk)
- Deploy/stop lifecycle via Podman Quadlets
"""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class GpuVendor(StrEnum):
    """Detected GPU vendor."""

    NVIDIA = "nvidia"
    AMD = "amd"
    NONE = "none"


class StackCategory(StrEnum):
    """AI stack categories."""

    SERVE = "serve"
    DEV = "dev"
    TRAIN = "train"
    NIM = "nim"


class StackStatus(StrEnum):
    """Stack runtime status."""

    RUNNING = "running"
    STOPPED = "stopped"
    AVAILABLE = "available"
    EXCEEDS_VRAM = "exceeds-vram"


@dataclass
class GpuDetection:
    """Result of GPU detection."""

    vendor: GpuVendor = GpuVendor.NONE
    model: str = ""
    vram_gb: int = 0
    driver_version: str = ""
    cdi_active: bool = False
    kfd_ok: bool = False

    @property
    def display(self) -> str:
        """Human-readable GPU summary."""
        if self.vendor == GpuVendor.NONE:
            return "No discrete GPU detected"
        parts = [f"{self.vendor.value.upper()} {self.model}"]
        if self.vram_gb:
            parts.append(f"{self.vram_gb} GB VRAM")
        if self.vendor == GpuVendor.NVIDIA:
            parts.append(f"CDI: {'active' if self.cdi_active else 'inactive'}")
            if self.driver_version:
                parts.append(f"Driver: {self.driver_version}")
        elif self.vendor == GpuVendor.AMD:
            parts.append(f"/dev/kfd: {'ok' if self.kfd_ok else 'missing'}")
        return " | ".join(parts)


@dataclass
class AIStack:
    """An AI stack discovered from system directories."""

    slug: str
    name: str = ""
    description: str = ""
    category: StackCategory = StackCategory.SERVE
    vram_gb: int = 0
    disk_gb: int = 0
    ports: dict[str, int] = field(default_factory=dict)
    requires_ngc_auth: bool = False
    requires_hf_auth: bool = False
    order: int = 99
    container_file: str = ""
    network_file: str = ""
    status: StackStatus = StackStatus.AVAILABLE

    @property
    def vram_badge(self) -> str:
        """VRAM requirement badge."""
        return f"{self.vram_gb} GB"


def detect_gpu() -> GpuDetection:
    """Detect GPU vendor, model, VRAM, and runtime readiness."""
    # Try NVIDIA first
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            model = parts[0] if parts else "Unknown"
            vram_mb = int(parts[1]) if len(parts) > 1 else 0
            driver = parts[2] if len(parts) > 2 else ""

            # Check CDI
            cdi_active = False
            try:
                cdi_result = subprocess.run(
                    ["nvidia-ctk", "cdi", "list"],
                    capture_output=True, text=True, timeout=5,
                )
                cdi_active = cdi_result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

            return GpuDetection(
                vendor=GpuVendor.NVIDIA,
                model=model,
                vram_gb=vram_mb // 1024,
                driver_version=driver,
                cdi_active=cdi_active,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try AMD
    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname", "--showmeminfo", "vram"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            model = "Radeon"
            vram_gb = 0
            for line in result.stdout.splitlines():
                if "GPU" in line and ":" in line:
                    model = line.split(":")[-1].strip()
                if "Total Memory" in line:
                    # Parse VRAM in bytes or MB
                    try:
                        val = int(line.split()[-1])
                        if val > 1_000_000:
                            vram_gb = val // (1024 * 1024 * 1024)
                        else:
                            vram_gb = val // 1024
                    except (ValueError, IndexError):
                        pass

            kfd_ok = Path("/dev/kfd").exists()
            return GpuDetection(
                vendor=GpuVendor.AMD,
                model=model,
                vram_gb=vram_gb,
                kfd_ok=kfd_ok,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return GpuDetection()


def _discover_stacks(vendor: GpuVendor) -> list[AIStack]:
    """Discover AI stacks from system directories."""
    stacks: list[AIStack] = []

    if vendor == GpuVendor.NVIDIA:
        stack_dir = Path("/usr/share/ublue-os/nvidia-stacks")
    elif vendor == GpuVendor.AMD:
        stack_dir = Path("/usr/share/ublue-os/amd-stacks")
    else:
        return stacks

    if not stack_dir.exists():
        return stacks

    for entry in sorted(stack_dir.iterdir()):
        if not entry.is_dir():
            continue
        env_file = entry / "stack.env"
        if not env_file.exists():
            continue

        # Parse stack.env
        env: dict[str, str] = {}
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"')

        # Parse ports
        ports: dict[str, int] = {}
        port_str = env.get("STACK_PORTS", "")
        if port_str:
            for mapping in port_str.split(","):
                if ":" in mapping:
                    name, port = mapping.split(":", 1)
                    try:
                        ports[name.strip()] = int(port.strip())
                    except ValueError:
                        pass

        # Find quadlet files
        container_file = ""
        network_file = ""
        for f in entry.iterdir():
            if f.suffix == ".container":
                container_file = str(f)
            elif f.suffix == ".network":
                network_file = str(f)

        stack = AIStack(
            slug=entry.name,
            name=env.get("STACK_NAME", entry.name.title()),
            description=env.get("STACK_DESC", ""),
            category=StackCategory(env.get("STACK_CATEGORY", "serve")),
            vram_gb=int(env.get("STACK_VRAM_GB", "0")),
            disk_gb=int(env.get("STACK_DISK_GB", "0")),
            ports=ports,
            requires_ngc_auth=env.get("STACK_REQUIRES_NGC_AUTH", "false").lower() == "true",
            requires_hf_auth=env.get("STACK_REQUIRES_HF_AUTH", "false").lower() == "true",
            order=int(env.get("STACK_ORDER", "99")),
            container_file=container_file,
            network_file=network_file,
        )
        stacks.append(stack)

    stacks.sort(key=lambda s: s.order)
    return stacks


async def get_stacks() -> tuple[GpuDetection, list[AIStack]]:
    """Get GPU info and available stacks."""
    loop = asyncio.get_running_loop()
    gpu = await loop.run_in_executor(None, detect_gpu)
    stacks = await loop.run_in_executor(None, _discover_stacks, gpu.vendor)

    # Check running status
    running_pods = await _get_running_pods()
    for stack in stacks:
        if stack.slug in running_pods:
            stack.status = StackStatus.RUNNING
        elif gpu.vram_gb > 0 and stack.vram_gb > gpu.vram_gb:
            stack.status = StackStatus.EXCEEDS_VRAM
        else:
            stack.status = StackStatus.AVAILABLE

    return gpu, stacks


async def _get_running_pods() -> set[str]:
    """Get names of running podman pods."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "podman", "pod", "ls", "--format", "{{.Name}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            return {p.strip() for p in stdout.decode().split("\n") if p.strip()}
    except FileNotFoundError:
        pass
    return set()


async def deploy_stack(stack: AIStack) -> bool:
    """Deploy an AI stack via quadlet files.

    Steps:
      1. Copy .container + .network to ~/.config/containers/systemd/
      2. systemctl --user daemon-reload
      3. systemctl --user start <pod>
    """
    quadlet_dir = Path.home() / ".config" / "containers" / "systemd"
    quadlet_dir.mkdir(parents=True, exist_ok=True)

    # Copy quadlet files
    if stack.container_file:
        src = Path(stack.container_file)
        dst = quadlet_dir / src.name
        dst.write_text(src.read_text())

    if stack.network_file:
        src = Path(stack.network_file)
        dst = quadlet_dir / src.name
        dst.write_text(src.read_text())

    # Daemon reload
    proc = await asyncio.create_subprocess_exec(
        "systemctl", "--user", "daemon-reload",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()

    # Start the service
    service_name = Path(stack.container_file).stem if stack.container_file else stack.slug
    proc = await asyncio.create_subprocess_exec(
        "systemctl", "--user", "start", service_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    return proc.returncode == 0


async def stop_stack(stack: AIStack) -> bool:
    """Stop a running AI stack."""
    service_name = Path(stack.container_file).stem if stack.container_file else stack.slug
    proc = await asyncio.create_subprocess_exec(
        "systemctl", "--user", "stop", service_name,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    return proc.returncode == 0
