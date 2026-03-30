"""Event bridge — adapts AgentEvent async streams to Textual messages."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from textual.message import Message

from cadre.agents.base import AgentEvent

if TYPE_CHECKING:
    from textual.app import App

    from cadre.orchestrator.router import MessageRouter


class AgentEventMessage(Message):
    """Textual message wrapping an AgentEvent with agent name."""

    def __init__(self, agent_name: str, event: AgentEvent) -> None:
        super().__init__()
        self.agent_name = agent_name
        self.event = event


class EventBridge:
    """Bridges MessageRouter async event streams into Textual's message system."""

    def __init__(self, app: App, router: MessageRouter) -> None:
        self.app = app
        self.router = router

    async def send_message(self, user_input: str) -> None:
        """Route a user message and post AgentEvents as Textual messages."""
        # Determine which agent will handle this
        agent_name = self._resolve_target(user_input)

        # Emit a synthetic "response_start" so the UI can show the agent name prefix
        first_content = True
        try:
            async for event in self.router.route(user_input):
                if first_content and event.type == "content_delta":
                    self.app.post_message(
                        AgentEventMessage(agent_name, AgentEvent(type="response_start"))
                    )
                    first_content = False
                self.app.post_message(AgentEventMessage(agent_name, event))
        except Exception as e:
            from cadre.errors import classify_llm_error, format_error_for_display

            classified = classify_llm_error(e)
            error_event = AgentEvent(type="error", content=format_error_for_display(classified))
            self.app.post_message(AgentEventMessage(agent_name, error_event))

    def _resolve_target(self, message: str) -> str:
        """Determine which agent a message is targeting."""
        match = re.match(r"^@(\w+)\b", message.strip())
        if match:
            name = match.group(1)
            if name in self.router.team.agents:
                return name
        return self.router._get_default_agent() or "team"
