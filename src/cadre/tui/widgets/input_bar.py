"""Input bar widget — text input with @mention autocomplete and slash command menu."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

SLASH_COMMANDS = {
    "/help": "Show available commands",
    "/init": "Initialize or reconfigure project",
    "/status": "Show team status",
    "/settings": "Open settings panel",
    "/config": "Open settings panel",
    "/models": "Show configured models",
    "/doctor": "Check prerequisites",
    "/workflow": "Show workflows",
    "/quit": "Exit OpenCadre",
}


class AgentSuggester(Suggester):
    """Suggests @agent mentions (inline ghost text)."""

    def __init__(self, agent_names: list[str]) -> None:
        super().__init__(use_cache=False, case_sensitive=False)
        self.agent_names = agent_names

    async def get_suggestion(self, value: str) -> str | None:
        """Provide completion suggestions for @mentions only."""
        if value.startswith("@"):
            prefix = value[1:].lower()
            for name in self.agent_names:
                if name.lower().startswith(prefix):
                    return f"@{name} "
        return None


class CommandMenu(Static):
    """Popup menu showing slash commands above the input bar."""

    DEFAULT_CSS = """
    CommandMenu {
        dock: bottom;
        layer: overlay;
        height: auto;
        max-height: 14;
        width: 50;
        margin-bottom: 3;
        margin-left: 1;
        background: #313244;
        border: tall #45475a;
        padding: 0 1;
        display: none;
    }

    CommandMenu OptionList {
        height: auto;
        max-height: 12;
        background: #313244;
        border: none;
    }

    CommandMenu OptionList:focus {
        border: none;
    }

    CommandMenu OptionList > .option-list--option-highlighted {
        background: #45475a;
    }
    """

    class CommandSelected(Message):
        """Posted when a command is selected from the menu."""

        def __init__(self, command: str) -> None:
            super().__init__()
            self.command = command

    def compose(self) -> ComposeResult:
        options = [
            Option(f"{cmd:12s} [dim]{desc}[/dim]", id=cmd) for cmd, desc in SLASH_COMMANDS.items()
        ]
        yield OptionList(*options, id="cmd-list")

    def show_filtered(self, prefix: str) -> None:
        """Show the menu filtered by prefix, or hide if no matches."""
        option_list = self.query_one("#cmd-list", OptionList)
        option_list.clear_options()

        matches = [
            (cmd, desc) for cmd, desc in SLASH_COMMANDS.items() if cmd.startswith(prefix.lower())
        ]

        if not matches:
            self.display = False
            return

        for cmd, desc in matches:
            option_list.add_option(Option(f"{cmd:12s} [dim]{desc}[/dim]", id=cmd))

        option_list.highlighted = 0
        self.display = True

    def hide(self) -> None:
        self.display = False

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """When user clicks or presses enter on a command."""
        if event.option.id:
            self.post_message(self.CommandSelected(str(event.option.id)))
        self.hide()


class InputBar(Widget):
    """Bottom input bar for typing messages and commands."""

    DEFAULT_CSS = """
    InputBar {
        layout: vertical;
        height: auto;
    }
    """

    class Submitted(Message):
        """Posted when the user submits a message."""

        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def __init__(self, agent_names: list[str] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_names = agent_names or []

    def compose(self) -> ComposeResult:
        yield CommandMenu()
        suggester = AgentSuggester(self.agent_names) if self.agent_names else None
        yield Input(
            placeholder="Message your team... (@agent to direct, / for commands)",
            suggester=suggester,
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Show/hide command menu as user types."""
        menu = self.query_one(CommandMenu)
        value = event.value.strip()
        if value.startswith("/"):
            menu.show_filtered(value)
        else:
            menu.hide()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Forward input submission as our own message."""
        value = event.value.strip()
        if value:
            self.query_one(CommandMenu).hide()
            self.post_message(self.Submitted(value))
            event.input.clear()

    def on_command_menu_command_selected(self, event: CommandMenu.CommandSelected) -> None:
        """When a command is picked from the menu, submit it."""
        self.query_one(CommandMenu).hide()
        self.post_message(self.Submitted(event.command))
        self.query_one(Input).clear()

    def focus_input(self) -> None:
        """Focus the text input."""
        self.query_one(Input).focus()
