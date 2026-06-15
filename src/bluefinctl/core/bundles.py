"""Core business logic — Bundle management.

Bundles are curated Brewfile collections shipped with the system image.
They represent "loadouts" — personality facets the user opts into.

System bundles live at /usr/share/ublue-os/homebrew/*.Brewfile (read-only).
User state (which bundles are active) tracked in ~/.config/bluefinctl/state.json.
"""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path

from bluefinctl.core.progress import BrewInstallParser, ProgressUpdate

SYSTEM_BREWFILES = Path("/usr/share/ublue-os/homebrew")
STATE_DIR = Path.home() / ".config" / "bluefinctl"
STATE_FILE = STATE_DIR / "state.json"


class BundleCategory(StrEnum):
    """Visual grouping for bundles."""

    FOUNDATION = "Foundation"
    DEVELOPMENT = "Development"
    AI = "AI & ML"
    CLOUD = "Cloud & Infra"
    DESKTOP = "Desktop"


class BundleState(StrEnum):
    """Whether a bundle is active on this system."""

    BASE = "base"
    ACTIVE = "active"
    AVAILABLE = "available"
    PARTIAL = "partial"


@dataclass
class BundleMeta:
    """Static metadata for a bundle."""

    slug: str
    name: str
    description: str
    category: BundleCategory
    icon: str
    base: bool = False
    package_count: int = 0


BUNDLE_REGISTRY: dict[str, BundleMeta] = {
    "cli": BundleMeta(
        slug="cli",
        name="CLI Essentials",
        description="Core command-line tools — atuin, bat, eza, fd, gh, ripgrep, starship, zoxide",
        category=BundleCategory.FOUNDATION,
        icon=">>",
        base=True,
    ),
    "fonts": BundleMeta(
        slug="fonts",
        name="Nerd Fonts",
        description="Patched developer fonts — FiraCode, JetBrains Mono, Hack, Meslo, Noto",
        category=BundleCategory.FOUNDATION,
        icon="Aa",
    ),
    "ide": BundleMeta(
        slug="ide",
        name="IDEs",
        description="VS Code, Neovim, Helix, devcontainer CLI",
        category=BundleCategory.DEVELOPMENT,
        icon="[]",
    ),
    "experimental-ide": BundleMeta(
        slug="experimental-ide",
        name="Experimental IDEs",
        description="Bleeding edge — Cursor, Zed, individual JetBrains IDEs",
        category=BundleCategory.DEVELOPMENT,
        icon="~~",
    ),
    "swift": BundleMeta(
        slug="swift",
        name="Swift",
        description="Swift development tools — swiftly, swiftlint, swiftformat",
        category=BundleCategory.DEVELOPMENT,
        icon="<>",
    ),
    "ai-tools": BundleMeta(
        slug="ai-tools",
        name="AI Tools",
        description="AI CLI & desktop — claude-code, aichat, goose, ramalama, LM Studio, Ollama",
        category=BundleCategory.AI,
        icon="AI",
    ),
    "k8s-tools": BundleMeta(
        slug="k8s-tools",
        name="Kubernetes",
        description="Container orchestration — kubectl, helm, kind, k9s, k3d, lens",
        category=BundleCategory.CLOUD,
        icon="k8",
    ),
    "cncf": BundleMeta(
        slug="cncf",
        name="CNCF Landscape",
        description="89 Cloud Native Computing Foundation tools — graduated, incubating, sandbox",
        category=BundleCategory.CLOUD,
        icon="::",
    ),
    "full-desktop": BundleMeta(
        slug="full-desktop",
        name="GNOME Circle Apps",
        description="~60 curated GNOME desktop applications via Flatpak",
        category=BundleCategory.DESKTOP,
        icon="##",
    ),
    "system-flatpaks": BundleMeta(
        slug="system-flatpaks",
        name="System Flatpaks",
        description="Default desktop applications — browser, office, media, utilities",
        category=BundleCategory.DESKTOP,
        icon="==",
    ),
    "system-dx-flatpaks": BundleMeta(
        slug="system-dx-flatpaks",
        name="DX Flatpaks",
        description="Developer experience — Podman Desktop, Ptyxis, Warehouse",
        category=BundleCategory.DESKTOP,
        icon="dx",
    ),
    "artwork": BundleMeta(
        slug="artwork",
        name="Wallpapers",
        description="Curated wallpaper packs for your desktop",
        category=BundleCategory.DESKTOP,
        icon="**",
    ),
}


