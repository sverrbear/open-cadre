"""Chat screen — in-TUI frontend for interacting with Claude Code."""

from __future__ import annotations

import asyncio
import json
import random
from typing import TYPE_CHECKING, ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Input, Label, RichLog

from cadre.tui.screens.chat_settings import ChatSessionSettings

if TYPE_CHECKING:
    from cadre.agents.manager import AgentInfo

THINKING_MESSAGES = [
    "Claude is thinking...",
    "Pondering your question...",
    "Reasoning through this...",
    "Analyzing your request...",
    "Working on a response...",
    "Contemplating the possibilities...",
    "Processing your input...",
    "Crafting a thoughtful reply...",
    "Considering the best approach...",
    "Mulling it over...",
    "Diving into the details...",
    "Connecting the dots...",
    "Weighing the options...",
    "Formulating a response...",
    "Thinking deeply about this...",
    "Exploring the solution space...",
    "Assembling the answer...",
    "Running through the logic...",
    "Piecing it together...",
    "Almost there...",
]

THINKING_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class ChatScreen(Screen):
    """Full-screen chat interface for Claude Code."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("ctrl+comma", "open_settings", "Settings", show=True),
    ]

    DEFAULT_CSS = """
    ChatScreen {
        layout: vertical;
    }

    #chat-header {
        height: 3;
        background: #313244;
        padding: 0 2;
        layout: horizontal;
        align: left middle;
    }

    #chat-header #back-btn {
        min-width: 8;
        margin-right: 2;
    }

    #chat-header #chat-title {
        width: 1fr;
        color: #89b4fa;
        text-style: bold;
    }

    #chat-header #settings-summary {
        color: #6c7086;
        width: auto;
        margin-right: 1;
    }

    #chat-header #settings-btn {
        min-width: 10;
    }

    #chat-log {
        height: 1fr;
        background: #1e1e2e;
        padding: 0 2;
        scrollbar-size: 1 1;
    }

    #chat-input-bar {
        height: 3;
        background: #313244;
        padding: 0 1;
        layout: horizontal;
        align: left middle;
    }

    #chat-input {
        width: 1fr;
    }

    #send-btn {
        min-width: 8;
        margin-left: 1;
    }

    #stop-btn {
        min-width: 8;
        margin-left: 1;
        display: none;
    }

    #thinking-indicator {
        color: #89b4fa;
        text-style: italic;
        padding: 0 2;
        height: 1;
        display: none;
    }
    """

    class GoBack(Message):
        pass

    def __init__(
        self,
        agent: str = "",
        agent_info: AgentInfo | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.agent = agent
        self._agent_info = agent_info
        self.session_id: str | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._is_streaming = False
        self._thinking = False
        self._thinking_timer: asyncio.Task | None = None
        self._thinking_label: Label | None = None

        # Initialize session settings from agent defaults
        self._session_settings = ChatSessionSettings()
        if agent_info:
            self._session_settings.permission_mode = agent_info.permission_mode or ""
            self._session_settings.model = agent_info.model or ""
            self._session_settings.effort = agent_info.effort or ""

    def compose(self) -> ComposeResult:
        agent_label = f"  agent: {self.agent}" if self.agent else ""
        with Vertical():
            with Horizontal(id="chat-header"):
                yield Button("\u2190 Back", variant="default", id="back-btn")
                yield Label(
                    f"Chat with Claude Code{agent_label}",
                    id="chat-title",
                )
                yield Label("", id="settings-summary")
                yield Button("Settings", variant="default", id="settings-btn")
            yield RichLog(
                highlight=True,
                markup=True,
                wrap=True,
                auto_scroll=True,
                id="chat-log",
            )
            yield Label("", id="thinking-indicator")
            with Horizontal(id="chat-input-bar"):
                yield Input(
                    placeholder="Type a message...",
                    id="chat-input",
                )
                yield Button("Send", variant="primary", id="send-btn")
                yield Button("Stop", variant="error", id="stop-btn")

    def on_mount(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        agent_hint = f" with agent [bold]{self.agent}[/bold]" if self.agent else ""
        log.write(f"[dim]Connected to Claude Code{agent_hint}. Type a message to begin.[/dim]\n")
        self.query_one("#chat-input", Input).focus()
        self._update_settings_summary()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.action_go_back()
        elif event.button.id == "send-btn":
            self._submit_input()
        elif event.button.id == "stop-btn":
            self._stop_streaming()
        elif event.button.id == "settings-btn":
            self.action_open_settings()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self._submit_input()

    def action_open_settings(self) -> None:
        """Open the session settings modal."""
        from cadre.tui.screens.chat_settings import ChatSettingsModal

        self.app.push_screen(
            ChatSettingsModal(settings=self._session_settings),
            callback=self._on_settings_result,
        )

    def _on_settings_result(self, result: ChatSessionSettings | None) -> None:
        """Apply settings from the modal."""
        if result is not None:
            self._session_settings = result
            self._update_settings_summary()

    def _update_settings_summary(self) -> None:
        """Update the header summary label with active settings."""
        parts = []
        s = self._session_settings
        if s.permission_mode:
            parts.append(f"mode:{s.permission_mode}")
        if s.model:
            parts.append(f"model:{s.model}")
        if s.effort:
            parts.append(f"effort:{s.effort}")
        if s.skip_permissions:
            parts.append("skip-perms")

        summary = self.query_one("#settings-summary", Label)
        summary.update("  ".join(parts) if parts else "")

    def _submit_input(self) -> None:
        input_widget = self.query_one("#chat-input", Input)
        message = input_widget.value.strip()
        if not message or self._is_streaming:
            return

        log = self.query_one("#chat-log", RichLog)
        log.write(f"\n[bold #cdd6f4]You:[/bold #cdd6f4] {message}\n")

        input_widget.value = ""
        self._set_streaming(True)
        self._thinking = True
        self._start_thinking_animation()
        self._send_message(message)

    def _start_thinking_animation(self) -> None:
        """Start the animated thinking indicator."""
        indicator = self.query_one("#thinking-indicator", Label)
        indicator.display = True
        self._thinking_message = random.choice(THINKING_MESSAGES)
        indicator.update(f"{THINKING_FRAMES[0]} {self._thinking_message}")
        self._thinking_timer = asyncio.ensure_future(self._animate_thinking())

    async def _animate_thinking(self) -> None:
        """Animate the thinking indicator with spinner and rotating messages."""
        indicator = self.query_one("#thinking-indicator", Label)
        frame_idx = 0
        cycle_count = 0
        try:
            while self._thinking:
                frame_idx = (frame_idx + 1) % len(THINKING_FRAMES)
                cycle_count += 1
                # Change the thinking message every ~30 frames (~3 seconds)
                if cycle_count % 30 == 0:
                    self._thinking_message = random.choice(THINKING_MESSAGES)
                indicator.update(f"{THINKING_FRAMES[frame_idx]} {self._thinking_message}")
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    def _stop_thinking_animation(self) -> None:
        """Stop and hide the thinking indicator."""
        self._thinking = False
        if self._thinking_timer and not self._thinking_timer.done():
            self._thinking_timer.cancel()
            self._thinking_timer = None
        try:
            indicator = self.query_one("#thinking-indicator", Label)
            indicator.display = False
        except Exception:
            pass

    def _set_streaming(self, streaming: bool) -> None:
        self._is_streaming = streaming
        input_widget = self.query_one("#chat-input", Input)
        send_btn = self.query_one("#send-btn", Button)
        stop_btn = self.query_one("#stop-btn", Button)

        input_widget.disabled = streaming
        send_btn.display = not streaming
        stop_btn.display = streaming

        if not streaming:
            input_widget.focus()

    def _stop_streaming(self) -> None:
        if self._process:
            self._process.terminate()

    def _build_claude_cmd(self, user_message: str) -> list[str]:
        """Build the claude CLI command with all session settings."""
        cmd = ["claude", "-p", user_message, "--output-format", "stream-json", "--verbose"]

        if self.agent:
            cmd.extend(["--agent", self.agent])
        if self.session_id:
            cmd.extend(["--resume", self.session_id])

        s = self._session_settings
        if s.model:
            cmd.extend(["--model", s.model])
        if s.effort:
            cmd.extend(["--effort", s.effort])
        if s.permission_mode:
            cmd.extend(["--permission-mode", s.permission_mode])
        if s.skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        return cmd

    @work(thread=False)
    async def _send_message(self, user_message: str) -> None:
        cmd = self._build_claude_cmd(user_message)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._process = proc

            current_text = ""
            async for raw_line in proc.stdout:
                line = raw_line.decode().strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    current_text = self._handle_stream_event(event, current_text)
                except json.JSONDecodeError:
                    pass

            # Flush any remaining text
            if current_text:
                log = self.query_one("#chat-log", RichLog)
                log.write(f"[#a6e3a1]{current_text}[/#a6e3a1]")

            await proc.wait()

            if proc.returncode and proc.returncode != 0:
                stderr_bytes = await proc.stderr.read()
                stderr = stderr_bytes.decode().strip()
                if stderr:
                    log = self.query_one("#chat-log", RichLog)
                    log.write(f"\n[bold red]Error:[/bold red] {stderr}\n")

        except FileNotFoundError:
            log = self.query_one("#chat-log", RichLog)
            log.write(
                "\n[bold red]Claude Code not found.[/bold red]\n"
                "[dim]Install: npm install -g @anthropic-ai/claude-code[/dim]\n"
            )
        except Exception as e:
            log = self.query_one("#chat-log", RichLog)
            log.write(f"\n[bold red]Error:[/bold red] {e}\n")
        finally:
            self._process = None
            self._stop_thinking_animation()
            self._set_streaming(False)

    def _handle_stream_event(self, event: dict, current_text: str) -> str:
        """Process a stream-json event and update the chat log.

        Returns the accumulated text buffer (for batching assistant text).
        """
        log = self.query_one("#chat-log", RichLog)
        event_type = event.get("type", "")

        if event_type == "assistant":
            # Flush previous text if any
            if current_text:
                log.write(f"[#a6e3a1]{current_text}[/#a6e3a1]")
                current_text = ""
            # Clear thinking indicator
            self._stop_thinking_animation()
            log.write("\n[bold #a6e3a1]Claude:[/bold #a6e3a1]")

            # Extract text from the assistant message content
            message = event.get("message", {})
            content_blocks = message.get("content", [])
            for block in content_blocks:
                if block.get("type") == "text":
                    text = block.get("text", "")
                    if text:
                        current_text += text

        elif event_type == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                current_text += delta.get("text", "")

        elif event_type == "tool_use":
            if current_text:
                log.write(f"[#a6e3a1]{current_text}[/#a6e3a1]")
                current_text = ""
            tool_name = event.get("name", event.get("tool", {}).get("name", "unknown"))
            tool_input = event.get("input", event.get("tool", {}).get("input", {}))
            input_summary = ""
            if isinstance(tool_input, dict):
                # Show a brief summary of the tool input
                for key, val in list(tool_input.items())[:2]:
                    val_str = str(val)[:80]
                    input_summary += f" {key}={val_str}"
            log.write(f"[dim #f9e2af]  \u25b8 {tool_name}{input_summary}[/dim #f9e2af]")

        elif event_type == "tool_result":
            content = event.get("content", "")
            if isinstance(content, list):
                text_parts = [b.get("text", "") for b in content if b.get("type") == "text"]
                content = "".join(text_parts)
            result_str = str(content)[:200]
            if len(str(content)) > 200:
                result_str += "..."
            log.write(f"[dim #585b70]  \u25b8 result: {result_str}[/dim #585b70]")

        elif event_type == "result":
            # If no text was displayed yet, use the result field as fallback
            result_text = event.get("result", "")
            if not current_text and result_text:
                current_text = result_text
            if current_text:
                log.write(f"[#a6e3a1]{current_text}[/#a6e3a1]")
                current_text = ""
            # Capture session_id for conversation continuity
            sid = event.get("session_id")
            if sid:
                self.session_id = sid
            # Ensure thinking is stopped
            self._stop_thinking_animation()
            log.write("")  # blank line separator

        return current_text

    def action_go_back(self) -> None:
        if self._is_streaming:
            self._stop_streaming()
        self.post_message(self.GoBack())
