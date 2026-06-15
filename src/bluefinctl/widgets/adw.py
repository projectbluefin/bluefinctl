"""GNOME libadwaita-inspired TUI widgets for bluefinctl.

Implements the HIG boxed-list pattern as Textual widgets so every screen
feels like a GTK4/libadwaita preferences page.

Widgets:
    AdwPreferencesGroup  — bordered group with optional muted heading above
    AdwActionRow         — title + subtitle (left) + trailing widget (right)
    AdwSwitchRow         — AdwActionRow with Switch trailing
    AdwComboRow          — AdwActionRow with cycling value (chevron-style)
    AdwButtonRow         — full-width clickable row (primary/warning/destructive)
    AdwPropertyRow       — read-only: key (muted left) + value (bold right)
    AdwExpanderRow       — AdwActionRow that reveals/hides child rows

HIG rules implemented:
    - Heading is ABOVE the boxed group, not inside it
    - One control per row (max two per HIG)
    - Row separators between items, not borders on each row
    - Hover and focus-within highlight
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Label, Rule


class _CheckToggle(Widget):
    """Compact checkbox replacement for Textual's Switch.

    Renders as ``[✓]`` (on) or ``[ ]`` (off) at exactly height 1.
    Textual's built-in Switch uses ``border: tall`` which forces 3 rows —
    this widget keeps the row height to 1 or 2 (with subtitle).

    Messages: fires the parent AdwSwitchRow.Changed, not its own message.
    """

    DEFAULT_CSS = """
    _CheckToggle {
        width: 5;
        height: 1;
        content-align: center middle;
        background: transparent;
    }
    _CheckToggle:hover { color: $accent; }
    _CheckToggle.-on    { color: $accent; text-style: bold; }
    """

    def __init__(self, value: bool = False, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._value = value
        if value:
            self.add_class("-on")

    def render(self) -> str:
        return "[✓]" if self._value else "[ ]"

    def on_click(self) -> None:
        self._value = not self._value
        if self._value:
            self.add_class("-on")
        else:
            self.remove_class("-on")
        self.refresh()
        # Walk up to the owning AdwSwitchRow and emit Changed
        row = self.parent
        while row is not None and not isinstance(row, AdwSwitchRow):
            row = getattr(row, "parent", None)
        if isinstance(row, AdwSwitchRow):
            row.post_message(AdwSwitchRow.Changed(row, self._value))

    @property
    def value(self) -> bool:
        return self._value

    @value.setter
    def value(self, v: bool) -> None:
        self._value = v
        if v:
            self.add_class("-on")
        else:
            self.remove_class("-on")
        self.refresh()


class AdwPreferencesGroup(Vertical):
    """A bordered preferences group with optional muted heading above the box.

    Usage::

        yield AdwPreferencesGroup(
            "Update Layers",
            AdwSwitchRow("OS Image", subtitle="Include bootc image updates", id="layer-os"),
            AdwSwitchRow("Flatpaks", subtitle="Include Flatpak app updates", id="layer-flatpak"),
        )
    """

    DEFAULT_CSS = """
    AdwPreferencesGroup {
        height: auto;
        margin-bottom: 1;
    }
    AdwPreferencesGroup > .adw-group-title {
        color: $text-muted;
        padding: 0 1;
        height: 1;
    }
    AdwPreferencesGroup > .adw-group-box {
        border: round $panel;
        background: $surface;
        height: auto;
    }
    Rule.adw-separator {
        color: $panel;
        height: 1;
    }
    """

    def __init__(
        self,
        title: str = "",
        *rows: Widget,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._group_title = title
        self._rows = list(rows)

    def compose(self) -> ComposeResult:
        if self._group_title:
            yield Label(self._group_title, classes="adw-group-title")
        with Vertical(classes="adw-group-box"):
            for i, row in enumerate(self._rows):
                yield row
                if i < len(self._rows) - 1:
                    yield Rule(classes="adw-separator")


class AdwActionRow(Horizontal):
    """Title + subtitle (left) + optional trailing widget (right).

    The entire row is hoverable; subclasses add click behaviour.
    Post ``AdwActionRow.Pressed`` if no specific subclass behaviour applies.
    """

    class Pressed(Message):
        """Fired when the row is clicked (generic — use typed subclasses for controls)."""

        def __init__(self, row: AdwActionRow) -> None:
            super().__init__()
            self.row = row

    DEFAULT_CSS = """
    AdwActionRow {
        height: auto;
        min-height: 2;
        background: $surface;
        padding: 0 1;
        align: left middle;
    }
    AdwActionRow:hover { background: $panel; }
    AdwActionRow:focus-within { background: $boost 5%; }
    AdwActionRow > .adw-row-content {
        width: 1fr;
        height: auto;
        min-height: 2;
        content-align: left middle;
        padding: 0;
    }
    AdwActionRow > .adw-row-trailing {
        width: auto;
        min-height: 2;
        content-align: right middle;
        align: right middle;
        padding: 0 0;
    }
    AdwActionRow > .adw-row-content > .adw-row-title {
        text-style: bold;
        width: 1fr;
    }
    AdwActionRow > .adw-row-content > .adw-row-subtitle {
        color: $text-muted;
        width: 1fr;
    }
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        trailing: Widget | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._row_title = title
        self._row_subtitle = subtitle
        self._trailing = trailing

    def compose(self) -> ComposeResult:
        with Vertical(classes="adw-row-content"):
            yield Label(self._row_title, classes="adw-row-title")
            if self._row_subtitle:
                yield Label(self._row_subtitle, classes="adw-row-subtitle")
        if self._trailing is not None:
            with Vertical(classes="adw-row-trailing"):
                yield self._trailing

    def on_click(self) -> None:
        self.post_message(AdwActionRow.Pressed(self))