@dataclass
class Bundle:
    """A bundle with runtime state."""

    meta: BundleMeta
    state: BundleState = BundleState.AVAILABLE
    packages: list[str] = field(default_factory=list)
    installed_count: int = 0
    total_count: int = 0

    @property
    def name(self) -> str:
        return self.meta.name

    @property
    def icon(self) -> str:
        return self.meta.icon

    @property
    def state_indicator(self) -> str:
        """Return a status character for the sidebar/list."""
        match self.state:
            case BundleState.BASE:
                return "#"
            case BundleState.ACTIVE:
                return "*"
            case BundleState.PARTIAL:
                return "~"
            case BundleState.AVAILABLE:
                return "."
            case _:
                return "?"


@dataclass(frozen=True)
class DeactivationPreview:
    """Safe package plan for bundle deactivation."""

    slug: str
    removable_packages: tuple[str, ...]
    shared_packages: tuple[str, ...]
    missing_packages: tuple[str, ...]


def _parse_brewfile_names(path: Path) -> list[str]:
    """Extract package/cask/flatpak names from a Brewfile."""
    names: list[str] = []
    if not path.exists():
        return names

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for prefix in ("brew ", "cask ", "flatpak "):
            if line.startswith(prefix):
                rest = line[len(prefix):]
                name = rest.strip().strip('"').strip("'")
                if "," in name:
                    name = name.split(",")[0].strip().strip('"')
                names.append(name)
                break
    return names


