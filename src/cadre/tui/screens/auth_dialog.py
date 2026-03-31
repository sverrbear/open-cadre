"""Authentication required dialog."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class AuthRequiredDialog(ModalScreen[None]):
    """Modal shown when Claude Code authentication is missing."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss_dialog", "Close"),
    ]

    DEFAULT_CSS = """
    AuthRequiredDialog {
        align: center middle;
    }

    #auth-container {
        width: 60;
        height: auto;
        max-height: 14;
        background: #1e1e2e;
        border: thick #313244;
        padding: 1 2;
    }

    #auth-title {
        text-style: bold;
        color: #f38ba8;
        text-align: center;
        margin-bottom: 1;
    }

    #auth-message {
        color: #cdd6f4;
        margin-bottom: 1;
    }

    #auth-hint {
        color: #a6adc8;
        margin-bottom: 1;
    }

    #auth-buttons {
        height: 3;
        align: center middle;
        dock: bottom;
    }
    """

    def __init__(self, error: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._error = error

    def compose(self) -> ComposeResult:
        with Vertical(id="auth-container"):
            yield Label("Authentication Required", id="auth-title")
            yield Label(
                self._error or "You are not logged in to Claude Code.",
                id="auth-message",
            )
            yield Label(
                "Run [bold]claude auth login[/bold] in your terminal, then try again.",
                id="auth-hint",
            )
            with Horizontal(id="auth-buttons"):
                yield Button("OK", variant="primary", id="auth-ok-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "auth-ok-btn":
            self.dismiss(None)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)
