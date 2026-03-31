"""Reusable confirmation dialog modal."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmDialog(ModalScreen[bool | None]):
    """Simple yes/no confirmation dialog."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }

    #confirm-container {
        width: 50;
        height: 10;
        background: #1e1e2e;
        border: thick #313244;
        padding: 1 2;
    }

    #confirm-title {
        text-style: bold;
        color: #f38ba8;
        text-align: center;
        margin-bottom: 1;
    }

    #confirm-message {
        color: #cdd6f4;
        text-align: center;
        margin-bottom: 1;
    }

    #confirm-buttons {
        height: 3;
        align: right middle;
        dock: bottom;
    }

    #confirm-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(
        self,
        message: str,
        title: str = "Confirm",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-container"):
            yield Label(self._title, id="confirm-title")
            yield Label(self._message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button("Cancel", variant="default", id="confirm-cancel-btn")
                yield Button("Delete", variant="error", id="confirm-delete-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-cancel-btn":
            self.dismiss(None)
        elif event.button.id == "confirm-delete-btn":
            self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(None)