def _get_installed_formulae() -> set[str]:
    """Get all currently installed brew formulae and casks."""
    installed = set()
    try:
        result = subprocess.run(
            ["brew", "list", "--formula", "-1"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            installed.update(result.stdout.strip().splitlines())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        result = subprocess.run(
            ["brew", "list", "--cask", "-1"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            installed.update(result.stdout.strip().splitlines())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return installed


def _get_installed_flatpaks() -> set[str]:
    """Get all installed flatpak application IDs."""
    try:
        result = subprocess.run(
            ["flatpak", "list", "--app", "--columns=application"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return set(result.stdout.strip().splitlines())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return set()


async def get_bundles() -> list[Bundle]:
    """Discover all available bundles and their activation state."""
    loop = asyncio.get_running_loop()

    installed_formulae = await loop.run_in_executor(None, _get_installed_formulae)
    installed_flatpaks = await loop.run_in_executor(None, _get_installed_flatpaks)
    all_installed = installed_formulae | installed_flatpaks

    bundles: list[Bundle] = []

    if SYSTEM_BREWFILES.exists():
        for brewfile in sorted(SYSTEM_BREWFILES.glob("*.Brewfile")):
            slug = brewfile.stem
            meta = BUNDLE_REGISTRY.get(slug)

            if meta is None:
                meta = BundleMeta(
                    slug=slug,
                    name=slug.replace("-", " ").title(),
                    description=f"Bundle: {slug}",
                    category=BundleCategory.DESKTOP,
                    icon="--",
                )

            packages = await loop.run_in_executor(None, _parse_brewfile_names, brewfile)
            meta = replace(meta, package_count=len(packages))

            installed_count = sum(1 for p in packages if p in all_installed)
            total_count = len(packages)

            if meta.base:
                state = BundleState.BASE
            elif total_count == 0:
                state = BundleState.AVAILABLE
            elif installed_count == total_count:
                state = BundleState.ACTIVE
            elif installed_count > 0:
                state = BundleState.PARTIAL
            else:
                state = BundleState.AVAILABLE

            bundles.append(Bundle(
                meta=meta,
                state=state,
                packages=packages,
                installed_count=installed_count,
                total_count=total_count,
            ))

    return bundles


async def preview_bundle_deactivation(slug: str) -> DeactivationPreview:
    """Return the safe deactivation plan for a bundle.

    Only installed packages unique to the selected bundle are removable. Packages
    also present in another active/base/partial bundle are protected as shared.
    """
    brewfile = SYSTEM_BREWFILES / f"{slug}.Brewfile"
    if not brewfile.exists():
        return DeactivationPreview(
            slug=slug,
            removable_packages=(),
            shared_packages=(),
            missing_packages=(),
        )

    target_packages = set(_parse_brewfile_names(brewfile))
    loop = asyncio.get_running_loop()
    installed_formulae = await loop.run_in_executor(None, _get_installed_formulae)
    installed_flatpaks = await loop.run_in_executor(None, _get_installed_flatpaks)
    installed = installed_formulae | installed_flatpaks

    protected: set[str] = set()
    for other_brewfile in sorted(SYSTEM_BREWFILES.glob("*.Brewfile")):
        other_slug = other_brewfile.stem
        if other_slug == slug:
            continue
        other_packages = _parse_brewfile_names(other_brewfile)
        other_meta = BUNDLE_REGISTRY.get(other_slug)
        other_installed_count = sum(1 for package in other_packages if package in installed)
        # Protect packages from any active, base, or partially-installed bundle.
        # Partial bundles may represent user-selected kit state; silently removing
        # their packages would break that state without the user knowing.
        if (other_meta and other_meta.base) or other_installed_count > 0:
            protected.update(other_packages)

    installed_target = target_packages & installed
    shared = installed_target & protected
    removable = installed_target - protected
    missing = target_packages - installed

    return DeactivationPreview(
        slug=slug,
        removable_packages=tuple(sorted(removable)),
        shared_packages=tuple(sorted(shared)),
        missing_packages=tuple(sorted(missing)),
    )


async def _run_command_updates(
    command: list[str],
    parser: BrewInstallParser,
) -> AsyncGenerator[ProgressUpdate]:
    proc = await asyncio.create_subprocess_exec(
        command[0],
        *command[1:],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout:
        async for raw_line in proc.stdout:
            line = raw_line.decode(errors="replace").rstrip()
            update = parser.parse_line(line)
            yield update or ProgressUpdate(message=line)
    rc = await proc.wait()
    if rc != 0:
        raise RuntimeError(f"Command failed ({rc}): {' '.join(command)}")


async def activate_bundle_steps(slug: str) -> AsyncGenerator[ProgressUpdate]:
    """Install a bundle and stream progress updates for OperationModal."""
    brewfile = SYSTEM_BREWFILES / f"{slug}.Brewfile"
    if not brewfile.exists():
        raise FileNotFoundError(f"Bundle not found: {slug}")

    packages = _parse_brewfile_names(brewfile)
    yield ProgressUpdate(percent=0, step=1, total_steps=2, message=f"Preparing {slug}")
    async for update in _run_command_updates(
        ["brew", "bundle", "install", f"--file={brewfile}"],
        BrewInstallParser(total_packages=len(packages)),
    ):
        yield update
    yield ProgressUpdate(percent=100, step=2, total_steps=2, message=f"{slug} activated")


async def deactivate_bundle_steps(
    slug: str,
    preview: DeactivationPreview | None = None,
) -> AsyncGenerator[ProgressUpdate]:
    """Safely deactivate a bundle and stream progress updates for OperationModal."""
    if preview is None:
        preview = await preview_bundle_deactivation(slug)
    total = max(len(preview.removable_packages), 1)

    if not preview.removable_packages:
        yield ProgressUpdate(
            percent=100,
            step=1,
            total_steps=1,
            message="No unique packages to remove",
        )
        return

    failures: list[str] = []
    for index, package in enumerate(preview.removable_packages, start=1):
        percent = ((index - 1) / total) * 100
        yield ProgressUpdate(
            percent=percent,
            step=index,
            total_steps=total,
            message=f"Removing {package}",
        )
        proc = await asyncio.create_subprocess_exec(
            "brew", "uninstall", "--ignore-dependencies", package,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            output = stdout.decode(errors="replace").strip()
            detail = f": {output}" if output else ""
            failures.append(package)
            yield ProgressUpdate(message=f"Failed to remove {package}{detail}")

    if failures:
        raise RuntimeError(
            f"Failed to remove {len(failures)} package(s): {', '.join(failures)}"
        )

    yield ProgressUpdate(percent=100, step=total, total_steps=total, message=f"{slug} deactivated")


async def activate_bundle(slug: str) -> bool:
    """Install a bundle (brew bundle --file=...)."""
    try:
        async for _update in activate_bundle_steps(slug):
            pass
    except (FileNotFoundError, RuntimeError):
        return False
    return True


async def deactivate_bundle(slug: str) -> tuple[bool, list[str]]:
    """Deactivate a bundle by removing only packages unique to that bundle."""
    preview = await preview_bundle_deactivation(slug)
    try:
        async for _update in deactivate_bundle_steps(slug, preview):
            pass
    except RuntimeError:
        return False, []
    return True, list(preview.removable_packages)


def get_bundles_by_category(bundles: list[Bundle]) -> dict[BundleCategory, list[Bundle]]:
    """Group bundles by their category for display."""
    grouped: dict[BundleCategory, list[Bundle]] = {}
    for cat in BundleCategory:
        grouped[cat] = []
    for bundle in bundles:
        grouped[bundle.meta.category].append(bundle)
    return grouped