class AdwSwitchRow(Horizontal):
    """AdwActionRow with a compact checkbox toggle on the right.

    Uses ``_CheckToggle`` (renders ``[\u2713]``/``[ ]`` at height 1) instead of
    Textual's built-in ``Switch`` which forces 3 rows via ``border: tall``.

    Messages:
        AdwSwitchRow.Changed: value changed (row, value).
    """

    class Changed(Message):
        def __init__(self, row: AdwSwitchRow, value: bool) -> None:
            super().__init__()
            self.row = row
            self.value = value

    DEFAULT_CSS = """
    AdwSwitchRow {
        height: 1;
        min-height: 1;
        background: $surface;
        padding: 0 1;
        align: left middle;
    }
    AdwSwitchRow:hover { background: $panel; }
    AdwSwitchRow > .adw-row-content {
        width: 1fr;
        height: 1;
        content-align: left middle;
    }
    AdwSwitchRow > .adw-row-trailing {
        width: 5;
        height: 1;
        align: right middle;
        content-align: right middle;
    }
    AdwSwitchRow > .adw-row-content > .adw-row-title {
        text-style: bold;
        width: 1fr;
        height: 1;
    }
    AdwSwitchRow > .adw-row-content > .adw-row-subtitle {
        color: $text-muted;
        width: 1fr;
        height: 1;
    }
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        value: bool = False,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._row_title = title
        self._row_subtitle = subtitle
        self._initial_value = value

    def compose(self) -> ComposeResult:
        with Vertical(classes="adw-row-content"):
            yield Label(self._row_title, classes="adw-row-title")
            if self._row_subtitle:
                yield Label(self._row_subtitle, classes="adw-row-subtitle")
        with Vertical(classes="adw-row-trailing"):
            yield _CheckToggle(value=self._initial_value, id=f"_ct_{self.id or id(self)}")

    def on_mount(self) -> None:
        if self._row_subtitle:
            self.styles.height = 2
            self.query_one(".adw-row-content").styles.height = 2
            self.query_one(".adw-row-trailing").styles.height = 2

    def set_value(self, value: bool) -> None:
        """Set value without firing Changed."""
        toggle = self.query_one(_CheckToggle)
        toggle._value = value
        if value:
            toggle.add_class("-on")
        else:
            toggle.remove_class("-on")
        toggle.refresh()

    @property
    def value(self) -> bool:
        try:
            return self.query_one(_CheckToggle).value
        except Exception:  # noqa: BLE001
            return self._initial_value


class AdwComboRow(Horizontal):
    """AdwActionRow with a cycling value label (chevron-style combo box).

    Displays the current value with a right chevron. Clicking cycles to the
    next choice; wraps around.

    Messages:
        AdwComboRow.Changed: Choice changed (row, value).
    """

    class Changed(Message):
        """Fired when the selected value changes."""

        def __init__(self, row: AdwComboRow, value: str) -> None:
            super().__init__()
            self.row = row
            self.value = value

    current_index: reactive[int] = reactive(0, init=False)

    DEFAULT_CSS = """
    AdwComboRow {
        height: auto;
        min-height: 2;
        background: $surface;
        padding: 0 1;
        align: left middle;
    }
    AdwComboRow:hover { background: $panel; }
    AdwComboRow > .adw-row-content {
        width: 1fr;
        height: auto;
        min-height: 2;
        content-align: left middle;
        padding: 0;
    }
    AdwComboRow > .adw-row-trailing {
        width: auto;
        min-height: 2;
        align: right middle;
        content-align: right middle;
    }
    AdwComboRow > .adw-row-content > .adw-row-title {
        text-style: bold;
        width: 1fr;
    }
    AdwComboRow > .adw-row-content > .adw-row-subtitle {
        color: $text-muted;
        width: 1fr;
    }
    AdwComboRow > .adw-row-trailing > #combo-value {
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        choices: list[str] | None = None,
        value: str = "",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._row_title = title
        self._row_subtitle = subtitle
        self._choices = choices or []
        self._current_index = 0
        if value and value in self._choices:
            self._current_index = self._choices.index(value)

    def compose(self) -> ComposeResult:
        with Vertical(classes="adw-row-content"):
            yield Label(self._row_title, classes="adw-row-title")
            if self._row_subtitle:
                yield Label(self._row_subtitle, classes="adw-row-subtitle")
        with Vertical(classes="adw-row-trailing"):
            display = self._choices[self._current_index] if self._choices else ""
            yield Label(f"{display}  ›", id="combo-value")

    def on_click(self) -> None:
        if not self._choices:
            return
        self._current_index = (self._current_index + 1) % len(self._choices)
        self.query_one("#combo-value", Label).update(
            f"{self._choices[self._current_index]}  ›"
        )
        self.post_message(AdwComboRow.Changed(self, self._choices[self._current_index]))

    def set_value(self, value: str) -> None:
        """Set the current value without firing a Changed event."""
        if value in self._choices:
            self._current_index = self._choices.index(value)
            try:
                self.query_one("#combo-value", Label).update(
                    f"{self._choices[self._current_index]}  ›"
                )
            except Exception:  # noqa: BLE001
                pass

    @property
    def value(self) -> str:
        """Currently selected value."""
        if not self._choices:
            return ""
        return self._choices[self._current_index]


