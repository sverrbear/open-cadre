"""Agent definition and event types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from cadre.tools.base import Tool


class AgentStatus(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    TOOL_CALLING = "tool_calling"
    WAITING = "waiting_for_approval"
    ERROR = "error"


@dataclass
class AgentEvent:
    """Event emitted during agent execution."""

    type: str  # "content_delta", "response", "tool_call", "tool_result", "confirmation_needed", "error", "status"
    content: str = ""
    tool: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    result: str = ""


@dataclass
class Agent:
    """An AI agent with a role, model, tools, and conversation history."""

    name: str
    role: str
    system_prompt: str
    model: str
    tools: list[Tool] = field(default_factory=list)
    workflow_description: str = ""
    can_write_code: bool = False
    can_approve_pr: bool = False
    history: list[dict[str, Any]] = field(default_factory=list)
    status: AgentStatus = AgentStatus.IDLE

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-format tool schemas for all agent tools."""
        return [t.to_schema() for t in self.tools]

    def get_tool(self, name: str) -> Tool | None:
        """Find a tool by name."""
        for t in self.tools:
            if t.name == name:
                return t
        return None

    def add_message(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self.history.append({"role": role, "content": content})

    def clear_history(self) -> None:
        """Reset conversation history."""
        self.history.clear()
