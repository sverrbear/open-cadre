"""LiteLLM provider — unified access to 100+ LLM providers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import litellm

# Provider names in litellm.models_by_provider that map to our provider names
_PROVIDER_ALIASES: dict[str, list[str]] = {
    "anthropic": ["anthropic"],
    "openai": ["openai"],
    "google": ["gemini"],
    "deepseek": ["deepseek"],
    "ollama": ["ollama"],
}

# Model name substrings to exclude (non-chat models: images, audio, TTS, embeddings, etc.)
_EXCLUDED_PATTERNS = (
    "dall-e",
    "gpt-image",
    "tts",
    "whisper",
    "embedding",
    "realtime",
    "transcribe",
    "audio",
    "image-generation",
    "moderation",
    "video",
    "search-preview",
    "deep-research",
    "babbage",
    "davinci",
    "ft:",
)


def list_provider_models(provider: str) -> list[str]:
    """Return chat-capable model IDs for a provider from litellm's catalog.

    Models are returned in the ``provider/model-name`` format used by litellm,
    filtered to only include chat/completion models (no image, audio, TTS, or
    embedding models).
    """
    aliases = _PROVIDER_ALIASES.get(provider, [provider])
    raw_models: set[str] = set()
    for alias in aliases:
        raw_models.update(litellm.models_by_provider.get(alias, set()))

    # Filter to chat models only, deduplicate by normalized ID
    seen: set[str] = set()
    chat_models: list[str] = []
    for model_name in sorted(raw_models):
        lower = model_name.lower()
        if any(pat in lower for pat in _EXCLUDED_PATTERNS):
            continue

        # Ensure model has provider/ prefix — use litellm's prefix (e.g. gemini/)
        # rather than our internal name (google/) since litellm expects it
        model_id = model_name if "/" in model_name else f"{provider}/{model_name}"

        # Deduplicate (e.g. "deepseek-chat" and "deepseek/deepseek-chat")
        if model_id in seen:
            continue
        seen.add(model_id)

        # Check mode via litellm metadata — only include chat models
        try:
            info = litellm.get_model_info(model_id)
            if info.get("mode") not in ("chat", "completion"):
                continue
        except Exception:
            # Model not in litellm's price map — skip unless it looks like a chat model
            continue

        chat_models.append(model_id)

    return chat_models


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

        litellm_attr = {
            "anthropic": "anthropic_key",
            "openai": "openai_key",
        }
        env_var_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }
        for provider, key in self.api_keys.items():
            if not key:
                continue
            # Set on litellm module if it has a named attribute
            attr = litellm_attr.get(provider)
            if attr:
                setattr(litellm, attr, key)
            # Always set in os.environ so LiteLLM's generic lookup works
            env_var = env_var_map.get(provider, f"{provider.upper()}_API_KEY")
            # Use direct assignment to ensure the key takes effect even if
            # an empty or stale value was previously in the environment
            os.environ[env_var] = key

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

        # Resolve provider-specific settings from the model string
        provider_name = model.split("/")[0] if "/" in model else ""
        api_key = self.api_keys.get(provider_name)
        if api_key:
            kwargs["api_key"] = api_key
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
