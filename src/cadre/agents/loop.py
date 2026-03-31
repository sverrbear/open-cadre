"""Agent execution loop — drives the tool-calling cycle until a final response."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from cadre.agents.base import Agent, AgentEvent, AgentStatus
from cadre.providers.base import LLMProvider


class AgentLoop:
    """Run an agent's tool-calling loop until it produces a final text response."""

    def __init__(self, agent: Agent, provider: LLMProvider) -> None:
        self.agent = agent
        self.provider = provider
        self.max_iterations = 25

    @staticmethod
    def _get_fallback_model(model: str) -> str | None:
        """Return the mid-tier model for the same provider, or None."""
        from cadre.config import MID_TIER_MODELS

        provider = model.split("/")[0] if "/" in model else None
        if not provider:
            return None
        mid = MID_TIER_MODELS.get(provider)
        if mid and mid != model:
            return mid
        return None

    async def run(self, user_message: str) -> AsyncIterator[AgentEvent]:
        """Execute the agent loop: send message, handle tool calls, repeat until done."""
        self.agent.add_message("user", user_message)
        self.agent.status = AgentStatus.THINKING
        yield AgentEvent(type="status", content="thinking")

        used_fallback = False

        for _iteration in range(self.max_iterations):
            # Build messages
            messages = [{"role": "system", "content": self.agent.system_prompt}]
            messages.extend(self.agent.history)

            # Get tool schemas
            tool_schemas = self.agent.get_tool_schemas() or None

            # Call LLM
            assistant_msg: dict[str, Any] = {}
            try:
                async for chunk in self.provider.complete(
                    messages=messages,
                    model=self.agent.model,
                    tools=tool_schemas,
                    stream=True,
                ):
                    if chunk["type"] == "content_delta":
                        yield AgentEvent(type="content_delta", content=chunk["content"])
                    elif chunk["type"] == "message_complete":
                        assistant_msg = chunk["message"]
            except Exception as e:
                from cadre.providers.litellm_provider import ModelError

                # If the model specifically failed and we haven't retried yet,
                # fall back to the mid-tier model for the same provider.
                if isinstance(e, ModelError) and not used_fallback:
                    fallback = self._get_fallback_model(self.agent.model)
                    if fallback:
                        used_fallback = True
                        original_model = self.agent.model
                        self.agent.model = fallback
                        yield AgentEvent(
                            type="status",
                            content=(
                                f"Model {original_model} unavailable, "
                                f"retrying with {fallback}"
                            ),
                        )
                        continue

                from cadre.errors import classify_llm_error, format_error_for_display

                classified = classify_llm_error(e)
                self.agent.status = AgentStatus.ERROR
                yield AgentEvent(type="error", content=format_error_for_display(classified))
                return

            if not assistant_msg:
                yield AgentEvent(type="error", content="No response from model")
                self.agent.status = AgentStatus.ERROR
                return

            # Add assistant message to history
            self.agent.history.append(assistant_msg)

            # Check for tool calls
            tool_calls = assistant_msg.get("tool_calls", [])
            if not tool_calls:
                # Final text response — we're done
                self.agent.status = AgentStatus.IDLE
                yield AgentEvent(type="response", content=assistant_msg.get("content", ""))
                return

            # Execute tool calls
            self.agent.status = AgentStatus.TOOL_CALLING
            yield AgentEvent(type="status", content="tool_calling")

            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    func_args = {}

                tool = self.agent.get_tool(func_name)
                if tool is None:
                    result = f"Error: Unknown tool '{func_name}'"
                    yield AgentEvent(type="error", content=result)
                else:
                    yield AgentEvent(type="tool_call", tool=func_name, args=func_args)

                    if tool.dangerous:
                        self.agent.status = AgentStatus.WAITING
                        yield AgentEvent(type="confirmation_needed", tool=func_name, args=func_args)
                        # In a real implementation, we'd wait for user approval here.
                        # For now, auto-approve (the UI layer handles gating).

                    try:
                        result = await tool.execute(func_args)
                    except Exception as e:
                        result = f"Tool error: {e}"
                        yield AgentEvent(type="error", content=f"Tool '{func_name}' failed: {e}")
                    yield AgentEvent(type="tool_result", tool=func_name, result=result)

                # Add tool result to history
                self.agent.history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )

            # Continue the loop for next LLM call
            self.agent.status = AgentStatus.THINKING
            yield AgentEvent(type="status", content="thinking")

        # Hit max iterations
        self.agent.status = AgentStatus.ERROR
        yield AgentEvent(type="error", content=f"Agent hit max iterations ({self.max_iterations})")
