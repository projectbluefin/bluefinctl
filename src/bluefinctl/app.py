"""Main Textual application for bluefinctl.

Five-screen navigation:
  System   — identity, hardware, health, quick actions (bootc systems only)
  Updates  — update strategy, focus mode, channel, rollback (bootc systems only)
  Toolkit  — kit management, package install via Command Palette
  DevMode  — developer tools, environments, Lima
  AI       — GPU-accelerated AI stack management
"""

from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from bluefinctl.theme.accent import get_accent_color


def _is_bootc_system() -> bool:
    """Detect whether we're running on a bootc/Universal Blue system."""
    import os
    import subprocess

    if os.path.exists("/run/ostree-booted"):
        return True
    try:
        result = subprocess.run(
            ["bootc", "status", "--json"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


class BluefinCtl(App[None]):
    """Bluefin OS control panel."""

    TITLE = "bluefinctl"

    CSS_PATH = "theme/bluefin.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("ctrl+p", "command_palette", "Commands"),
        Binding("1", "goto('screen1')", "Screen 1", show=False),
        Binding("2", "goto('screen2')", "Screen 2", show=False),
        Binding("3", "goto('screen3')", "Screen 3", show=False),
        Binding("4", "goto('screen4')", "Screen 4", show=False),
        Binding("5", "goto('screen5')", "Screen 5", show=False),
    ]

    def __init__(self, start_screen: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._start_screen = start_screen
        self._accent_color = get_accent_color()
        self._is_bootc = _is_bootc_system()
        # Screen name -> number key mapping, set in on_mount
        self._screen_keys: dict[str, str] = {}

    def on_mount(self) -> None:
        from textual.theme import Theme

        from bluefinctl.screens.ai import AIScreen
        from bluefinctl.screens.devmode import DevModeScreen
        from bluefinctl.screens.toolkit import ToolkitScreen
        from bluefinctl.theme.accent import get_accent_hex

        # Register dynamic theme with GNOME accent color
        accent = get_accent_hex()
        self.register_theme(Theme(
            name='bluefin',
            primary=accent,
            accent=accent,
            background='#1a1a2e',
            surface='#16213e',
            panel='#1f3460',
            error='#f44336',
            warning='#ff9800',
            success='#4caf50',
            dark=True,
        ))
        self.theme = 'bluefin'

        # Build screen list based on platform detection
        key_num = 1
        if self._is_bootc:
            from bluefinctl.screens.system import SystemScreen
            from bluefinctl.screens.updates import UpdatesScreen

            self.install_screen(SystemScreen(), name='system')
            self._screen_keys[f'screen{key_num}'] = 'system'
            key_num += 1

            self.install_screen(UpdatesScreen(), name='updates')
            self._screen_keys[f'screen{key_num}'] = 'updates'
            key_num += 1

        self.install_screen(ToolkitScreen(), name='toolkit')
        self._screen_keys[f'screen{key_num}'] = 'toolkit'
        key_num += 1

        self.install_screen(DevModeScreen(), name='devmode')
        self._screen_keys[f'screen{key_num}'] = 'devmode'
        key_num += 1

        self.install_screen(AIScreen(), name='ai')
        self._screen_keys[f'screen{key_num}'] = 'ai'

        # Determine start screen
        if self._start_screen:
            start = self._start_screen
        elif self._is_bootc:
            start = 'system'
        else:
            start = 'toolkit'

        self.push_screen(start)

    def compose(self) -> ComposeResult:
        """App chrome — header with system identity."""
        yield Header(show_clock=True)
        yield Footer()

    @property
    def is_bootc(self) -> bool:
        """Whether this is a bootc/Universal Blue system."""
        return self._is_bootc

    def get_screen_names(self) -> list[str]:
        """Return ordered list of active screen names."""
        return [self._screen_keys[k] for k in sorted(self._screen_keys.keys())]

    def action_goto(self, screen: str) -> None:
        """Switch to a named screen.

        Accepts both 'screenN' (key binding) and direct names like 'system'.
        """
        # Resolve 'screenN' keys to actual screen names
        if screen in self._screen_keys:
            screen = self._screen_keys[screen]
        self.switch_screen(screen)

    def action_help(self) -> None:
        from bluefinctl.screens._modals import HelpModal
        self.push_screen(HelpModal())
