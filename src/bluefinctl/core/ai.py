"""Core business logic — AI stack and tool management.

Handles:
- GPU detection (NVIDIA CDI / AMD KFD)
- Stack discovery from /usr/share/ublue-os/{nvidia,amd}-stacks/
- Preflight checks (VRAM, ports, auth, disk)
- Deploy/stop lifecycle via Podman Quadlets
- AI tool inventory and install workflows
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import subprocess
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path

from bluefinctl.core.progress import ProgressUpdate


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


@dataclass(frozen=True)
class AITool:
    """An AI-related tool with install/source metadata and runtime status."""

    slug: str
    command: str
    name: str
    description: str
    category: str
    installed: bool
    source: str


BUNDLE_AI_TOOLS_SOURCE = "bundle:ai-tools"
AI_TOOLS_KIT_SLUG = "ai-tools-kit"
# Bundle catalog slug used by activate_bundle_steps(); distinct from the
# AI_TOOLS_KIT_SLUG registry row identifier.
_AI_BUNDLE_CATALOG_SLUG = "ai-tools"

AI_TOOL_REGISTRY: tuple[AITool, ...] = (
    AITool(
        slug=AI_TOOLS_KIT_SLUG,
        command="",
        name="AI Tools kit",
        description="Install the curated Project Bluefin AI tooling bundle",
        category="Bundle",
        installed=False,
        source=BUNDLE_AI_TOOLS_SOURCE,
    ),
    AITool(
        slug="lemonade",
        command="lemonade",
        name="Lemonade",
        description="AMD-native LLM server",
        category="Local AI",
        installed=False,
        source=BUNDLE_AI_TOOLS_SOURCE,
    ),
    AITool(
        slug="whisper",
        command="whisper-cpp",
        name="Whisper",
        description="Speech-to-text tooling",
        category="Local AI",
        installed=False,
        source=BUNDLE_AI_TOOLS_SOURCE,
    ),
    AITool(
        slug="llm",
        command="llm",
        name="llm",
        description="CLI for language models",
        category="Local AI",
        installed=False,
        source=BUNDLE_AI_TOOLS_SOURCE,
    ),
    AITool(
        slug="coding-agents",
        command="goose",
        name="Coding agents",
        description="Goose, Claude Code, Aider, and other terminal agents",
        category="Coding Agents",
        installed=False,
        source=BUNDLE_AI_TOOLS_SOURCE,
    ),
    AITool(
        slug="docker-model",
        command="docker",
        name="Docker Model",
        description="Docker model management CLI",
        category="Model Tools",
        installed=False,
        source="external:docker-desktop",
    ),
)


def detect_gpu() -> GpuDetection:
    """Detect GPU vendor, model, VRAM, and runtime readiness."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            model = parts[0] if parts else "Unknown"
            vram_mb = int(parts[1]) if len(parts) > 1 else 0
            driver = parts[2] if len(parts) > 2 else ""

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
                    with contextlib.suppress(ValueError, IndexError):
                        val = int(line.split()[-1])
                        vram_gb = val // (1024 * 1024 * 1024) if val > 1000000 else val // 1024

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


# Commands that indicate the AI tools bundle is at least partially installed.
# Derived from registry members whose source is "bundle:ai-tools" so this list
# stays in sync automatically when the registry is updated.
_BUNDLE_AI_TOOLS_COMMANDS: tuple[str, ...] = tuple(
    t.command
    for t in AI_TOOL_REGISTRY
    if t.source == BUNDLE_AI_TOOLS_SOURCE and t.command and t.slug != AI_TOOLS_KIT_SLUG
)

# Commands whose presence counts as the coding-agents group being installed.
# The coding-agents Brewfile is an aggregated bundle entry that installs multiple
# tools (goose, claude, aider); checking any of these is sufficient to mark the
# group as present without requiring every tool to exist on every machine.
_CODING_AGENT_COMMANDS: tuple[str, ...] = ("goose", "claude", "aider")


