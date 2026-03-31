"""Settings screen — theme and UI configuration."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label, OptionList
from textual.widgets.option_list import Option

from cadre.config import CadreConfig


class SettingsScreen(ModalScreen[CadreConfig | None]):
    """Modal for TUI settings — theme and display options."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-container {
        width: 48;
        height: 22;
        background: #1e1e2e;
        border: thick #313244;
        padding: 1 2;
    }

    #settings-title {
        text-style: bold;
        color: #89b4fa;
        margin-bottom: 1;
    }

    .field-label {
        color: #6c7086;
        margin-top: 1;
    }

    #theme-list {
        height: 8;
        margin-bottom: 1;
    }

    #button-row {
        height: 3;
        align: right middle;
        dock: bottom;
    }

    Button {
        margin-left: 1;
    }
    """

    def __init__(
        self,
        config: CadreConfig,
        available_themes: list[str],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.available_themes = available_themes

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("Settings", id="settings-title")

            yield Label("Theme", classes="field-label")
            options = [Option(name, id=name) for name in self.available_themes]
            yield OptionList(*options, id="theme-list")

            yield Checkbox(
                "Show sidebar",
                value=self.config.ui.sidebar_visible,
                id="ui-sidebar-visible",
            )

            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("Apply", variant="primary", id="apply-btn")

    def on_mount(self) -> None:
        option_list = self.query_one("#theme-list", OptionList)
        for i, name in enumerate(self.available_themes):
            if name == self.config.ui.theme:
                option_list.highlighted = i
                break

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply-btn":
            self._apply_and_dismiss()
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _apply_and_dismiss(self) -> None:
        import contextlib

        # Theme
        theme_list = self.query_one("#theme-list", OptionList)
        highlighted = theme_list.highlighted
        if highlighted is not None and 0 <= highlighted < len(self.available_themes):
            self.config.ui.theme = self.available_themes[highlighted]

        # Sidebar
        with contextlib.suppress(Exception):
            self.config.ui.sidebar_visible = self.query_one("#ui-sidebar-visible", Checkbox).value

        self.dismiss(self.config)
