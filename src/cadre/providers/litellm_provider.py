"""LiteLLM provider — unified access to 100+ LLM providers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import litellm


@dataclass
class UsageStats:
    """Token usage and cost tracking for a single request."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


@dataclass
class LiteLLMProvider:
    """LLM provider backed by LiteLLM (Anthropic, OpenAI, Google, Ollama, etc.)."""

    api_keys: dict[str, str] = field(default_factory=dict)
    api_bases: dict[str, str] = field(default_factory=dict)
    total_cost: float = 0.0

    def __post_init__(self) -> None:
        # Suppress LiteLLM's noisy logging
        litellm.suppress_debug_info = True
        # Set API keys — also push into os.environ so LiteLLM picks them up
        # for all providers (not just the ones we explicitly map here)
        import os

        _LITELLM_ATTR = {
            "anthropic": "anthropic_key",
            "openai": "openai_key",
        }
        _ENV_VAR = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }
        for provider, key in self.api_keys.items():
            if not key:
                continue
            # Set on litellm module if it has a named attribute
            attr = _LITELLM_ATTR.get(provider)
            if attr:
                setattr(litellm, attr, key)
            # Always set in os.environ so LiteLLM's generic lookup works
            env_var = _ENV_VAR.get(provider, f"{provider.upper()}_API_KEY")
            os.environ.setdefault(env_var, key)

    async def complete(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict] | None = None,
        stream: bool = True,
    ) -> AsyncIterator[dict]:
        """Send completion request via LiteLLM and yield response chunks or full response."""
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools

        # Set custom API base for providers like Ollama
        provider_name = model.split("/")[0] if "/" in model else ""
        if provider_name in self.api_bases:
            kwargs["api_base"] = self.api_bases[provider_name]

        response = await litellm.acompletion(**kwargs)

        if stream:
            collected_content = ""
            collected_tool_calls: list[dict] = []
            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue

                # Yield streaming text
                if delta.content:
                    collected_content += delta.content
                    yield {"type": "content_delta", "content": delta.content}

                # Collect tool call deltas
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        while len(collected_tool_calls) <= idx:
                            collected_tool_calls.append(
                                {"id": "", "function": {"name": "", "arguments": ""}}
                            )
                        if tc_delta.id:
                            collected_tool_calls[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                collected_tool_calls[idx]["function"]["name"] = (
                                    tc_delta.function.name
                                )
                            if tc_delta.function.arguments:
                                collected_tool_calls[idx]["function"]["arguments"] += (
                                    tc_delta.function.arguments
                                )

            # Yield the final assembled message
            msg: dict[str, Any] = {"role": "assistant", "content": collected_content}
            if collected_tool_calls:
                msg["tool_calls"] = collected_tool_calls
            yield {"type": "message_complete", "message": msg}

            # Track cost
            if hasattr(chunk, "usage") and chunk.usage:
                self._track_cost(model, chunk.usage)
        else:
            # Non-streaming
            msg = {
                "role": "assistant",
                "content": response.choices[0].message.content or "",
            }
            if response.choices[0].message.tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in response.choices[0].message.tool_calls
                ]
            yield {"type": "message_complete", "message": msg}

            if response.usage:
                self._track_cost(model, response.usage)

    def _track_cost(self, model: str, usage: Any) -> None:
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        cost = self.get_cost(model, input_tokens, output_tokens)
        self.total_cost += cost

    def get_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost using LiteLLM's cost tracking."""
        try:
            return litellm.completion_cost(
                model=model,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
            )
        except Exception:
            return 0.0
