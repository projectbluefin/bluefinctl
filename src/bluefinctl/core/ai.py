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
    arch: str = ""  # e.g. "strix-halo" — empty means any AMD GPU
    long_description: str = ""  # multi-sentence description for the detail pane
    requires_kfd: bool = False  # derived from container file — True if AddDevice=/dev/kfd present

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
    # Bundle entry — triggers full bundle install when selected
    AITool(
        slug=AI_TOOLS_KIT_SLUG,
        command="",
        name="AI Tools kit",
        description="Install the curated Project Bluefin AI tooling bundle",
        category="Bundle",
        installed=False,
        source=BUNDLE_AI_TOOLS_SOURCE,
    ),
    # Coding Agents
    AITool(
        slug="goose",
        command="goose",
        name="Goose",
        description="Block Protocol AI agent",
        category="Coding Agents",
        installed=False,
        source=BUNDLE_AI_TOOLS_SOURCE,
    ),
    AITool(
        slug="claude-code",
        command="claude",
        name="Claude Code",
        description="Anthropic coding agent",
        category="Coding Agents",
        installed=False,
        source=BUNDLE_AI_TOOLS_SOURCE,
    ),
    AITool(
        slug="copilot-cli",
        command="gh-copilot",
        name="GitHub Copilot CLI",
        description="GitHub Copilot in the terminal (via gh extension)",
        category="Coding Agents",
        installed=False,
        source=BUNDLE_AI_TOOLS_SOURCE,
    ),
    AITool(
        slug="aider",
        command="aider",
        name="Aider",
        description="AI pair programming in the terminal",
        category="Coding Agents",
        installed=False,
        source=BUNDLE_AI_TOOLS_SOURCE,
    ),
    # Local AI
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
        slug="aichat",
        command="aichat",
        name="aichat",
        description="AI-powered shell assistant with model routing",
        category="Local AI",
        installed=False,
        source=BUNDLE_AI_TOOLS_SOURCE,
    ),
    AITool(
        slug="ramalama",
        command="ramalama",
        name="RamaLama",
        description="Run AI models locally via OCI containers",
        category="Local AI",
        installed=False,
        source=BUNDLE_AI_TOOLS_SOURCE,
    ),
    # Model Tools
    AITool(
        slug="docker-model",
        command="docker",
        name="Docker Model",
        description="Docker model management CLI",
        category="Model Tools",
        installed=False,
        source="external:docker-desktop",
    ),
    AITool(
        slug="lm-studio",
        command="lms",
        name="LM Studio",
        description="Desktop app for running local LLMs",
        category="Model Tools",
        installed=False,
        source=BUNDLE_AI_TOOLS_SOURCE,
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

    # AMD via sysfs — no root required
    import os as _os
    try:
        for _entry in sorted(_os.listdir("/sys/class/drm")):
            if not _entry.startswith("card") or "-" in _entry:
                continue
            _vendor_path = f"/sys/class/drm/{_entry}/device/vendor"
            if not _os.path.exists(_vendor_path):
                continue
            with open(_vendor_path) as _vf:
                if _vf.read().strip() != "0x1002":
                    continue
            # AMD card found
            _model = "AMD Radeon"
            try:
                _lspci = subprocess.run(
                    ["lspci", "-d", "1002:"],
                    capture_output=True, text=True, timeout=3,
                ).stdout
                for _line in _lspci.splitlines():
                    if "VGA" in _line or "Display" in _line or "3D" in _line:
                        _model = _line.split(": ", 1)[-1]
                        break
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                pass
            _vram_gb = 0
            _vram_path = f"/sys/class/drm/{_entry}/device/mem_info_vram_total"
            if _os.path.exists(_vram_path):
                with contextlib.suppress(ValueError, OSError), open(_vram_path) as _mf:
                    _vram_gb = int(_mf.read().strip()) // (1024 * 1024 * 1024)
            _kfd_ok = _os.path.exists("/dev/kfd") and _os.path.exists("/sys/class/kfd/kfd")
            return GpuDetection(
                vendor=GpuVendor.AMD,
                model=_model,
                vram_gb=_vram_gb,
                kfd_ok=_kfd_ok,
            )
    except (FileNotFoundError, PermissionError, OSError):
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
        elif tool.slug == "docker-model":
            installed = _has_docker_model()
        elif tool.command:
            installed = tool.command in installed_commands
        else:
            installed = False
        tools.append(replace(tool, installed=installed))
    return tools


async def install_ai_tools_kit_steps() -> AsyncGenerator[ProgressUpdate]:
    """Install/update the AI Tools bundle."""
    from bluefinctl.core.bundles import activate_bundle_steps

    async for update in activate_bundle_steps(_AI_BUNDLE_CATALOG_SLUG):
        yield update


def _bundled_stack_dir(vendor: GpuVendor) -> Path:
    """Return the bundled stacks directory for the given vendor."""
    import importlib.resources
    vendor_name = "nvidia" if vendor == GpuVendor.NVIDIA else "amd"
    ref = importlib.resources.files("bluefinctl") / "stacks" / vendor_name
    return Path(str(ref))


def _discover_stacks(vendor: GpuVendor) -> list[AIStack]:
    """Discover AI stacks, preferring system dirs and falling back to bundled."""
    stacks: list[AIStack] = []

    if vendor == GpuVendor.NVIDIA:
        stack_dir = Path("/usr/share/ublue-os/nvidia-stacks")
    elif vendor == GpuVendor.AMD:
        stack_dir = Path("/usr/share/ublue-os/amd-stacks")
    else:
        return stacks

    if not stack_dir.exists():
        stack_dir = _bundled_stack_dir(vendor)
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

        requires_kfd = False
        if container_file:
            with contextlib.suppress(OSError):
                requires_kfd = "AddDevice=/dev/kfd" in Path(container_file).read_text()

        stack = AIStack(
            slug=entry.name,
            name=env.get("STACK_NAME", entry.name.title()),
            description=env.get("STACK_DESC", ""),
            long_description=env.get("STACK_LONG_DESC", ""),
            arch=env.get("STACK_ARCH", ""),
            category=category,
            vram_gb=int(env.get("STACK_VRAM_GB", "0")),
            disk_gb=int(env.get("STACK_DISK_GB", "0")),
            ports=ports,
            requires_ngc_auth=env.get("STACK_REQUIRES_NGC_AUTH", "false").lower() == "true",
            requires_hf_auth=env.get("STACK_REQUIRES_HF_AUTH", "false").lower() == "true",
            order=int(env.get("STACK_ORDER", "99")),
            container_file=container_file,
            network_file=network_file,
            requires_kfd=requires_kfd,
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


def _read_version_file(vendor: GpuVendor) -> str:
    """Read the vendor version file bundled alongside the stacks."""
    import importlib.resources
    filename = "rocm-version" if vendor == GpuVendor.AMD else "ngc-month"
    ref = importlib.resources.files("bluefinctl") / "stacks" / vendor.value / filename
    with contextlib.suppress(OSError, TypeError):
        return Path(str(ref)).read_text().strip()
    return ""


def _copy_quadlets(stack: AIStack) -> int:
    """Copy quadlet files to the user systemd directory, substituting version variables.

    Substitutions applied before writing:
      ${ROCM_VERSION}  → content of stacks/amd/rocm-version
      ${NGC_MONTH}     → content of stacks/nvidia/ngc-month

    Returns the number of files copied.
    """
    quadlet_dir = Path.home() / ".config" / "containers" / "systemd"
    quadlet_dir.mkdir(parents=True, exist_ok=True)

    rocm_version = _read_version_file(GpuVendor.AMD)
    ngc_month = _read_version_file(GpuVendor.NVIDIA)

    # Load stack-specific env vars (LLAMA_MODEL, VLLM_MODEL, etc.)
    stack_env: dict[str, str] = {}
    if stack.container_file:
        env_file = Path(stack.container_file).parent / "stack.env"
        with contextlib.suppress(OSError):
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                stack_env[key.strip()] = value.strip().strip('"')

    copied = 0
    for source_file in (stack.container_file, stack.network_file):
        if not source_file:
            continue
        src = Path(source_file)
        text = src.read_text()
        if rocm_version:
            text = text.replace("${ROCM_VERSION}", rocm_version)
        if ngc_month:
            text = text.replace("${NGC_MONTH}", ngc_month)
        for var, val in stack_env.items():
            text = text.replace(f"${{{var}}}", val)
        dest = quadlet_dir / src.name
        dest.write_text(text)
        shutil.copystat(src, dest)
        copied += 1
    return copied


async def deploy_stack_steps(stack: AIStack) -> AsyncGenerator[ProgressUpdate]:
    """Deploy an AI stack via quadlet files with OperationModal progress."""
    import getpass
    import grp
    import os

    # Preflight: render group membership for KFD/ROCm stacks
    if stack.requires_kfd:
        try:
            render_gid = grp.getgrnam("render").gr_gid
            in_render = render_gid in os.getgroups()
        except KeyError:
            in_render = True  # render group doesn't exist — skip
        if not in_render:
            username = getpass.getuser()
            yield ProgressUpdate(
                percent=0,
                step=1,
                total_steps=6,
                message=f"Adding {username} to render group (requires password)…",
            )
            proc = await asyncio.create_subprocess_exec(
                "pkexec", "usermod", "-aG", "render", username,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                await asyncio.wait_for(proc.communicate(), timeout=30.0)
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
            if proc.returncode == 0:
                yield ProgressUpdate(
                    percent=5,
                    step=1,
                    total_steps=6,
                    message="Added to render group — effective on next login",
                )
            else:
                yield ProgressUpdate(
                    percent=5,
                    step=1,
                    total_steps=6,
                    message="Could not add to render group — continuing anyway",
                )
            total_steps = 6
            step_offset = 1
        else:
            total_steps = 5
            step_offset = 0
    else:
        total_steps = 5
        step_offset = 0

    yield ProgressUpdate(
        percent=max(5, 0),
        step=1 + step_offset,
        total_steps=total_steps,
        message="Preparing quadlet directory",
    )

    loop = asyncio.get_running_loop()
    copied = await loop.run_in_executor(None, _copy_quadlets, stack)

    yield ProgressUpdate(
        percent=25 + step_offset * 5,
        step=2 + step_offset,
        total_steps=total_steps,
        message=f"Copied {copied} quadlet file(s)",
    )

    yield ProgressUpdate(
        percent=50 + step_offset * 5,
        step=3 + step_offset,
        total_steps=total_steps,
        message="Reloading user systemd",
    )
    await _run_systemctl_user("daemon-reload")

    service_name = _stack_service_name(stack)
    yield ProgressUpdate(
        percent=75 + step_offset * 5,
        step=4 + step_offset,
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


async def remove_stack_steps(stack: AIStack) -> AsyncGenerator[ProgressUpdate]:
    """Remove a deployed AI stack: stop, disable, delete quadlet files, daemon-reload."""
    service_name = _stack_service_name(stack)
    quadlet_dir = Path.home() / ".config" / "containers" / "systemd"
    total_steps = 4

    yield ProgressUpdate(
        percent=0, step=1, total_steps=total_steps, message=f"Stopping {service_name}",
    )
    with contextlib.suppress(RuntimeError):
        await _run_systemctl_user("stop", service_name)

    yield ProgressUpdate(
        percent=33, step=2, total_steps=total_steps, message=f"Disabling {service_name}",
    )
    with contextlib.suppress(RuntimeError):
        await _run_systemctl_user("disable", service_name)

    yield ProgressUpdate(
        percent=66, step=3, total_steps=total_steps, message="Removing quadlet files",
    )
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _remove_quadlet_files, stack, quadlet_dir)

    yield ProgressUpdate(
        percent=90, step=4, total_steps=total_steps, message="Reloading user systemd",
    )
    with contextlib.suppress(RuntimeError):
        await _run_systemctl_user("daemon-reload")

    yield ProgressUpdate(
        percent=100,
        step=total_steps,
        total_steps=total_steps,
        message=f"{stack.name or stack.slug} removed",
    )


def _remove_quadlet_files(stack: AIStack, quadlet_dir: Path) -> None:
    for source_file in (stack.container_file, stack.network_file):
        if not source_file:
            continue
        dest = quadlet_dir / Path(source_file).name
        with contextlib.suppress(FileNotFoundError):
            dest.unlink()


async def stop_stack_steps(stack: AIStack) -> AsyncGenerator[ProgressUpdate]:
    """Remove a deployed AI stack (alias kept for CLI compat — delegates to remove_stack_steps)."""
    async for update in remove_stack_steps(stack):
        yield update


async def stop_stack(stack: AIStack) -> bool:
    """Remove a deployed AI stack (CLI path)."""
    try:
        async for _update in remove_stack_steps(stack):
            pass
    except (OSError, RuntimeError):
        return False
    return True
