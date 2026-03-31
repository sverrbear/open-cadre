"""Permission request dialog for Claude Code tool approval."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class PermissionDialog(ModalScreen[bool]):
    """Modal dialog showing a tool permission request from Claude."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "deny", "Deny"),
        Binding("enter", "allow", "Allow"),
    ]

    DEFAULT_CSS = """
    PermissionDialog {
        align: center middle;
    }

    #perm-container {
        width: 70;
        height: auto;
        max-height: 24;
        background: #1e1e2e;
        border: thick #f9e2af;
        padding: 1 2;
    }

    #perm-title {
        text-style: bold;
        color: #f9e2af;
        text-align: center;
        margin-bottom: 1;
    }

    #perm-tool-label {
        color: #89b4fa;
        text-style: bold;
        margin-bottom: 1;
    }

    #perm-detail {
        color: #cdd6f4;
        background: #313244;
        padding: 1 2;
        margin-bottom: 1;
        max-height: 10;
        overflow-y: auto;
    }

    #perm-reason {
        color: #6c7086;
        text-style: italic;
        margin-bottom: 1;
    }

    #perm-buttons {
        height: 3;
        align: center middle;
    }

    #perm-buttons Button {
        margin: 0 1;
    }

    #perm-hint {
        color: #6c7086;
        text-align: center;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        tool_name: str,
        tool_input: dict | str,
        reason: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._tool_name = tool_name
        self._tool_input = tool_input
        self._reason = reason

    def compose(self) -> ComposeResult:
        detail = self._format_tool_input()

        with Vertical(id="perm-container"):
            yield Label("Claude wants to use a tool", id="perm-title")
            yield Label(f"Tool: {self._tool_name}", id="perm-tool-label")
            yield Static(detail, id="perm-detail")
            if self._reason:
                yield Label(f"Reason: {self._reason}", id="perm-reason")
            with Horizontal(id="perm-buttons"):
                yield Button("Deny", variant="error", id="perm-deny-btn")
                yield Button("Allow", variant="success", id="perm-allow-btn")
            yield Label("Enter to allow, Escape to deny", id="perm-hint")

    def _format_tool_input(self) -> str:
        """Format tool input for display."""
        if isinstance(self._tool_input, str):
            return self._tool_input

        if isinstance(self._tool_input, dict):
            # Special formatting for common tools
            if self._tool_name == "Bash" and "command" in self._tool_input:
                return f"$ {self._tool_input['command']}"
            if self._tool_name == "Write" and "file_path" in self._tool_input:
                content = self._tool_input.get("content", "")
                preview = content[:300] + "..." if len(content) > 300 else content
                return f"File: {self._tool_input['file_path']}\n{preview}"
            if self._tool_name == "Edit" and "file_path" in self._tool_input:
                old = self._tool_input.get("old_string", "")[:150]
                new = self._tool_input.get("new_string", "")[:150]
                return f"File: {self._tool_input['file_path']}\nReplace: {old}\nWith: {new}"
            if self._tool_name == "Read" and "file_path" in self._tool_input:
                return f"File: {self._tool_input['file_path']}"

            # Generic: show key=value pairs
            lines = []
            for key, val in self._tool_input.items():
                val_str = str(val)
                if len(val_str) > 200:
                    val_str = val_str[:200] + "..."
                lines.append(f"{key}: {val_str}")
            return "\n".join(lines)

        return str(self._tool_input)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "perm-allow-btn":
            self.dismiss(True)
        elif event.button.id == "perm-deny-btn":
            self.dismiss(False)

    def action_allow(self) -> None:
        self.dismiss(True)

    def action_deny(self) -> None:
        self.dismiss(False)
