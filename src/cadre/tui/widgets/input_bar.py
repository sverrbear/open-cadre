"""Input bar widget — text input with @mention autocomplete and slash commands."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Input


class AgentSuggester(Suggester):
    """Suggests @agent mentions and /slash commands."""

    def __init__(self, agent_names: list[str]) -> None:
        super().__init__(use_cache=False, case_sensitive=False)
        self.agent_names = agent_names
        self.slash_commands = [
            "/help",
            "/status",
            "/settings",
            "/quit",
        ]

    async def get_suggestion(self, value: str) -> str | None:
        """Provide completion suggestions."""
        if value.startswith("@"):
            prefix = value[1:].lower()
            for name in self.agent_names:
                if name.lower().startswith(prefix):
                    return f"@{name} "
        elif value.startswith("/"):
            prefix = value.lower()
            for cmd in self.slash_commands:
                if cmd.startswith(prefix) and cmd != prefix:
                    return cmd
        return None


class InputBar(Widget):
    """Bottom input bar for typing messages and commands."""

    class Submitted(Message):
        """Posted when the user submits a message."""

        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def __init__(self, agent_names: list[str] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_names = agent_names or []

    def compose(self) -> ComposeResult:
        suggester = AgentSuggester(self.agent_names) if self.agent_names else None
        yield Input(
            placeholder="Message your team... (@agent to direct, /help for commands)",
            suggester=suggester,
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Forward input submission as our own message."""
        value = event.value.strip()
        if value:
            self.post_message(self.Submitted(value))
            event.input.clear()

    def focus_input(self) -> None:
        """Focus the text input."""
        self.query_one(Input).focus()
