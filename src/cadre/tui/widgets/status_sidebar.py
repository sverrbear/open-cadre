"""Agent sidebar — shows installed agents with details."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from cadre.agents.manager import AgentInfo


class AgentSidebarCard(Static):
    """A compact agent info card for the sidebar."""

    def __init__(self, agent: AgentInfo, is_active: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent = agent
        self.is_active = is_active
        self.add_class("agent-card")

    def render(self) -> Text:
        text = Text()
        text.append(f"{self.agent.name}", style="bold #89b4fa")
        model = self.agent.model or "default"
        text.append(f"\n{model}", style="#6c7086")
        if self.is_active:
            text.append("\n● running", style="bold #a6e3a1")
        else:
            text.append("\n○ idle", style="#585b70")
        return text


class AgentSidebar(Widget):
    """Sidebar showing all installed agents."""

    def __init__(
        self, agents: list[AgentInfo], active_agents: set[str] | None = None, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.agents = agents
        self.active_agents = active_agents or set()

    def compose(self) -> ComposeResult:
        yield Label("[bold]Team[/bold]\n", id="sidebar-title")
        if self.agents:
            for agent in self.agents:
                yield AgentSidebarCard(
                    agent=agent,
                    is_active=agent.name in self.active_agents,
                    id=f"sidebar-card-{agent.name}",
                )
        else:
            yield Static("[dim]No agents[/dim]")
