"""Developer screen — feature portal for Bluefin DX tools.

Design:
  Single scrollable screen. No tabs, no devmode toggle, no modals.
  Each section is an AdwPreferencesGroup presenting a named Bluefin capability.
  Install/detected state shown via inline buttons on each row.
  OpsBar shows progress for every install operation.

On mount: silently runs `ujust dx-group` via pkexec (adds docker/libvirt/
  incus-admin/dialout groups).  Invisible infrastructure — errors swallowed.
"""

from __future__ import annotations

import asyncio

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button

from bluefinctl.core.notify import system_notify
from bluefinctl.screens._viewswitcher import ViewSwitcher
from bluefinctl.widgets.adw import AdwActionRow, AdwPreferencesGroup
from bluefinctl.widgets.ops_bar import OpsBar


def _install_btn(tool_id: str) -> Button:
    """Return the initial Install button for a tool row."""
    return Button("Install", id=f"install-{tool_id}", variant="primary")


class DevModeScreen(Screen[None]):
    """Developer — feature portal for installing and managing DX tools."""

    DEFAULT_CSS = """
    DevModeScreen { layout: vertical; }
    #adw-content  { height: 1fr; scrollbar-gutter: stable; }
    .adw-cols     { height: auto; }
    .adw-col      { width: 1fr; padding: 0 2; }
    DevModeScreen AdwActionRow { height: 3; }
    DevModeScreen AdwActionRow > .adw-row-content > .adw-row-subtitle { overflow-x: hidden; }
    """

    def compose(self) -> ComposeResult:
        yield ViewSwitcher("devmode")
        with ScrollableContainer(id="adw-content"):
            with Horizontal(classes="adw-cols"):

                # ── Left column: Cloud Native Development ────────────────────
                with Vertical(classes="adw-col"):
                    yield AdwPreferencesGroup(
                        "Cloud Native Development",
                        AdwActionRow(
                            "Podman Desktop",
                            subtitle="Podman and Podman Desktop from the CNCF.",
                            trailing=_install_btn("podman"),
                            id="tool-podman",
                        ),
                        AdwActionRow(
                            "The Bluefin WSL Experience",
                            subtitle=(
                                "Persistent Ubuntu VM powered by Lima (CNCF). "
                                "VS Code SSH wired. limactl shell ubuntu"
                            ),
                            trailing=_install_btn("lima"),
                            id="tool-lima",
                        ),
                        AdwActionRow(
                            "Incus",
                            subtitle=(
                                "System containers and VMs via Homebrew. "
                                "Fully supported third option."
                            ),
                            trailing=_install_btn("incus"),
                            id="tool-incus",
                        ),
                        AdwActionRow(
                            "Docker",
                            subtitle="Docker + compose + lazydocker + dive.",
                            trailing=_install_btn("docker"),
                            id="tool-docker",
                        ),
                    )
                    yield AdwPreferencesGroup(
                        "Virtualization",
                        AdwActionRow(
                            "Virtual Machines",
                            subtitle="virt-manager + QEMU. Linux and Windows VMs.",
                            trailing=_install_btn("vms"),
                            id="tool-vms",
                        ),
                    )

                # ── Right column: Editors + Virtualization ────────────────────
                with Vertical(classes="adw-col"):
                    yield AdwPreferencesGroup(
                        "Editors",
                        AdwActionRow(
                            "VS Code",
                            subtitle="The world's most popular editor, native on Linux.",
                            trailing=_install_btn("vscode"),
                            id="tool-vscode",
                        ),
                        AdwActionRow(
                            "JetBrains Toolbox",
                            subtitle="Manage all JetBrains IDEs from one launcher.",
                            trailing=_install_btn("jetbrains"),
                            id="tool-jetbrains",
                        ),
                        AdwActionRow(
                            "Zed",
                            subtitle="A high-performance editor built in Rust.",
                            trailing=_install_btn("zed"),
                            id="tool-zed",
                        ),
                        AdwActionRow(
                            "VSCodium",
                            subtitle="VS Code without Microsoft telemetry.",
                            trailing=_install_btn("vscodium"),
                            id="tool-vscodium",
                        ),
                        AdwActionRow(
                            "Neovim",
                            subtitle="Hyperextensible Vim-based text editor.",
                            trailing=_install_btn("neovim"),
                            id="tool-neovim",
                        ),
                        AdwActionRow(
                            "Helix",
                            subtitle="A post-modern modal editor.",
                            trailing=_install_btn("helix"),
                            id="tool-helix",
                        ),
                    )

        yield OpsBar()

    # ── Mount ─────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        # Silent DX group provisioning — invisible infrastructure
        self.run_worker(self._setup_dx_groups(), exclusive=False)
        # Detect installed state and update buttons
        self.run_worker(self._detect_installed(), exclusive=False)

    async def _setup_dx_groups(self) -> None:
        """Silently provision DX groups via pkexec.  Errors are swallowed."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "pkexec", "ujust", "dx-group",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:  # noqa: BLE001
            pass

    async def _detect_installed(self) -> None:
        """Check install state for all tools and update button labels."""
        from bluefinctl.core.devmode import (
            is_docker_installed,
            is_helix_installed,
            is_incus_installed,
            is_jetbrains_installed,
            is_lima_installed,
            is_neovim_installed,
            is_podman_desktop_installed,
            is_vms_installed,
            is_vscode_installed,
            is_vscodium_installed,
            is_zed_installed,
        )

        loop = asyncio.get_running_loop()
        detectors: dict[str, object] = {
            "docker":    is_docker_installed,
            "podman":    is_podman_desktop_installed,
            "lima":      is_lima_installed,
            "incus":     is_incus_installed,
            "vscode":    is_vscode_installed,
            "vscodium":  is_vscodium_installed,
            "zed":       is_zed_installed,
            "jetbrains": is_jetbrains_installed,
            "neovim":    is_neovim_installed,
            "helix":     is_helix_installed,
            "vms":       is_vms_installed,
        }
        from typing import Any
        tool_ids = list(detectors.keys())
        raw_tasks: list[Any] = [
            loop.run_in_executor(None, detectors[tid])  # type: ignore[arg-type]
            for tid in tool_ids
        ]
        gather_results: list[Any] = list(
            await asyncio.gather(*raw_tasks, return_exceptions=True)
        )
        for tool_id, result in zip(tool_ids, gather_results, strict=True):
            if isinstance(result, bool):
                self._update_tool_button(tool_id, result)

    # ── Button helpers ────────────────────────────────────────────────────────

    def _update_tool_button(self, tool_id: str, installed: bool) -> None:
        """Set the Install/Installed ✓ state for a tool button."""
        from textual.css.query import NoMatches
        try:
            btn = self.query_one(f"#install-{tool_id}", Button)
            if installed:
                btn.label = "Installed ✓"
                btn.disabled = True
                btn.variant = "success"
            else:
                btn.label = "Install"
                btn.disabled = False
                btn.variant = "primary"
        except NoMatches:
            pass

    # ── Event handlers ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id.startswith("install-"):
            tool_id = btn_id[len("install-"):]
            event.stop()
            self._install_tool(tool_id)

    # ── Install worker ────────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _install_tool(self, tool_id: str) -> None:
        """Run the install steps for ``tool_id``, streaming progress to OpsBar."""
        from bluefinctl.core.devmode import TOOL_NAMES, get_install_steps

        ops  = self.query_one(OpsBar)
        name = TOOL_NAMES.get(tool_id, tool_id)
        ops.set_running(f"Installing {name}…")

        # Disable the button immediately so double-clicks are ignored
        self._update_tool_button(tool_id, False)
        try:
            btn = self.query_one(f"#install-{tool_id}", Button)
            btn.disabled = True
        except Exception:  # noqa: BLE001
            pass

        try:
            cur_step = 0
            cur_total = 0
            async for update in get_install_steps(tool_id):
                if update.step is not None:
                    cur_step = update.step
                if update.total_steps is not None:
                    cur_total = update.total_steps
                if update.step and update.total_steps:
                    ops.set_running(
                        update.message,
                        step=update.step,
                        total=update.total_steps,
                    )
                elif update.message:
                    ops.set_running(update.message, step=cur_step, total=cur_total)

            ops.set_complete(f"✓  {name} installed")
            ops.add_completed(name)
            self._update_tool_button(tool_id, True)
            system_notify(f"{name} installed", "Ready to use")

        except Exception as exc:  # noqa: BLE001
            ops.set_error(f"✗  Failed — {exc}")
            # Re-enable the button so the user can retry
            self._update_tool_button(tool_id, False)
            system_notify(f"{name} install failed", str(exc), urgency="critical")
