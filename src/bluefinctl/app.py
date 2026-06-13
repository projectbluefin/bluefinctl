"""Main Textual application for bluefinctl."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from bluefinctl.screens.dashboard import DashboardScreen
from bluefinctl.theme.accent import get_accent_color


class BluefinCtl(App):
    """Bluefin OS control panel."""

    TITLE = "bluefinctl"
    SUB_TITLE = "Bluefin Control Panel"

    CSS_PATH = "theme/bluefin.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("d", "switch_screen('dashboard')", "Dashboard", show=False),
        Binding("b", "switch_screen('brew')", "Brew", show=False),
        Binding("u", "switch_screen('updates')", "Updates", show=False),
        Binding("c", "switch_screen('containers')", "Containers", show=False),
        Binding("s", "switch_screen('settings')", "Settings", show=False),
    ]

    SCREENS = {
        "dashboard": DashboardScreen,
    }

    def __init__(self, start_screen: str = "dashboard", **kwargs) -> None:
        super().__init__(**kwargs)
        self._start_screen = start_screen
        self._accent_color = get_accent_color()

    def on_mount(self) -> None:
        """Apply accent color and show start screen."""
        if self._accent_color:
            self.app.set_class(True, f"accent-{self._accent_color}")

        self.push_screen(self._start_screen)

    def compose(self) -> ComposeResult:
        """Create the app chrome."""
        yield Header(show_clock=True)
        yield Footer()
