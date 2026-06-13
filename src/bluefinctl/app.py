"""Main Textual application for bluefinctl.

Five-panel navigation:
  System   — identity, hardware, devmode, health
  Bundles  — curated loadout collections (the hero screen)
  Packages — individual brew/cask additions
  Updates  — uupd strategy, focus mode, channel
  Containers — podman pod status
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from bluefinctl.theme.accent import get_accent_color


class BluefinCtl(App):
    """Bluefin OS control panel."""

    TITLE = "bluefinctl"

    CSS_PATH = "theme/bluefin.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("1", "goto('system')", "System", show=False),
        Binding("2", "goto('bundles')", "Bundles", show=False),
        Binding("3", "goto('packages')", "Packages", show=False),
        Binding("4", "goto('updates')", "Updates", show=False),
        Binding("5", "goto('containers')", "Containers", show=False),
    ]

    def __init__(self, start_screen: str = "system", **kwargs) -> None:
        super().__init__(**kwargs)
        self._start_screen = start_screen
        self._accent_color = get_accent_color()

    def on_mount(self) -> None:
        """Apply accent color and show start screen."""
        # Import screens lazily to avoid circular imports
        from bluefinctl.screens.bundles import BundlesScreen
        from bluefinctl.screens.containers import ContainersScreen
        from bluefinctl.screens.packages import PackagesScreen
        from bluefinctl.screens.system import SystemScreen
        from bluefinctl.screens.updates import UpdatesScreen

        self.install_screen(SystemScreen(), name="system")
        self.install_screen(BundlesScreen(), name="bundles")
        self.install_screen(PackagesScreen(), name="packages")
        self.install_screen(UpdatesScreen(), name="updates")
        self.install_screen(ContainersScreen(), name="containers")

        self.push_screen(self._start_screen)

    def compose(self) -> ComposeResult:
        """App chrome — header with system identity."""
        yield Header(show_clock=True)
        yield Footer()

    def action_goto(self, screen: str) -> None:
        """Switch to a named screen."""
        self.switch_screen(screen)
