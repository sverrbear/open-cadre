"""Per-agent session management — tracks conversation history and state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Session:
    """Conversation session for an agent."""

    agent_name: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

    def get_history(self) -> list[dict[str, str]]:
        """Get messages in LLM-compatible format (role + content only)."""
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]

    def clear(self) -> None:
        self.messages.clear()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0


@dataclass
class SessionManager:
    """Manages sessions for all agents."""

    sessions: dict[str, Session] = field(default_factory=dict)

    def get_or_create(self, agent_name: str) -> Session:
        if agent_name not in self.sessions:
            self.sessions[agent_name] = Session(agent_name=agent_name)
        return self.sessions[agent_name]

    def clear_all(self) -> None:
        self.sessions.clear()

    def get_total_cost(self) -> float:
        return sum(s.total_cost for s in self.sessions.values())
