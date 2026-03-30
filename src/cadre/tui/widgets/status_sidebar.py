"""Status sidebar widget — live agent status display."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

STATUS_ICONS = {
    "idle": ("● idle", "status-idle"),
    "thinking": ("◉ thinking...", "status-thinking"),
    "tool_calling": ("◉ calling tools...", "status-tool-calling"),
    "waiting_for_approval": ("⏸ waiting...", "status-waiting"),
    "error": ("✗ error", "status-error"),
}


class AgentCard(Static):
    """A single agent's status card."""

    status = reactive("idle")

    def __init__(self, agent_name: str, model: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_name = agent_name
        self.model = model
        self.add_class("agent-card")

    def render(self) -> Text:
        icon, _css_class = STATUS_ICONS.get(self.status, ("? unknown", "status-idle"))
        text = Text()
        text.append(f"{self.agent_name}", style="bold #89b4fa")
        text.append(f"\n{self.model[:24]}", style="#6c7086")
        text.append(f"\n{icon}")
        return text

    def watch_status(self, new_status: str) -> None:
        """Update CSS classes when status changes."""
        for cls in (
            "status-idle",
            "status-thinking",
            "status-tool-calling",
            "status-waiting",
            "status-error",
        ):
            self.remove_class(cls)
        _, css_class = STATUS_ICONS.get(new_status, ("", "status-idle"))
        self.add_class(css_class)


class StatusSidebar(Widget):
    """Sidebar showing live status for all agents."""

    def __init__(self, agents: dict[str, dict], **kwargs) -> None:
        """agents: dict mapping name -> {"role": str, "model": str}"""
        super().__init__(**kwargs)
        self.agents = agents

    def compose(self) -> ComposeResult:
        yield Label("[bold]Team Status[/bold]\n", id="sidebar-title")
        for name, info in self.agents.items():
            yield AgentCard(
                agent_name=name,
                model=info.get("model", "unknown"),
                id=f"agent-card-{name}",
            )

    def update_agent_status(self, agent_name: str, status: str) -> None:
        """Update a specific agent's status."""
        try:
            card = self.query_one(f"#agent-card-{agent_name}", AgentCard)
            card.status = status
        except Exception:
            pass
