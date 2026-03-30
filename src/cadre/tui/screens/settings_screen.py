"""Settings screen — theme selection and layout configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList, Static
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from cadre.config import UIConfig


class SettingsScreen(ModalScreen[str | None]):
    """Modal screen for TUI settings — theme selection and layout toggles."""

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-container {
        width: 60;
        height: 24;
        background: #1e1e2e;
        border: thick #313244;
        padding: 1 2;
    }

    #settings-title {
        text-style: bold;
        color: #89b4fa;
        margin-bottom: 1;
    }

    #theme-section {
        height: auto;
        margin-bottom: 1;
    }

    #theme-label {
        margin-bottom: 1;
        text-style: bold;
    }

    OptionList {
        height: 8;
        background: #313244;
        border: tall #45475a;
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

    def __init__(self, ui_config: UIConfig, available_themes: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self.ui_config = ui_config
        self.available_themes = available_themes
        self.selected_theme = ui_config.theme

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("Settings", id="settings-title")

            with Vertical(id="theme-section"):
                yield Label("Theme", id="theme-label")
                options = [Option(name, id=name) for name in self.available_themes]
                yield OptionList(*options, id="theme-list")

            yield Static(
                "[dim]Shortcuts: ctrl+b toggle sidebar, ctrl+t toggle tools[/dim]",
            )

            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("Apply", variant="primary", id="apply-btn")

    def on_mount(self) -> None:
        """Highlight the current theme."""
        option_list = self.query_one("#theme-list", OptionList)
        for i, name in enumerate(self.available_themes):
            if name == self.selected_theme:
                option_list.highlighted = i
                break

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Track theme selection."""
        if event.option.id:
            self.selected_theme = str(event.option.id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "apply-btn":
            self.dismiss(self.selected_theme)
        else:
            self.dismiss(None)
