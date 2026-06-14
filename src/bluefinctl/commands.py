"""Command Palette providers for bluefinctl.

Provides package search (brew + flatpak), navigation, and action commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.command import Hit, Hits, Provider

if TYPE_CHECKING:
    pass


class PackageProvider(Provider):
    """Search and install/remove packages via brew and flatpak.

    Supports prefixed queries:
      install brew:<query>     — search Homebrew
      install flatpak:<query>  — search Flatpak
      remove brew:<query>      — find installed brew packages to remove
    """

    async def search(self, query: str) -> Hits:
        """Search packages based on prefixed query."""
        q = query.strip().lower()

        if q.startswith("install brew:"):
            remainder = q[len("install brew:"):].strip()
            if len(remainder) < 2:
                return
            from bluefinctl.core.brew import search_packages
            results = await search_packages(remainder)
            matcher = self.matcher(remainder)
            for result in results:
                score = matcher.match(result.name)
                if score > 0:
                    badge = f"[brew {result.type.value}]"
                    display = Text.assemble(
                        ("Install ", "bold"),
                        (result.name, ""),
                        (f" {badge}", "dim cyan"),
                    )
                    pkg_name = result.name
                    pkg_type = result.type

                    async def _install_brew(
                        name: str = pkg_name, ptype: str = pkg_type.value,
                    ) -> None:
                        from bluefinctl.core.brew import PackageType, add_package
                        pt = PackageType.CASK if ptype == "cask" else PackageType.FORMULA
                        await add_package(name, pt)
                        self.app.notify(
                            f"Installed {name}", title="Package", severity="information",
                        )

                    yield Hit(
                        score=score,
                        match_display=display,
                        command=_install_brew,
                        text=f"install brew:{result.name}",
                        help=f"Install {result.name} via Homebrew ({badge})",
                    )

        elif q.startswith("install flatpak:"):
            remainder = q[len("install flatpak:"):].strip()
            if len(remainder) < 2:
                return
            from bluefinctl.core.flatpak import search_packages as flatpak_search
            fp_results = await flatpak_search(remainder)
            matcher = self.matcher(remainder)
            for fp_result in fp_results:
                score = matcher.match(fp_result.name) or matcher.match(fp_result.app_id)
                if score > 0:
                    display = Text.assemble(
                        ("Install ", "bold"),
                        (fp_result.name, ""),
                        (" [flatpak]", "dim magenta"),
                    )
                    app_id = fp_result.app_id

                    async def _install_flatpak(fid: str = app_id) -> None:
                        from bluefinctl.core.flatpak import install_package
                        ok = await install_package(fid)
                        if ok:
                            self.app.notify(
                                f"Installed {fid}", title="Flatpak", severity="information",
                            )
                        else:
                            self.app.notify(
                                f"Failed to install {fid}", title="Flatpak", severity="error",
                            )

                    yield Hit(
                        score=score,
                        match_display=display,
                        command=_install_flatpak,
                        text=f"install flatpak:{fp_result.app_id}",
                        help=f"Install {fp_result.name} ({fp_result.app_id})",
                    )

        elif q.startswith("remove brew:"):
            remainder = q[len("remove brew:"):].strip()
            if len(remainder) < 2:
                return
            from bluefinctl.core.brew import get_brew_state
            state = await get_brew_state()
            matcher = self.matcher(remainder)
            for pkg in state.user_packages:
                score = matcher.match(pkg.name)
                if score > 0:
                    display = Text.assemble(
                        ("Remove ", "bold red"),
                        (pkg.name, ""),
                        (f" [{pkg.type.value}]", "dim"),
                    )
                    pkg_name = pkg.name

                    async def _remove_brew(name: str = pkg_name) -> None:
                        from bluefinctl.core.brew import remove_package
                        await remove_package(name)
                        self.app.notify(
                            f"Removed {name}", title="Package", severity="information",
                        )

                    yield Hit(
                        score=score,
                        match_display=display,
                        command=_remove_brew,
                        text=f"remove brew:{pkg.name}",
                        help=f"Remove {pkg.name} from user Brewfile",
                    )


class NavigationProvider(Provider):
    """Navigate between screens."""

    _SCREENS = [
        ("Go to System",    "system",  "System info and health"),
        ("Go to Updates",   "updates", "Update strategy and focus mode"),
        ("Go to Developer", "devmode", "Kits, developer tools, and environments"),
        ("Go to AI",        "ai",      "AI stack management"),
    ]

    async def search(self, query: str) -> Hits:
        """Match navigation commands."""
        matcher = self.matcher(query)
        for label, screen_name, help_text in self._SCREENS:
            score = matcher.match(label)
            if score > 0:
                name = screen_name

                async def _goto(target: str = name) -> None:
                    self.app.action_goto(target)  # type: ignore[attr-defined]

                yield Hit(
                    score=score,
                    match_display=Text(label),
                    command=_goto,
                    text=label,
                    help=help_text,
                )


class ActionsProvider(Provider):
    """Quick actions available from any screen."""

    _ACTIONS: list[tuple[str, str, str]] = [
        ("Update all",          "action_update_now",      "Trigger system update"),
        ("Pause updates",       "action_toggle_focus",    "Enable focus mode"),
        ("Enable developer mode","action_toggle_devmode", "Toggle devmode"),
        ("Open podman-tui",     "action_launch_podman_tui","Launch container manager"),
    ]

    async def search(self, query: str) -> Hits:
        """Match action commands."""
        matcher = self.matcher(query)
        for label, action_name, help_text in self._ACTIONS:
            score = matcher.match(label)
            if score > 0:
                action = action_name

                async def _run_action(act: str = action) -> None:
                    await self.app.run_action(act)

                yield Hit(
                    score=score,
                    match_display=Text(label),
                    command=_run_action,
                    text=label,
                    help=help_text,
                )
