"""Core business logic — Bundle management.

Bundles are curated Brewfile collections shipped with the system image.
They represent "loadouts" — personality facets the user opts into.

System bundles live at /usr/share/ublue-os/homebrew/*.Brewfile (read-only).
User state (which bundles are active) tracked in ~/.config/bluefinctl/state.json.
"""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

SYSTEM_BREWFILES = Path("/usr/share/ublue-os/homebrew")
STATE_DIR = Path.home() / ".config" / "bluefinctl"
STATE_FILE = STATE_DIR / "state.json"


class BundleCategory(str, Enum):
    """Visual grouping for bundles."""

    FOUNDATION = "Foundation"
    DEVELOPMENT = "Development"
    AI = "AI & ML"
    CLOUD = "Cloud & Infra"
    DESKTOP = "Desktop"


class BundleState(str, Enum):
    """Whether a bundle is active on this system."""

    BASE = "base"          # Always active (cli.Brewfile) — can't remove
    ACTIVE = "active"      # User opted in
    AVAILABLE = "available"  # Not installed
    PARTIAL = "partial"    # Some packages installed, not all


# ─── Bundle Registry ─────────────────────────────────────────
# Maps Brewfile stem → metadata. This is the knowledge of what
# each bundle IS — names, descriptions, categories.

@dataclass
class BundleMeta:
    """Static metadata for a bundle."""

    slug: str              # Filename stem (e.g., "cli", "ai-tools")
    name: str              # Human-friendly display name
    description: str       # One-line description
    category: BundleCategory
    icon: str              # Emoji icon for the list
    base: bool = False     # True = always active, can't deactivate
    package_count: int = 0  # Populated at runtime


BUNDLE_REGISTRY: dict[str, BundleMeta] = {
    "cli": BundleMeta(
        slug="cli",
        name="CLI Essentials",
        description="Core command-line tools — atuin, bat, eza, fd, gh, ripgrep, starship, zoxide",
        category=BundleCategory.FOUNDATION,
        icon="⌨️",
        base=True,
    ),
    "fonts": BundleMeta(
        slug="fonts",
        name="Nerd Fonts",
        description="Patched developer fonts — FiraCode, JetBrains Mono, Hack, Meslo, Noto",
        category=BundleCategory.FOUNDATION,
        icon="🔤",
    ),
    "ide": BundleMeta(
        slug="ide",
        name="IDEs",
        description="VS Code, Neovim, Helix, devcontainer CLI",
        category=BundleCategory.DEVELOPMENT,
        icon="📝",
    ),
    "experimental-ide": BundleMeta(
        slug="experimental-ide",
        name="Experimental IDEs",
        description="Bleeding edge — Cursor, Zed, individual JetBrains IDEs",
        category=BundleCategory.DEVELOPMENT,
        icon="🧪",
    ),
    "swift": BundleMeta(
        slug="swift",
        name="Swift",
        description="Swift development tools — swiftly, swiftlint, swiftformat",
        category=BundleCategory.DEVELOPMENT,
        icon="🐦",
    ),
    "ai-tools": BundleMeta(
        slug="ai-tools",
        name="AI Tools",
        description="AI CLI & desktop — claude-code, aichat, goose, ramalama, LM Studio, Ollama",
        category=BundleCategory.AI,
        icon="🤖",
    ),
    "k8s-tools": BundleMeta(
        slug="k8s-tools",
        name="Kubernetes",
        description="Container orchestration — kubectl, helm, kind, k9s, k3d, lens",
        category=BundleCategory.CLOUD,
        icon="☸️",
    ),
    "cncf": BundleMeta(
        slug="cncf",
        name="CNCF Landscape",
        description="89 Cloud Native Computing Foundation tools — graduated, incubating, sandbox",
        category=BundleCategory.CLOUD,
        icon="☁️",
    ),
    "full-desktop": BundleMeta(
        slug="full-desktop",
        name="GNOME Circle Apps",
        description="~60 curated GNOME desktop applications via Flatpak",
        category=BundleCategory.DESKTOP,
        icon="🖥️",
    ),
    "system-flatpaks": BundleMeta(
        slug="system-flatpaks",
        name="System Flatpaks",
        description="Default desktop applications — browser, office, media, utilities",
        category=BundleCategory.DESKTOP,
        icon="📦",
    ),
    "system-dx-flatpaks": BundleMeta(
        slug="system-dx-flatpaks",
        name="DX Flatpaks",
        description="Developer experience — Podman Desktop, Ptyxis, Warehouse",
        category=BundleCategory.DESKTOP,
        icon="🛠️",
    ),
    "artwork": BundleMeta(
        slug="artwork",
        name="Wallpapers",
        description="Curated wallpaper packs for your desktop",
        category=BundleCategory.DESKTOP,
        icon="🎨",
    ),
}


