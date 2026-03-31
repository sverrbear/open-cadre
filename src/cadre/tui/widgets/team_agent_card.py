"""Team agent card — live status card for an agent in team chat."""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

# Agent color palette
AGENT_COLORS: dict[str, str] = {
    "lead": "#a6e3a1",
    "engineer": "#89b4fa",
    "architect": "#f9e2af",
    "qa": "#f38ba8",
}

DEFAULT_AGENT_COLOR = "#cba6f7"


def agent_color(name: str) -> str:
    """Get the display color for an agent."""
    return AGENT_COLORS.get(name, DEFAULT_AGENT_COLOR)


class TeamAgentCard(Static):
    """Live status card for an agent in the team chat sidebar."""

    status: reactive[str] = reactive("idle")
    current_task: reactive[str] = reactive("")

    def __init__(
        self,
        agent_name: str,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.agent_name = agent_name
        self._color = agent_color(agent_name)

    def render(self) -> Text:
        text = Text()

        if self.status == "idle":
            dot = "\u25cb"
            dot_style = "#585b70"
            status_text = "idle"
            status_style = "#585b70"
        elif self.status == "thinking":
            dot = "\u25cf"
            dot_style = self._color
            status_text = "thinking..."
            status_style = f"italic {self._color}"
        else:  # working
            dot = "\u25cf"
            dot_style = self._color
            status_text = "working"
            status_style = f"bold {self._color}"

        text.append(f" {dot} ", style=dot_style)
        text.append(self.agent_name, style=f"bold {self._color}")
        text.append(f"  {status_text}", style=status_style)

        if self.current_task and self.status != "idle":
            task_display = self.current_task[:35]
            if len(self.current_task) > 35:
                task_display += "..."
            text.append(f"\n     {task_display}", style="#6c7086")

        return text
