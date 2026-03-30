"""Base LLM provider protocol."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol that all LLM providers must satisfy."""

    async def complete(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict] | None = None,
        stream: bool = True,
    ) -> AsyncIterator[dict]:
        """Send a completion request and yield response chunks."""
        ...

    def get_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for a given model and token counts."""
        ...