def _has_docker_model() -> bool:
    """Return True only if `docker model` sub-command is available."""
    try:
        result = subprocess.run(
            ["docker", "model", "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def get_ai_tools_status() -> list[AITool]:
    """Return AI tools with current install status."""
    installed_commands = {
        tool.command
        for tool in AI_TOOL_REGISTRY
        if tool.command and shutil.which(tool.command)
    }
    kit_installed = any(shutil.which(cmd) for cmd in _BUNDLE_AI_TOOLS_COMMANDS)

    tools: list[AITool] = []
    for tool in AI_TOOL_REGISTRY:
        if tool.slug == AI_TOOLS_KIT_SLUG:
            installed = kit_installed
        elif tool.slug == "coding-agents":
            installed = any(shutil.which(cmd) for cmd in _CODING_AGENT_COMMANDS)
        elif tool.slug == "docker-model":
            installed = _has_docker_model()
        elif tool.command:
            installed = tool.command in installed_commands
        else:
            installed = False
        tools.append(replace(tool, installed=installed))
    return tools


async def install_ai_tools_kit_steps() -> AsyncGenerator[ProgressUpdate, None]:
    """Install/update the AI Tools bundle."""
    from bluefinctl.core.bundles import activate_bundle_steps

    async for update in activate_bundle_steps(_AI_BUNDLE_CATALOG_SLUG):
        yield update


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

        env: dict[str, str] = {}
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"')

        ports: dict[str, int] = {}
        port_str = env.get("STACK_PORTS", "")
        if port_str:
            for mapping in port_str.split(","):
                if ":" in mapping:
                    name, port = mapping.split(":", 1)
                    with contextlib.suppress(ValueError):
                        ports[name.strip()] = int(port.strip())

        container_file = ""
        network_file = ""
        for file in entry.iterdir():
            if file.suffix == ".container":
                container_file = str(file)
            elif file.suffix == ".network":
                network_file = str(file)

        category = StackCategory.SERVE
        with contextlib.suppress(ValueError):
            category = StackCategory(env.get("STACK_CATEGORY", "serve"))

        stack = AIStack(
            slug=entry.name,
            name=env.get("STACK_NAME", entry.name.title()),
            description=env.get("STACK_DESC", ""),
            category=category,
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

    stacks.sort(key=lambda stack: stack.order)
    return stacks


async def get_stacks() -> tuple[GpuDetection, list[AIStack]]:
    """Get GPU info and available stacks."""
    loop = asyncio.get_running_loop()
    gpu = await loop.run_in_executor(None, detect_gpu)
    stacks = await loop.run_in_executor(None, _discover_stacks, gpu.vendor)

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


async def _run_systemctl_user(*args: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "systemctl", "--user", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30.0)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        raise RuntimeError(f"systemctl --user {' '.join(args)} timed out") from None
    if proc.returncode != 0:
        output = stdout.decode(errors="replace").strip()
        detail = f": {output}" if output else ""
        raise RuntimeError(f"systemctl --user {' '.join(args)} failed{detail}")


def _stack_service_name(stack: AIStack) -> str:
    return Path(stack.container_file).stem if stack.container_file else stack.slug


def _copy_quadlets(stack: AIStack) -> int:
    """Copy quadlet files to the user systemd directory synchronously.

    Returns the number of files copied.  Uses :func:`shutil.copy2` so
    file metadata is preserved and the write never blocks the event loop.
    """
    quadlet_dir = Path.home() / ".config" / "containers" / "systemd"
    quadlet_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for source_file in (stack.container_file, stack.network_file):
        if not source_file:
            continue
        src = Path(source_file)
        shutil.copy2(src, quadlet_dir / src.name)
        copied += 1
    return copied


async def deploy_stack_steps(stack: AIStack) -> AsyncGenerator[ProgressUpdate, None]:
    """Deploy an AI stack via quadlet files with OperationModal progress."""
    total_steps = 5
    yield ProgressUpdate(
        percent=0,
        step=1,
        total_steps=total_steps,
        message="Preparing quadlet directory",
    )

    loop = asyncio.get_running_loop()
    copied = await loop.run_in_executor(None, _copy_quadlets, stack)

    yield ProgressUpdate(
        percent=25,
        step=2,
        total_steps=total_steps,
        message=f"Copied {copied} quadlet file(s)",
    )

    yield ProgressUpdate(
        percent=50,
        step=3,
        total_steps=total_steps,
        message="Reloading user systemd",
    )
    await _run_systemctl_user("daemon-reload")

    service_name = _stack_service_name(stack)
    yield ProgressUpdate(
        percent=75,
        step=4,
        total_steps=total_steps,
        message=f"Starting {service_name}",
    )
    await _run_systemctl_user("start", service_name)

    yield ProgressUpdate(
        percent=100,
        step=total_steps,
        total_steps=total_steps,
        message=f"{stack.name or stack.slug} deployed",
    )


async def deploy_stack(stack: AIStack) -> bool:
    """Deploy an AI stack via quadlet files for CLI compatibility."""
    try:
        async for _update in deploy_stack_steps(stack):
            pass
    except (OSError, RuntimeError):
        return False
    return True


async def stop_stack_steps(stack: AIStack) -> AsyncGenerator[ProgressUpdate, None]:
    """Stop a running AI stack with OperationModal progress."""
    service_name = _stack_service_name(stack)
    yield ProgressUpdate(percent=0, step=1, total_steps=2, message=f"Stopping {service_name}")
    await _run_systemctl_user("stop", service_name)
    yield ProgressUpdate(
        percent=100,
        step=2,
        total_steps=2,
        message=f"{stack.name or stack.slug} stopped",
    )


async def stop_stack(stack: AIStack) -> bool:
    """Stop a running AI stack."""
    try:
        async for _update in stop_stack_steps(stack):
            pass
    except (OSError, RuntimeError):
        return False
    return True