# ─── Runtime Bundle State ─────────────────────────────────────

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
                return "◆"  # Solid — always on
            case BundleState.ACTIVE:
                return "●"  # Filled circle — opted in
            case BundleState.PARTIAL:
                return "◐"  # Half — partially installed
            case BundleState.AVAILABLE:
                return "○"  # Empty — not installed


def _parse_brewfile_names(path: Path) -> list[str]:
    """Extract package/cask/flatpak names from a Brewfile."""
    names = []
    if not path.exists():
        return names

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Parse: brew "name", cask "name", flatpak "name"
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
    loop = asyncio.get_event_loop()

    # Get what's installed
    installed_formulae = await loop.run_in_executor(None, _get_installed_formulae)
    installed_flatpaks = await loop.run_in_executor(None, _get_installed_flatpaks)
    all_installed = installed_formulae | installed_flatpaks

    bundles: list[Bundle] = []

    # Discover system Brewfiles
    if SYSTEM_BREWFILES.exists():
        for brewfile in sorted(SYSTEM_BREWFILES.glob("*.Brewfile")):
            slug = brewfile.stem
            meta = BUNDLE_REGISTRY.get(slug)

            if meta is None:
                # Unknown bundle (not in registry) — create minimal metadata
                meta = BundleMeta(
                    slug=slug,
                    name=slug.replace("-", " ").title(),
                    description=f"Bundle: {slug}",
                    category=BundleCategory.DESKTOP,
                    icon="📋",
                )

            # Parse contents and check installation state
            packages = await loop.run_in_executor(None, _parse_brewfile_names, brewfile)
            meta.package_count = len(packages)

            # Determine state by checking how many packages are installed
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


async def activate_bundle(slug: str) -> bool:
    """Install a bundle (brew bundle --file=...)."""
    brewfile = SYSTEM_BREWFILES / f"{slug}.Brewfile"
    if not brewfile.exists():
        return False

    proc = await asyncio.create_subprocess_exec(
        "brew", "bundle", "install", f"--file={brewfile}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    await proc.communicate()
    return proc.returncode == 0


async def deactivate_bundle(slug: str) -> tuple[bool, list[str]]:
    """Deactivate a bundle — uninstall its packages that aren't in other active bundles.

    Returns (success, list of packages that were removed).
    """
    brewfile = SYSTEM_BREWFILES / f"{slug}.Brewfile"
    if not brewfile.exists():
        return False, []

    # Get this bundle's packages
    target_packages = set(_parse_brewfile_names(brewfile))

    # Get packages from all OTHER active bundles (don't remove shared packages)
    all_bundles = await get_bundles()
    shared_packages: set[str] = set()
    for bundle in all_bundles:
        if bundle.meta.slug != slug and bundle.state in (BundleState.ACTIVE, BundleState.BASE):
            other_brewfile = SYSTEM_BREWFILES / f"{bundle.meta.slug}.Brewfile"
            shared_packages.update(_parse_brewfile_names(other_brewfile))

    # Only remove packages unique to this bundle
    to_remove = target_packages - shared_packages
    removed = []

    for pkg in to_remove:
        proc = await asyncio.create_subprocess_exec(
            "brew", "uninstall", "--ignore-dependencies", pkg,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        if proc.returncode == 0:
            removed.append(pkg)

    return True, removed


def get_bundles_by_category(bundles: list[Bundle]) -> dict[BundleCategory, list[Bundle]]:
    """Group bundles by their category for display."""
    grouped: dict[BundleCategory, list[Bundle]] = {}
    for cat in BundleCategory:
        grouped[cat] = []
    for bundle in bundles:
        grouped[bundle.meta.category].append(bundle)
    return grouped
