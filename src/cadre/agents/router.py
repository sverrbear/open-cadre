"""TeamRouter — coordinates multiple AgentSessions for team chat."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from cadre.agents.session import AgentSession, StreamEvent
from cadre.tui.screens.chat_settings import ChatSessionSettings

if TYPE_CHECKING:
    from cadre.agents.manager import AgentInfo


@dataclass
class TeamMessage:
    """A message in the team conversation timeline."""

    sender: str  # "user" or agent name
    recipient: str  # agent name, "all", or "user"
    content: str
    message_type: Literal["user", "agent_text", "agent_tool", "routing", "system", "error"]

    # For routing messages
    from_agent: str = ""

    # Stream event (if this came from a stream)
    stream_event: StreamEvent | None = None


# Maximum routing depth to prevent infinite loops
MAX_ROUTING_DEPTH = 10


class TeamRouter:
    """Coordinates multiple AgentSessions for a team.

    Manages lifecycle of all agent sessions, routes @mentions between agents,
    and serializes permission requests.
    """

    def __init__(self) -> None:
        self.team_name: str = ""
        self.sessions: dict[str, AgentSession] = {}
        self.agent_names: set[str] = set()
        self._mention_pattern: re.Pattern | None = None
        self._permission_lock = asyncio.Lock()
        self._routing_depth: dict[str, int] = {}  # track per-chain depth

        # Callbacks — set by TeamChatScreen
        self.on_message: Callable[[TeamMessage], None] | None = None
        self.on_agent_status_change: Callable[[str, str, str], None] | None = None
        self.on_permission_needed: Callable[[str, dict], Awaitable[bool]] | None = None

    def start_team(
        self,
        team_name: str,
        agents: list[AgentInfo],
        settings: ChatSessionSettings | None = None,
    ) -> None:
        """Initialize sessions for all team agents."""
        self.team_name = team_name
        self.agent_names = {a.name for a in agents}

        # Build @mention regex: @lead, @engineer, etc.
        names = "|".join(re.escape(n) for n in sorted(self.agent_names))
        self._mention_pattern = re.compile(
            rf"@({names})\b\s*(.*?)(?=\n@(?:{names})\b|\Z)",
            re.DOTALL,
        )

        for agent in agents:
            agent_settings = ChatSessionSettings(
                permission_mode=agent.permission_mode or "",
                model=agent.model or "",
                effort=agent.effort or "medium",
                skip_permissions=settings.skip_permissions if settings else False,
            )
            session = AgentSession(
                agent_name=agent.name,
                settings=agent_settings,
            )
            session.on_stream_event = self._make_event_handler(agent.name)
            session.on_permission_request = self._handle_permission
            session.on_status_change = self._handle_status_change
            session.on_complete = self._handle_agent_complete
            self.sessions[agent.name] = session

    def _make_event_handler(self, agent_name: str) -> Callable[[StreamEvent], None]:
        """Create a stream event handler bound to a specific agent."""

        def handler(se: StreamEvent) -> None:
            self._on_agent_event(agent_name, se)

        return handler

    def _on_agent_event(self, agent_name: str, se: StreamEvent) -> None:
        """Forward agent stream events as TeamMessages."""
        if not self.on_message:
            return

        if se.event_type in ("assistant", "content_block_delta"):
            if se.text:
                msg = TeamMessage(
                    sender=agent_name,
                    recipient="user",
                    content=se.text,
                    message_type="agent_text",
                    stream_event=se,
                )
                self.on_message(msg)

        elif se.event_type == "tool_use":
            task = f"Using {se.tool_name}"
            if se.tool_input_summary:
                task += f" {se.tool_input_summary}"
            msg = TeamMessage(
                sender=agent_name,
                recipient="user",
                content=task,
                message_type="agent_tool",
                stream_event=se,
            )
            self.on_message(msg)

        elif se.event_type == "result":
            msg = TeamMessage(
                sender=agent_name,
                recipient="user",
                content="",
                message_type="agent_text",
                stream_event=se,
            )
            self.on_message(msg)

        elif se.event_type == "error":
            msg = TeamMessage(
                sender=agent_name,
                recipient="user",
                content=se.text,
                message_type="error",
            )
            self.on_message(msg)

    def _handle_status_change(self, agent_name: str, status: str, task: str) -> None:
        if self.on_agent_status_change:
            self.on_agent_status_change(agent_name, status, task)

    async def _handle_permission(self, agent_name: str, event: dict) -> bool:
        """Serialize permission requests — one dialog at a time."""
        async with self._permission_lock:
            if self.on_permission_needed:
                return await self.on_permission_needed(agent_name, event)
            return False

    def _handle_agent_complete(self, agent_name: str, accumulated_text: str) -> None:
        """When an agent completes, check for @mentions to route."""
        if not accumulated_text:
            return

        depth = self._routing_depth.get(agent_name, 0)
        mentions = self._parse_mentions(accumulated_text)

        for target, message_text in mentions:
            if depth >= MAX_ROUTING_DEPTH:
                if self.on_message:
                    self.on_message(
                        TeamMessage(
                            sender="system",
                            recipient="user",
                            content=(
                                f"Routing depth limit ({MAX_ROUTING_DEPTH}) "
                                f"reached. Stopping auto-delegation from "
                                f"@{agent_name}."
                            ),
                            message_type="system",
                        )
                    )
                break

            # Route the message
            self._route_message(agent_name, target, message_text, depth + 1)

    def _parse_mentions(self, text: str) -> list[tuple[str, str]]:
        """Extract @mentions from text. Returns [(target_agent, message)]."""
        if not self._mention_pattern:
            return []

        results = []
        for match in self._mention_pattern.finditer(text):
            target = match.group(1)
            message = match.group(2).strip()
            if target in self.agent_names and message:
                results.append((target, message))
        return results

    def _route_message(
        self,
        from_agent: str,
        to_agent: str,
        message: str,
        depth: int,
    ) -> None:
        """Route a message from one agent to another."""
        if to_agent not in self.sessions:
            if self.on_message:
                available = ", ".join(f"@{n}" for n in sorted(self.agent_names))
                self.on_message(
                    TeamMessage(
                        sender="system",
                        recipient="user",
                        content=(f"@{to_agent} is not in this team. Available: {available}"),
                        message_type="system",
                    )
                )
            return

        # Show routing in timeline
        if self.on_message:
            self.on_message(
                TeamMessage(
                    sender=from_agent,
                    recipient=to_agent,
                    content=message[:80] + ("..." if len(message) > 80 else ""),
                    message_type="routing",
                    from_agent=from_agent,
                )
            )

        # Track depth for the target agent
        self._routing_depth[to_agent] = depth

        # Send concise message to target — minimal framing
        framed = f"From @{from_agent}: {message}"

        session = self.sessions[to_agent]
        self._pending_routes: list[asyncio.Task] = getattr(self, "_pending_routes", [])
        task = asyncio.ensure_future(session.send_message(framed))
        self._pending_routes.append(task)
        task.add_done_callback(lambda t: self._pending_routes.remove(t))

    async def send_user_message(self, message: str, target: str = "lead") -> None:
        """Send a user message to a specific agent.

        If message starts with @agentname, routes to that agent instead.
        """
        # Check for @mention at start of message
        if message.startswith("@"):
            for name in self.agent_names:
                prefix = f"@{name}"
                if message.startswith(prefix) and (
                    len(message) == len(prefix) or message[len(prefix)] in (" ", "\n", "\t")
                ):
                    target = name
                    message = message[len(prefix) :].strip()
                    break

        if target not in self.sessions:
            if self.on_message:
                self.on_message(
                    TeamMessage(
                        sender="system",
                        recipient="user",
                        content=f"Agent @{target} not found in team.",
                        message_type="system",
                    )
                )
            return

        # Reset routing depth for user-initiated messages
        self._routing_depth.clear()

        # Show user message in timeline
        if self.on_message:
            self.on_message(
                TeamMessage(
                    sender="user",
                    recipient=target,
                    content=message,
                    message_type="user",
                )
            )

        await self.sessions[target].send_message(message)

    def stop_all(self) -> None:
        """Terminate all running agent sessions."""
        for session in self.sessions.values():
            session.stop()

    def get_session(self, agent_name: str) -> AgentSession | None:
        """Get an agent's session by name."""
        return self.sessions.get(agent_name)
