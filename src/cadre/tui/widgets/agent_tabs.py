"""Agent tabs widget — tabbed container with one ChatPane per agent."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import TabbedContent, TabPane

from cadre.tui.widgets.chat_pane import ChatPane


class AgentTabs(Widget):
    """Tabbed container creating one ChatPane per enabled agent plus a Team tab."""

    def __init__(self, agent_names: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_names = agent_names

    def compose(self) -> ComposeResult:
        with TabbedContent():
            # Team tab first — shows interleaved output from all agents
            with TabPane("Team", id="tab-team"):
                yield ChatPane(agent_name="team", id="chat-team")
            # Individual agent tabs
            for name in self.agent_names:
                with TabPane(name.capitalize(), id=f"tab-{name}"):
                    yield ChatPane(agent_name=name, id=f"chat-{name}")

    def get_chat_pane(self, agent_name: str) -> ChatPane | None:
        """Get the ChatPane for a given agent name."""
        try:
            return self.query_one(f"#chat-{agent_name}", ChatPane)
        except Exception:
            return None

    def get_team_pane(self) -> ChatPane:
        """Get the Team tab's ChatPane."""
        return self.query_one("#chat-team", ChatPane)

    def switch_to_agent(self, agent_name: str) -> None:
        """Switch to a specific agent's tab."""
        tabbed = self.query_one(TabbedContent)
        tabbed.active = f"tab-{agent_name}"
