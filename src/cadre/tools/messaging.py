"""Messaging tool — enables peer-to-peer agent communication."""

from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING, Any

from cadre.tools.base import Tool

if TYPE_CHECKING:
    from cadre.orchestrator.router import MessageRouter

# Tracks delegation depth across nested message_agent calls within a coroutine chain.
_message_depth: contextvars.ContextVar[int] = contextvars.ContextVar("_message_depth", default=0)

MAX_DELEGATION_DEPTH = 3


class MessageAgentTool(Tool):
    """Send a message to a teammate and receive their response."""

    def __init__(
        self,
        agent_name: str,
        team_agent_names: list[str],
    ) -> None:
        self._agent_name = agent_name
        self._team_agent_names = team_agent_names
        self._router: MessageRouter | None = None

        teammates = [n for n in team_agent_names if n != agent_name]
        super().__init__(
            name="message_agent",
            description=(
                "Send a message to a teammate and get their response. "
                "Use this to delegate tasks, ask questions, or report status."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "agent": {
                        "type": "string",
                        "description": "Name of the teammate to message",
                        "enum": teammates,
                    },
                    "message": {
                        "type": "string",
                        "description": "The message to send to the teammate",
                    },
                },
                "required": ["agent", "message"],
            },
        )

    def set_router(self, router: MessageRouter) -> None:
        """Inject the message router (called after router construction)."""
        self._router = router

    async def execute(self, args: dict[str, Any]) -> str:
        """Send a message to a teammate and return their response."""
        if self._router is None:
            return "Error: messaging not available (router not initialized)"

        target = args.get("agent", "")
        message = args.get("message", "")

        if not target or not message:
            return "Error: both 'agent' and 'message' are required"

        if target not in self._team_agent_names:
            available = [n for n in self._team_agent_names if n != self._agent_name]
            return f"Error: agent '{target}' not found. Available: {', '.join(available)}"

        if target == self._agent_name:
            return "Error: cannot message yourself"

        # Check delegation depth to prevent infinite recursion
        depth = _message_depth.get()
        if depth >= MAX_DELEGATION_DEPTH:
            return (
                "Error: maximum delegation depth reached. "
                "Respond directly instead of delegating further."
            )

        token = _message_depth.set(depth + 1)
        try:
            # Prefix message with sender context
            prefixed = f"[Message from {self._agent_name}]: {message}"

            response_text = ""
            async for event in self._router.send_to_agent(target, prefixed):
                if event.type == "response":
                    response_text = event.content

            return response_text if response_text else "(no response received)"
        finally:
            _message_depth.reset(token)
