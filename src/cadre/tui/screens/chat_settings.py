"""Chat session settings modal for configuring Claude Code launch options."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label, Select

PERMISSION_MODES = [
    ("Default", ""),
    ("Plan", "plan"),
    ("Auto", "auto"),
    ("Accept Edits", "acceptEdits"),
    ("Bypass Permissions", "bypassPermissions"),
]

MODELS = [
    ("Default (inherit)", ""),
    ("Opus", "opus"),
    ("Sonnet", "sonnet"),
    ("Haiku", "haiku"),
]

EFFORT_OPTIONS = [
    ("Default", ""),
    ("Low", "low"),
    ("Medium", "medium"),
    ("High", "high"),
    ("Max", "max"),
]


@dataclass
class ChatSessionSettings:
    """Settings for a Claude Code chat session."""

    permission_mode: str = ""
    model: str = ""
    effort: str = "medium"
    skip_permissions: bool = False


class ChatSettingsModal(ModalScreen[ChatSessionSettings | None]):
    """Modal for configuring Claude Code session settings."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    ChatSettingsModal {
        align: center middle;
    }

    #settings-container {
        width: 60;
        height: auto;
        max-height: 28;
        background: #1e1e2e;
        border: thick #313244;
        padding: 1 2;
    }

    #settings-title {
        text-style: bold;
        color: #89b4fa;
        text-align: center;
        margin-bottom: 1;
    }

    .settings-field {
        height: auto;
        margin-bottom: 1;
    }

    .settings-label {
        color: #cdd6f4;
        margin-bottom: 0;
    }

    #skip-permissions-warning {
        color: #f38ba8;
        display: none;
    }

    #settings-buttons {
        height: 3;
        align: right middle;
        dock: bottom;
    }

    #settings-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(self, settings: ChatSessionSettings | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._settings = settings or ChatSessionSettings()

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("Session Settings", id="settings-title")

            with Vertical(classes="settings-field"):
                yield Label("Permission Mode", classes="settings-label")
                yield Select(
                    PERMISSION_MODES,
                    value=self._settings.permission_mode,
                    id="permission-mode-select",
                )

            with Vertical(classes="settings-field"):
                yield Label("Model", classes="settings-label")
                yield Select(
                    MODELS,
                    value=self._settings.model,
                    id="model-select",
                )

            with Vertical(classes="settings-field"):
                yield Label("Effort", classes="settings-label")
                yield Select(
                    EFFORT_OPTIONS,
                    value=self._settings.effort,
                    id="effort-select",
                )

            with Vertical(classes="settings-field"):
                yield Checkbox(
                    "Dangerously skip permissions",
                    value=self._settings.skip_permissions,
                    id="skip-permissions-check",
                )
                yield Label(
                    "Warning: Bypasses all safety checks. Use with caution.",
                    id="skip-permissions-warning",
                )

            with Horizontal(id="settings-buttons"):
                yield Button("Cancel", variant="default", id="settings-cancel-btn")
                yield Button("Apply", variant="primary", id="settings-apply-btn")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "skip-permissions-check":
            warning = self.query_one("#skip-permissions-warning", Label)
            warning.display = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-cancel-btn":
            self.dismiss(None)
        elif event.button.id == "settings-apply-btn":
            self._apply()

    def _apply(self) -> None:
        permission_mode = self.query_one("#permission-mode-select", Select).value
        model = self.query_one("#model-select", Select).value
        effort = self.query_one("#effort-select", Select).value
        skip_permissions = self.query_one("#skip-permissions-check", Checkbox).value

        result = ChatSessionSettings(
            permission_mode=permission_mode if isinstance(permission_mode, str) else "",
            model=model if isinstance(model, str) else "",
            effort=effort if isinstance(effort, str) else "",
            skip_permissions=skip_permissions,
        )
        self.dismiss(result)

    def action_cancel(self) -> None:
        self.dismiss(None)