class AdwButtonRow(Widget):
    """Full-width clickable row — acts as a suggestion/action button.

    Messages:
        AdwButtonRow.Pressed: Row was pressed.

    Variants:
        "default"     — plain text, surface background
        "primary"     — accent colored text
        "warning"     — warning colored text
        "destructive" — error colored text
    """

    class Pressed(Message):
        """Fired when the button row is pressed."""

        def __init__(self, row: AdwButtonRow) -> None:
            super().__init__()
            self.row = row

    DEFAULT_CSS = """
    AdwButtonRow {
        height: auto;
        min-height: 1;
        background: $surface;
        padding: 0 1;
        content-align: left middle;
    }
    AdwButtonRow:hover { background: $panel; }
    AdwButtonRow.-primary { color: $primary; text-style: bold; }
    AdwButtonRow.-destructive { color: $error; }
    AdwButtonRow.-warning { color: $warning; }
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        variant: str = "default",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._title = title
        self._subtitle = subtitle
        self._variant = variant
        if variant != "default":
            self.add_class(f"-{variant}")

    def update_title(self, title: str) -> None:
        """Update the displayed title text."""
        self._title = title
        self.refresh()

    def render(self) -> str:
        if self._subtitle:
            return f"{self._title}\n{self._subtitle}"
        return self._title

    def on_click(self) -> None:
        self.post_message(AdwButtonRow.Pressed(self))


class AdwPropertyRow(Horizontal):
    """Read-only row: key (muted, left) + value (bold, right).

    Usage::

        yield AdwPropertyRow("Current", "stable", id="channel-info")

        # Update value later:
        self.query_one("#channel-info", AdwPropertyRow).update_value("testing")
    """

    DEFAULT_CSS = """
    AdwPropertyRow {
        height: 1;
        background: $surface;
        padding: 0 1;
        align: left middle;
    }
    AdwPropertyRow > .adw-prop-key {
        color: $text-muted;
        width: 1fr;
        content-align: left middle;
    }
    AdwPropertyRow > .adw-prop-value {
        text-style: bold;
        width: 1fr;
        content-align: right middle;
    }
    """

    def __init__(
        self,
        key: str,
        value: str = "",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._key = key
        self._value = value

    def compose(self) -> ComposeResult:
        yield Label(self._key, classes="adw-prop-key")
        yield Label(self._value, classes="adw-prop-value")

    def update_value(self, value: str) -> None:
        """Update the displayed value."""
        self.query_one(".adw-prop-value", Label).update(value)


class AdwExpanderRow(Horizontal):
    """AdwActionRow that reveals or hides a set of child rows below it.

    Usage::

        expander = AdwExpanderRow("Advanced", subtitle="More options")
        expander.add_child_row(AdwSwitchRow("Option A"))
        expander.add_child_row(AdwSwitchRow("Option B"))
        yield expander
    """

    DEFAULT_CSS = """
    AdwExpanderRow {
        height: auto;
        min-height: 2;
        background: $surface;
        padding: 0 1;
        align: left middle;
    }
    AdwExpanderRow:hover { background: $panel; }
    AdwExpanderRow > .adw-row-content {
        width: 1fr;
        height: auto;
        min-height: 2;
        content-align: left middle;
        padding: 0;
    }
    AdwExpanderRow > .adw-row-trailing {
        width: 3;
        min-height: 2;
        align: right middle;
        content-align: right middle;
    }
    AdwExpanderRow > .adw-row-title {
        text-style: bold;
    }
    AdwExpanderRow > .adw-row-subtitle {
        color: $text-muted;
    }
    #adw-expander-children {
        height: auto;
        display: none;
    }
    #adw-expander-children.expanded {
        display: block;
    }
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._row_title = title
        self._row_subtitle = subtitle
        self._child_rows: list[Widget] = []
        self._expanded = False

    def add_child_row(self, row: Widget) -> None:
        """Add a child row (shown when expanded)."""
        self._child_rows.append(row)

    def compose(self) -> ComposeResult:
        with Vertical(classes="adw-row-content"):
            yield Label(self._row_title, classes="adw-row-title")
            if self._row_subtitle:
                yield Label(self._row_subtitle, classes="adw-row-subtitle")
        with Vertical(classes="adw-row-trailing"):
            yield Label("›", id="expander-chevron")

    def on_click(self) -> None:
        self._expanded = not self._expanded
        chevron = self.query_one("#expander-chevron", Label)
        chevron.update("⌄" if self._expanded else "›")
        try:
            children_container = self.query_one("#adw-expander-children")
            if self._expanded:
                children_container.add_class("expanded")
            else:
                children_container.remove_class("expanded")
        except Exception:  # noqa: BLE001
            pass

    @property
    def expanded(self) -> bool:
        """Whether the expander is open."""
        return self._expanded


class AdwButtonsRow(Horizontal):
    """A row containing real Textual Button widgets, side by side.

    Use for primary actions (Update Now, Check for Updates, etc.).
    Buttons are accent-coloured per their variant.

    Handle via ``on_button_pressed``, NOT ``on_adw_button_row_pressed``.

    Usage::

        yield AdwButtonsRow(
            Button("Update Now", variant="primary", id="btn-update"),
            Button("Check for Updates", id="btn-check"),
        )
    """

    DEFAULT_CSS = """
    AdwButtonsRow {
        height: 3;
        background: $surface;
        padding: 0 1;
        align: left middle;
    }
    AdwButtonsRow Button {
        margin-right: 1;
    }
    """

    def __init__(
        self,
        *buttons: Button,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._buttons = list(buttons)

    def compose(self) -> ComposeResult:
        yield from self._buttons


# Type alias for cleaner imports
__all__ = [
    "AdwActionRow",
    "AdwButtonRow",
    "AdwButtonsRow",
    "AdwComboRow",
    "AdwExpanderRow",
    "AdwPreferencesGroup",
    "AdwPropertyRow",
    "AdwSwitchRow",
]
