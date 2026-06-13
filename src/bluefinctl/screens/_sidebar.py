"""Shared sidebar navigation widget."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, Static

NAV_ITEMS = [
    ('1', 'system', 'System'),
    ('2', 'bundles', 'Bundles'),
    ('3', 'packages', 'Packages'),
    ('4', 'updates', 'Updates'),
    ('5', 'containers', 'Containers'),
]


class NavItem(Static):
    """A clickable sidebar navigation item."""

    DEFAULT_CSS = """
    NavItem {
        height: 3;
        padding: 0 2;
        content-align: left middle;
    }
    NavItem:hover { background: $panel; }
    NavItem.-active {
        background: $accent 20%;
        border-left: thick $accent;
        text-style: bold;
    }
    """

    def __init__(self, key: str, slug: str, name: str, active: bool = False) -> None:
        super().__init__()
        self._key = key
        self._slug = slug
        self._name = name
        self._active = active
        if active:
            self.add_class('-active')

    def render(self) -> str:
        indicator = '*' if self._active else ' '
        return f' {indicator} [{self._key}] {self._name}'

    def on_click(self) -> None:
        self.app.action_goto(self._slug)


class Sidebar(Static):
    """Left navigation sidebar."""

    DEFAULT_CSS = """
    Sidebar {
        width: 22;
        background: $surface;
        border-right: thick $panel;
        padding: 1 0;
    }
    #sidebar-title {
        padding: 1 2;
        color: $accent;
        text-style: bold;
    }
    """

    def __init__(self, active: str = 'system') -> None:
        super().__init__()
        self._active = active

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(' bluefinctl', id='sidebar-title')
            yield Label('', id='sidebar-spacer')
            for key, slug, name in NAV_ITEMS:
                yield NavItem(key, slug, name, active=(slug == self._active))
