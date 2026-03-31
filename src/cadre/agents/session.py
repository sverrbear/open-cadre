"""AgentSession — manages a single Claude Code subprocess conversation."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from cadre.tui.screens.chat_settings import ChatSessionSettings


@dataclass
class StreamEvent:
    """A parsed event from the Claude Code stream-json output."""

    agent_name: str
    event_type: str  # assistant, content_block_delta, tool_use, tool_result, etc.
    raw: dict[str, Any] = field(default_factory=dict)

    # Extracted fields depending on event_type
    text: str = ""  # for assistant / content_block_delta
    tool_name: str = ""  # for tool_use
    tool_input_summary: str = ""  # for tool_use (short summary)
    session_id: str = ""  # for result
    input_tokens: int = 0
    output_tokens: int = 0
    result_text: str = ""  # for result


def parse_stream_event(agent_name: str, event: dict) -> StreamEvent:
    """Parse a raw stream-json event into a StreamEvent."""
    event_type = event.get("type", "")
    se = StreamEvent(agent_name=agent_name, event_type=event_type, raw=event)

    if event_type == "assistant":
        message = event.get("message", {})
        content_blocks = message.get("content", [])
        text_parts = []
        for block in content_blocks:
            if block.get("type") == "text":
                t = block.get("text", "")
                if t:
                    text_parts.append(t)
        se.text = "".join(text_parts)
        usage = message.get("usage", {})
        se.input_tokens = usage.get("input_tokens", 0)
        se.output_tokens = usage.get("output_tokens", 0)

    elif event_type == "content_block_delta":
        delta = event.get("delta", {})
        if delta.get("type") == "text_delta":
            se.text = delta.get("text", "")

    elif event_type == "tool_use":
        se.tool_name = event.get("name", event.get("tool", {}).get("name", "unknown"))
        tool_input = event.get("input", event.get("tool", {}).get("input", {}))
        if isinstance(tool_input, dict):
            for _key, val in list(tool_input.items())[:1]:
                se.tool_input_summary = str(val)[:60]

    elif event_type == "result":
        se.result_text = event.get("result", "")
        se.session_id = event.get("session_id", "")
        usage = event.get("usage", {})
        se.input_tokens = usage.get("input_tokens", 0)
        se.output_tokens = usage.get("output_tokens", 0)

    return se


class AgentSession:
    """Manages a single Claude Code subprocess conversation.

    This class encapsulates all subprocess lifecycle management for one agent.
    It streams JSON events via callbacks and handles permission requests.
    """

    def __init__(
        self,
        agent_name: str,
        settings: ChatSessionSettings | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.settings = settings or ChatSessionSettings()
        self.session_id: str | None = None
        self.status: Literal["idle", "thinking", "working"] = "idle"
        self.current_task: str = ""
        self.accumulated_text: str = ""

        # Token tracking
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0

        # Subprocess state
        self._process: asyncio.subprocess.Process | None = None
        self._message_queue: asyncio.Queue[str] = asyncio.Queue()
        self._processing = False

        # Callbacks — set by the owner (ChatScreen or TeamRouter)
        self.on_stream_event: Callable[[StreamEvent], None] | None = None
        self.on_permission_request: Callable[[str, dict], Awaitable[bool]] | None = (
            None  # (agent_name, event) -> allowed
        )
        self.on_status_change: Callable[[str, str, str], None] | None = (
            None  # (agent_name, status, task_desc)
        )
        self.on_complete: Callable[[str, str], None] | None = None  # (agent_name, accumulated_text)

    def _set_status(self, status: Literal["idle", "thinking", "working"], task: str = "") -> None:
        self.status = status
        self.current_task = task
        if self.on_status_change:
            self.on_status_change(self.agent_name, status, task)

    def _build_cmd(self, user_message: str) -> list[str]:
        """Build the claude CLI command."""
        cmd = ["claude", "-p", user_message, "--output-format", "stream-json", "--verbose"]

        if self.agent_name:
            cmd.extend(["--agent", self.agent_name])
        if self.session_id:
            cmd.extend(["--resume", self.session_id])

        s = self.settings
        if s.model:
            cmd.extend(["--model", s.model])
        if s.effort:
            cmd.extend(["--effort", s.effort])
        if s.permission_mode:
            cmd.extend(["--permission-mode", s.permission_mode])
        if s.skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        return cmd

    async def send_message(self, text: str) -> None:
        """Send a message to this agent. Queues if agent is busy."""
        if self._processing:
            await self._message_queue.put(text)
            return
        await self._process_message(text)

    async def _process_message(self, user_message: str) -> None:
        """Process a single message — spawn subprocess, stream events."""
        self._processing = True
        self._set_status("thinking")
        self.accumulated_text = ""

        cmd = self._build_cmd(user_message)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )
            self._process = proc

            async for raw_line in proc.stdout:
                line = raw_line.decode().strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)

                    # Handle permission requests
                    if event.get("type") == "control_request":
                        await self._handle_permission(event)
                        continue

                    se = parse_stream_event(self.agent_name, event)
                    self._process_event(se)

                    if self.on_stream_event:
                        self.on_stream_event(se)

                except json.JSONDecodeError:
                    pass

            await proc.wait()

            if proc.returncode and proc.returncode != 0:
                stderr_bytes = await proc.stderr.read()
                stderr = stderr_bytes.decode().strip()
                if stderr:
                    error_event = StreamEvent(
                        agent_name=self.agent_name,
                        event_type="error",
                        text=stderr,
                    )
                    if self.on_stream_event:
                        self.on_stream_event(error_event)

        except FileNotFoundError:
            error_event = StreamEvent(
                agent_name=self.agent_name,
                event_type="error",
                text="Claude Code not found. Install: npm install -g @anthropic-ai/claude-code",
            )
            if self.on_stream_event:
                self.on_stream_event(error_event)
        except Exception as e:
            error_event = StreamEvent(
                agent_name=self.agent_name,
                event_type="error",
                text=str(e),
            )
            if self.on_stream_event:
                self.on_stream_event(error_event)
        finally:
            self._process = None
            self._set_status("idle")
            self._processing = False

            if self.on_complete:
                self.on_complete(self.agent_name, self.accumulated_text)

            # Process queued messages
            if not self._message_queue.empty():
                next_msg = await self._message_queue.get()
                await self._process_message(next_msg)

    def _process_event(self, se: StreamEvent) -> None:
        """Update internal state based on a stream event."""
        if se.event_type == "assistant":
            if se.text:
                self.accumulated_text += se.text
            if se.input_tokens:
                self.total_input_tokens += se.input_tokens
            if se.output_tokens:
                self.total_output_tokens += se.output_tokens

        elif se.event_type == "content_block_delta":
            if se.text:
                self.accumulated_text += se.text

        elif se.event_type == "tool_use":
            task_desc = f"Using {se.tool_name}"
            if se.tool_input_summary:
                task_desc += f" {se.tool_input_summary}"
            self._set_status("working", task_desc)

        elif se.event_type == "result":
            if se.session_id:
                self.session_id = se.session_id
            if se.input_tokens:
                self.total_input_tokens += se.input_tokens
            if se.output_tokens:
                self.total_output_tokens += se.output_tokens
            # If no text was accumulated, use the result text
            if not self.accumulated_text and se.result_text:
                self.accumulated_text = se.result_text

    async def _handle_permission(self, event: dict) -> None:
        """Handle a permission request from the subprocess."""
        if not self.on_permission_request:
            # Auto-deny if no handler
            await self._send_permission_response(event, False)
            return

        allowed = await self.on_permission_request(self.agent_name, event)
        await self._send_permission_response(event, allowed)

    async def _send_permission_response(self, event: dict, allowed: bool) -> None:
        """Send permission response back to the subprocess via stdin."""
        if self._process and self._process.stdin:
            request_id = event.get("request_id", "")
            response = {
                "type": "control_response",
                "request_id": request_id,
                "response": {"allowed": allowed},
            }
            response_line = json.dumps(response) + "\n"
            self._process.stdin.write(response_line.encode())
            await self._process.stdin.drain()

    def stop(self) -> None:
        """Terminate the current subprocess if running."""
        if self._process:
            self._process.terminate()

    @property
    def is_active(self) -> bool:
        """Whether this session has an active subprocess."""
        return self._process is not None
