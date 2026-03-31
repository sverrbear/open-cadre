"""Main screen — agent dashboard with cards, actions, and log."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Label, RichLog, Static

from cadre.agents.manager import AgentInfo
from cadre.tui.widgets.header_bar import HeaderBar
from cadre.tui.widgets.status_sidebar import AgentSidebar

if TYPE_CHECKING:
    from cadre.config import CadreConfig


class AgentCard(Static):
    """Visual card for a single agent."""

    DEFAULT_CSS = """
    AgentCard {
        height: 5;
        margin: 0 1 1 0;
        padding: 1 2;
        background: #313244;
        border: tall #45475a;
        width: 1fr;
    }

    AgentCard:hover {
        border: tall #89b4fa;
    }

    AgentCard .agent-name {
        text-style: bold;
        color: #89b4fa;
    }

    AgentCard .agent-desc {
        color: #a6adc8;
    }

    AgentCard .agent-meta {
        color: #6c7086;
    }
    """

    class Selected(Message):
        def __init__(self, agent_name: str) -> None:
            super().__init__()
            self.agent_name = agent_name

    def __init__(self, agent: AgentInfo, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent = agent

    def compose(self) -> ComposeResult:
        full_desc = self.agent.description
        desc = full_desc[:70] + "..." if len(full_desc) > 70 else full_desc
        model = self.agent.model or "default"
        tools = ", ".join(self.agent.tools[:4])
        if len(self.agent.tools) > 4:
            tools += f" +{len(self.agent.tools) - 4}"

        yield Label(f"[bold #89b4fa]{self.agent.name}[/bold #89b4fa]", classes="agent-name")
        yield Label(f"[#a6adc8]{desc}[/#a6adc8]", classes="agent-desc")
        yield Label(f"[#6c7086]model: {model}  tools: {tools}[/#6c7086]", classes="agent-meta")

    def on_click(self) -> None:
        self.post_message(self.Selected(self.agent.name))


class MainScreen(Screen):
    """Primary screen — agent dashboard."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("n", "new_agent", "New agent", show=True),
        Binding("i", "install_team", "Install team", show=True),
        Binding("l", "launch_claude", "Launch Claude", show=True),
        Binding("d", "delete_agent", "Delete", show=False),
    ]

    class LaunchClaude(Message):
        def __init__(self, agent: str = "") -> None:
            super().__init__()
            self.agent = agent

    class AgentsChanged(Message):
        pass

    def __init__(self, config: CadreConfig, agents: list[AgentInfo], **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.agents = agents
        self._selected_agent: str | None = None

    def compose(self) -> ComposeResult:
        from cadre import __version__

        yield HeaderBar(
            project_name=self.config.project.name,
            version=__version__,
        )

        with Horizontal(id="main-content"):
            with Vertical(id="dashboard"):
                yield Label("[bold]Agents[/bold]", id="section-title")

                if self.agents:
                    for agent in self.agents:
                        yield AgentCard(agent, id=f"card-{agent.name}")
                else:
                    yield Static(
                        "[dim]No agents configured. Press [bold]I[/bold] to install a team.[/dim]",
                        id="empty-state",
                    )

                with Horizontal(id="action-bar"):
                    yield Button("Launch Claude", variant="primary", id="launch-btn")
                    yield Button("New Agent", variant="default", id="new-btn")
                    yield Button("Install Team", variant="default", id="team-btn")

            yield AgentSidebar(agents=self.agents, id="sidebar")

        yield RichLog(highlight=True, markup=True, wrap=True, auto_scroll=True, id="log")

    def get_log(self) -> RichLog:
        return self.query_one("#log", RichLog)

    def toggle_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar", AgentSidebar)
        sidebar.display = not sidebar.display

    def on_mount(self) -> None:
        """Focus first card if any."""
        if self.agents:
            self._selected_agent = self.agents[0].name

    def on_agent_card_selected(self, event: AgentCard.Selected) -> None:
        """Handle agent card click — open editor."""
        self._selected_agent = event.agent_name
        self._edit_agent(event.agent_name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "launch-btn":
            self.post_message(self.LaunchClaude())
        elif event.button.id == "new-btn":
            self.action_new_agent()
        elif event.button.id == "team-btn":
            self.action_install_team()

    def action_launch_claude(self) -> None:
        self.post_message(self.LaunchClaude())

    def action_new_agent(self) -> None:
        from cadre.tui.screens.agent_editor import AgentEditorScreen

        self.app.push_screen(
            AgentEditorScreen(),
            callback=self._on_agent_edited,
        )

    def action_install_team(self) -> None:
        from cadre.tui.screens.team_picker import TeamPickerScreen

        self.app.push_screen(
            TeamPickerScreen(),
            callback=self._on_team_installed,
        )

    def action_delete_agent(self) -> None:
        if self._selected_agent:
            from cadre.agents.manager import delete_agent

            delete_agent(self._selected_agent)
            log = self.get_log()
            log.write(f"[red]Deleted agent: {self._selected_agent}[/red]\n")
            self.post_message(self.AgentsChanged())

    def _edit_agent(self, name: str) -> None:
        from cadre.agents.manager import load_agent
        from cadre.tui.screens.agent_editor import AgentEditorScreen

        try:
            agent = load_agent(name)
        except FileNotFoundError:
            return

        self.app.push_screen(
            AgentEditorScreen(agent=agent),
            callback=self._on_agent_edited,
        )

    def _on_agent_edited(self, result: bool | None) -> None:
        if result:
            self.post_message(self.AgentsChanged())

    def _on_team_installed(self, result: bool | None) -> None:
        if result:
            self.post_message(self.AgentsChanged())
