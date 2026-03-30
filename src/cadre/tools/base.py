"""Base tool class and tool registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Tool:
    """Base tool that agents can call. Produces OpenAI-format schemas for LiteLLM compatibility."""

    name: str
    description: str
    parameters: dict[str, Any]
    dangerous: bool = False

    async def execute(self, args: dict[str, Any]) -> str:
        """Execute the tool with given arguments. Override in subclasses."""
        raise NotImplementedError(f"Tool {self.name} has no execute implementation")

    def to_schema(self) -> dict[str, Any]:
        """OpenAI-format tool schema (works with all providers via LiteLLM)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_schemas(self) -> list[dict[str, Any]]:
        return [t.to_schema() for t in self._tools.values()]
