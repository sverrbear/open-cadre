"""Agent sidebar — shows installed agents with details."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from cadre.agents.manager import AgentInfo


class AgentSidebarCard(Static):
    """A compact agent info card for the sidebar."""

    def __init__(self, agent: AgentInfo, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent = agent
        self.add_class("agent-card")

    def render(self) -> Text:
        text = Text()
        text.append(f"{self.agent.name}", style="bold #89b4fa")
        model = self.agent.model or "default"
        text.append(f"\n{model}", style="#6c7086")
        tools_str = ", ".join(self.agent.tools[:3])
        if len(self.agent.tools) > 3:
            tools_str += "..."
        text.append(f"\n{tools_str}", style="#585b70")
        return text


class AgentSidebar(Widget):
    """Sidebar showing all installed agents."""

    def __init__(self, agents: list[AgentInfo], **kwargs) -> None:
        super().__init__(**kwargs)
        self.agents = agents

    def compose(self) -> ComposeResult:
        yield Label("[bold]Team[/bold]\n", id="sidebar-title")
        if self.agents:
            for agent in self.agents:
                yield AgentSidebarCard(
                    agent=agent,
                    id=f"sidebar-card-{agent.name}",
                )
        else:
            yield Static("[dim]No agents[/dim]")
