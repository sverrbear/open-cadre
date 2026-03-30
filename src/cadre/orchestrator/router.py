"""Message router — handles @agent mentions, team routing, and broadcasts."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

from cadre.agents.base import AgentEvent
from cadre.orchestrator.team import Team


@dataclass
class MessageRouter:
    """Routes messages to agents based on @mentions or team lead delegation."""

    team: Team

    async def route(self, message: str) -> AsyncIterator[AgentEvent]:
        """Route a message to the appropriate agent(s)."""
        # Check for @agent mention
        target = self._parse_mention(message)
        if target:
            clean_message = re.sub(r"@\w+\s*", "", message, count=1).strip()
            async for event in self.send_to_agent(target, clean_message):
                yield event
            return

        # Default: send to team lead (or solo agent)
        default_agent = self._get_default_agent()
        if default_agent:
            async for event in self.send_to_agent(default_agent, message):
                yield event
        else:
            yield AgentEvent(type="error", content="No agents available")

    async def send_to_agent(self, agent_name: str, message: str) -> AsyncIterator[AgentEvent]:
        """Send a message directly to a specific agent."""
        loop = self.team.get_loop(agent_name)
        if loop is None:
            yield AgentEvent(
                type="error",
                content=(
                    f"Agent '{agent_name}' not found."
                    f" Available: {', '.join(self.team.agents.keys())}"
                ),
            )
            return

        async for event in loop.run(message):
            yield event

    def _parse_mention(self, message: str) -> str | None:
        """Extract @agent mention from the start of a message."""
        match = re.match(r"^@(\w+)\b", message.strip())
        if match:
            agent_name = match.group(1)
            if agent_name in self.team.agents:
                return agent_name
        return None

    def _get_default_agent(self) -> str | None:
        """Get the default agent to route to (lead in full mode, solo in solo mode)."""
        if "lead" in self.team.agents:
            return "lead"
        if "solo" in self.team.agents:
            return "solo"
        # Fall back to first available agent
        agents = list(self.team.agents.keys())
        return agents[0] if agents else None
