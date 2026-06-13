"""System screen — identity, hardware, devmode, health at a glance.

This is the home screen. Shows:
- Image identity (name, tag, variant)
- Hardware (GPU, RAM)
- Mode (standard/developer)
- Active bundles summary
- Health checks (post-update)
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, Static

from bluefinctl.screens._sidebar import Sidebar


class IdentityCard(Static):
    """System identity — image name, tag, ref."""

    DEFAULT_CSS = """
    IdentityCard { height: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Label("⬡ Identity", classes="card--title")
        yield Label("Loading...", id="identity-info")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        from bluefinctl.core.system import get_system_info

        info = await get_system_info()
        self.query_one("#identity-info", Label).update(
            f"Image:    {info.image_name}:{info.image_tag}\n"
            f"Vendor:   projectbluefin\n"
            f"Boot:     {info.boot_status}\n"
            f"Hostname: {info.hostname or 'unknown'}"
        )


class HardwareCard(Static):
    """Hardware summary — GPU, basic specs."""

    DEFAULT_CSS = """
    HardwareCard { height: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Label("⚙ Hardware", classes="card--title")
        yield Label("Loading...", id="hardware-info")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        from bluefinctl.core.system import get_system_info

        info = await get_system_info()
        gpu_line = f"{info.gpu.icon} {info.gpu.vendor.upper()} {info.gpu.model}"
        if info.gpu.vram_mb:
            gpu_line += f" ({info.gpu.vram_mb // 1024}GB VRAM)"

        self.query_one("#hardware-info", Label).update(
            f"GPU:  {gpu_line}\n"
            f"Mode: {'🛠️  Developer' if info.devmode else '📦 Standard'}"
        )


class BundleSummaryCard(Static):
    """Quick summary of active bundles."""

    DEFAULT_CSS = """
    BundleSummaryCard { height: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Label("◆ Active Bundles", classes="card--title")
        yield Label("Loading...", id="bundles-summary")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        from bluefinctl.core.bundles import BundleState, get_bundles

        bundles = await get_bundles()
        active = [b for b in bundles if b.state in (BundleState.BASE, BundleState.ACTIVE)]
        partial = [b for b in bundles if b.state == BundleState.PARTIAL]
        available = [b for b in bundles if b.state == BundleState.AVAILABLE]

        lines = []
        for b in active:
            lines.append(f"  {b.icon} {b.name}")
        if partial:
            lines.append("")
            for b in partial:
                lines.append(f"  {b.icon} {b.name} (partial)")
        lines.append(f"\n  {len(active)} active / {len(available)} available — press [2] for details")

        self.query_one("#bundles-summary", Label).update("\n".join(lines))


class HealthCard(Static):
    """Post-update health checks."""

    DEFAULT_CSS = """
    HealthCard { height: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Label("♥ Health", classes="card--title")
        yield Label("Loading...", id="health-info")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        import asyncio

        checks = []

        # GPU driver
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi", stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            checks.append("✓ GPU driver" if proc.returncode == 0 else "✗ GPU driver")
        except FileNotFoundError:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "rocm-smi", stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.communicate()
                checks.append("✓ GPU driver" if proc.returncode == 0 else "✗ GPU driver")
            except FileNotFoundError:
                checks.append("─ GPU (no discrete GPU)")

        # systemd
        try:
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "is-system-running",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            status = stdout.decode().strip()
            if status == "running":
                checks.append("✓ System services")
            elif status == "degraded":
                checks.append("⚠ System services (degraded)")
            else:
                checks.append(f"✗ System services ({status})")
        except FileNotFoundError:
            checks.append("─ systemd unavailable")

        # Homebrew
        try:
            proc = await asyncio.create_subprocess_exec(
                "brew", "--prefix",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            checks.append("✓ Homebrew" if proc.returncode == 0 else "✗ Homebrew")
        except FileNotFoundError:
            checks.append("✗ Homebrew not found")

        self.query_one("#health-info", Label).update("  " + "\n  ".join(checks))


class SystemScreen(Screen):
    """System overview — the home screen."""

    BINDINGS = [
        ("d", "toggle_devmode", "Toggle Devmode"),
        ("r", "system_report", "System Report"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Sidebar("system")
            with Vertical(id="main-content"):
                with Container(classes="card"):
                    yield IdentityCard()
                with Container(classes="card"):
                    yield HardwareCard()
                with Container(classes="card"):
                    yield BundleSummaryCard()
                with Container(classes="card"):
                    yield HealthCard()

    async def action_toggle_devmode(self) -> None:
        self.notify("Toggling developer mode...", title="Devmode")

    async def action_system_report(self) -> None:
        self.notify("Generating system report...", title="Report")
