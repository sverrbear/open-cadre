"""Chat screen — in-TUI frontend for interacting with Claude Code."""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from typing import TYPE_CHECKING, ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Label, RichLog, TextArea

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

# Regex to detect numbered options like "1. Option text" or "1) Option text"
OPTION_RE = re.compile(r"^\s*(\d+)[.)]\s+(.+)$", re.MULTILINE)


class ChatScreen(Screen):
    """Full-screen chat interface for Claude Code."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "go_back", "Back", show=True),
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

    #chat-log {
        height: 1fr;
        background: #1e1e2e;
        padding: 0 2;
        scrollbar-size: 1 1;
    }

    #command-palette {
        dock: bottom;
        height: auto;
        max-height: 12;
        background: #313244;
        padding: 1 2;
        display: none;
        border-top: solid #45475a;
    }

    .cmd-item {
        height: 1;
        padding: 0 1;
        color: #cdd6f4;
    }

    .cmd-item:hover {
        background: #45475a;
    }

    .cmd-name {
        color: #89b4fa;
        text-style: bold;
    }

    .cmd-desc {
        color: #6c7086;
    }

    #quick-replies {
        height: auto;
        max-height: 10;
        background: #1e1e2e;
        padding: 0 2;
        display: none;
    }

    .quick-reply-btn {
        width: 100%;
        height: 1;
        background: transparent;
        color: #cdd6f4;
        padding: 0 1;
        margin: 0;
        border: none;
        text-align: left;
        min-width: 0;
    }

    .quick-reply-btn:hover {
        background: #313244;
        color: #89b4fa;
    }

    .quick-reply-btn:focus {
        background: #313244;
        color: #89b4fa;
        text-style: bold;
    }

    .quick-reply-btn.-selected {
        background: #313244;
        color: #89b4fa;
        text-style: bold;
    }

    #chat-input-bar {
        height: auto;
        min-height: 3;
        max-height: 8;
        background: #313244;
        padding: 0 1;
        layout: horizontal;
        align: left middle;
    }

    #chat-input {
        width: 1fr;
        height: auto;
        min-height: 1;
        max-height: 5;
        background: #45475a;
        color: #cdd6f4;
        border: none;
    }

    #chat-input:focus {
        border: none;
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

    class OpenDashboard(Message):
        pass

    def __init__(
        self,
        agent: str = "",
        agent_info: AgentInfo | None = None,
        show_welcome: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.agent = agent
        self._agent_info = agent_info
        self._show_welcome = show_welcome
        self.session_id: str | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._is_streaming = False
        self._thinking = False
        self._thinking_timer: asyncio.Task | None = None
        self._thinking_label: Label | None = None
        self._shown_claude_header = False
        self._last_response_text = ""
        self._quick_reply_index = -1
        self._stream_start_time: float = 0
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._pending_permission: asyncio.Future | None = None

        # Initialize session settings from agent defaults
        self._session_settings = ChatSessionSettings()
        if agent_info:
            self._session_settings.permission_mode = agent_info.permission_mode or ""
            self._session_settings.model = agent_info.model or ""
            self._session_settings.effort = agent_info.effort or "medium"
        else:
            self._session_settings.effort = "medium"

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
            yield RichLog(
                highlight=True,
                markup=True,
                wrap=True,
                auto_scroll=True,
                id="chat-log",
            )
            yield Label("", id="thinking-indicator")
            with Vertical(id="quick-replies"):
                pass  # populated dynamically
            with Vertical(id="command-palette"):
                pass  # populated dynamically
            with Horizontal(id="chat-input-bar"):
                yield TextArea(
                    id="chat-input",
                )
                yield Button("Send", variant="primary", id="send-btn")
                yield Button("Stop", variant="error", id="stop-btn")

    def on_mount(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        if self._show_welcome:
            log.write(
                "[bold #89b4fa]Welcome to OpenCadre![/bold #89b4fa]\n\n"
                "Type [bold]/[/bold] to see available commands, or start with:\n\n"
                "  [bold #89b4fa]/init[/bold #89b4fa]     Set up your lead agent\n"
                "  [bold #89b4fa]/explore[/bold #89b4fa]  Analyze your repo and build a team\n\n"
                "[dim]Or just type a message to chat with Claude directly.[/dim]\n"
            )
        else:
            agent_hint = f" with agent [bold]{self.agent}[/bold]" if self.agent else ""
            log.write(
                f"[dim]Connected to Claude Code{agent_hint}. "
                "Type a message or [bold]/[/bold] for commands.[/dim]\n"
            )

        # Configure the TextArea for chat input
        text_area = self.query_one("#chat-input", TextArea)
        text_area.show_line_numbers = False
        text_area.tab_behavior = "focus"
        text_area.focus()
        self._update_settings_summary()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.action_go_back()
        elif event.button.id == "send-btn":
            self._submit_input()
        elif event.button.id == "stop-btn":
            self._stop_streaming()
        elif hasattr(event.button, "data") and isinstance(getattr(event.button, "data", None), str):
            # Quick reply button clicked
            self._send_quick_reply(event.button.data)

    def on_key(self, event) -> None:
        """Handle keyboard events for TextArea submit and quick-reply navigation."""
        quick_replies = self.query_one("#quick-replies", Vertical)

        # Handle quick-reply navigation when visible
        if quick_replies.display:
            buttons = list(quick_replies.query(".quick-reply-btn"))
            if event.key == "up":
                event.prevent_default()
                event.stop()
                if buttons:
                    self._quick_reply_index = max(0, self._quick_reply_index - 1)
                    self._highlight_quick_reply(buttons)
                return
            elif event.key == "down":
                event.prevent_default()
                event.stop()
                if buttons:
                    self._quick_reply_index = min(len(buttons) - 1, self._quick_reply_index + 1)
                    self._highlight_quick_reply(buttons)
                return
            elif event.key == "enter" and self._quick_reply_index >= 0:
                event.prevent_default()
                event.stop()
                if 0 <= self._quick_reply_index < len(buttons):
                    btn = buttons[self._quick_reply_index]
                    if hasattr(btn, "data") and btn.data:
                        self._send_quick_reply(btn.data)
                    else:
                        # "Type your own" option
                        self._hide_quick_replies()
                        self.query_one("#chat-input", TextArea).focus()
                return

        # Handle Enter to submit (without shift) in TextArea
        text_area = self.query_one("#chat-input", TextArea)
        if text_area.has_focus and event.key == "enter" and not event.shift:
            event.prevent_default()
            event.stop()
            self._submit_input()

    def _highlight_quick_reply(self, buttons: list) -> None:
        """Update visual highlighting of quick-reply buttons."""
        for i, btn in enumerate(buttons):
            if i == self._quick_reply_index:
                btn.add_class("-selected")
            else:
                btn.remove_class("-selected")

    def _send_quick_reply(self, text: str) -> None:
        """Send a quick-reply option as the user's message."""
        self._hide_quick_replies()
        log = self.query_one("#chat-log", RichLog)
        log.write(f"\n[bold #cdd6f4]You:[/bold #cdd6f4] {text}\n")
        self._set_streaming(True)
        self._thinking = True
        self._start_thinking_animation()
        self._send_message(text)

    def _show_quick_replies(self, options: list[str]) -> None:
        """Show quick-reply buttons for the given options."""
        container = self.query_one("#quick-replies", Vertical)
        container.remove_children()

        for option in options:
            btn = Button(f"  {option}", classes="quick-reply-btn")
            btn.data = option
            container.mount(btn)

        # Add "Type your own answer..." option
        type_own = Button(
            "  [dim]Type your own answer...[/dim]",
            classes="quick-reply-btn",
        )
        type_own.data = ""
        container.mount(type_own)

        self._quick_reply_index = 0
        container.display = True

        # Highlight first option
        buttons = list(container.query(".quick-reply-btn"))
        self._highlight_quick_reply(buttons)

    def _hide_quick_replies(self) -> None:
        """Hide the quick-reply container."""
        try:
            container = self.query_one("#quick-replies", Vertical)
            container.display = False
            self._quick_reply_index = -1
        except Exception:
            pass

    def _parse_options_from_text(self, text: str) -> list[str]:
        """Extract numbered options from Claude's response text."""
        matches = OPTION_RE.findall(text)
        if len(matches) >= 2:
            return [m[1].strip() for m in matches]
        return []

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
        text_area = self.query_one("#chat-input", TextArea)
        message = text_area.text.strip()
        if not message or self._is_streaming:
            return

        # Hide command palette and quick replies on submit
        self._hide_command_palette()
        self._hide_quick_replies()

        # Check for slash commands
        if message.startswith("/"):
            text_area.clear()
            self._dispatch_command(message)
            return

        log = self.query_one("#chat-log", RichLog)
        log.write(f"\n[bold #cdd6f4]You:[/bold #cdd6f4] {message}\n")

        text_area.clear()
        self._set_streaming(True)
        self._thinking = True
        self._start_thinking_animation()
        self._send_message(message)

    @work(thread=False)
    async def _dispatch_command(self, text: str) -> None:
        """Dispatch a slash command."""
        from cadre.tui.commands import dispatch

        handled = await dispatch(self, text)
        if not handled:
            log = self.query_one("#chat-log", RichLog)
            log.write(
                f"[bold yellow]Unknown command:[/bold yellow] {text}\n"
                "[dim]Type [bold]/help[/bold] to see available commands.[/dim]\n"
            )

    def _format_elapsed(self) -> str:
        """Format elapsed time since stream started."""
        if not self._stream_start_time:
            return ""
        elapsed = time.time() - self._stream_start_time
        if elapsed < 60:
            return f"{elapsed:.0f}s"
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes}m{seconds:02d}s"

    def _format_tokens(self) -> str:
        """Format token usage summary."""
        parts = []
        if self._total_input_tokens:
            parts.append(f"in:{self._total_input_tokens:,}")
        if self._total_output_tokens:
            parts.append(f"out:{self._total_output_tokens:,}")
        return " ".join(parts)

    def _start_thinking_animation(self) -> None:
        """Start the animated thinking indicator."""
        indicator = self.query_one("#thinking-indicator", Label)
        indicator.display = True
        self._thinking_message = random.choice(THINKING_MESSAGES)
        indicator.update(f"{THINKING_FRAMES[0]} {self._thinking_message}")
        self._thinking_timer = asyncio.ensure_future(self._animate_thinking())

    async def _animate_thinking(self) -> None:
        """Animate the thinking indicator with spinner, rotating messages, timer, and tokens."""
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

                # Build status line with timer and tokens
                elapsed = self._format_elapsed()
                tokens = self._format_tokens()
                status_parts = [f"{THINKING_FRAMES[frame_idx]} {self._thinking_message}"]
                if elapsed:
                    status_parts.append(f"[dim]{elapsed}[/dim]")
                if tokens:
                    status_parts.append(f"[dim]({tokens})[/dim]")
                indicator.update("  ".join(status_parts))
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
        text_area = self.query_one("#chat-input", TextArea)
        send_btn = self.query_one("#send-btn", Button)
        stop_btn = self.query_one("#stop-btn", Button)

        text_area.disabled = streaming
        send_btn.display = not streaming
        stop_btn.display = streaming

        if not streaming:
            text_area.focus()

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

    def _flush_text(self, log: RichLog, current_text: str) -> str:
        """Flush buffered text to the log, prepending Claude: header if needed."""
        if current_text:
            if not self._shown_claude_header:
                log.write("\n[bold #a6e3a1]Claude:[/bold #a6e3a1]")
                self._shown_claude_header = True
            log.write(f"[#a6e3a1]{current_text}[/#a6e3a1]")
            self._last_response_text += current_text
        return ""

    async def _handle_permission_request(self, event: dict) -> None:
        """Show permission dialog and send response back to Claude via stdin."""
        from cadre.tui.screens.permission_dialog import PermissionDialog

        request = event.get("request", {})
        tool_name = request.get("tool_name", "unknown")
        tool_input = request.get("input", {})
        reason = request.get("decision_reason", "")
        request_id = event.get("request_id", "")

        # Show in the chat log
        log = self.query_one("#chat-log", RichLog)
        if isinstance(tool_input, dict) and tool_name == "Bash":
            cmd_str = tool_input.get("command", "")
            log.write(f"[dim #f9e2af]  ⚠ Permission needed: {tool_name} — {cmd_str}[/dim #f9e2af]")
        else:
            log.write(f"[dim #f9e2af]  ⚠ Permission needed: {tool_name}[/dim #f9e2af]")

        # Create a future to wait for the dialog result
        future: asyncio.Future[bool] = asyncio.get_event_loop().create_future()
        self._pending_permission = future

        def on_result(allowed: bool | None) -> None:
            if not future.done():
                future.set_result(bool(allowed))

        self.app.push_screen(
            PermissionDialog(tool_name=tool_name, tool_input=tool_input, reason=reason),
            callback=on_result,
        )

        # Wait for user decision
        allowed = await future
        self._pending_permission = None

        # Send response back to Claude via stdin
        if self._process and self._process.stdin:
            response = {
                "type": "control_response",
                "request_id": request_id,
                "response": {"allowed": allowed},
            }
            response_line = json.dumps(response) + "\n"
            self._process.stdin.write(response_line.encode())
            await self._process.stdin.drain()

            if allowed:
                status = "[bold green]✓ Allowed[/bold green]"
            else:
                status = "[bold red]✗ Denied[/bold red]"
            log.write(f"[dim]  {status}[/dim]")

    @work(thread=False)
    async def _send_message(self, user_message: str) -> None:
        cmd = self._build_claude_cmd(user_message)
        self._shown_claude_header = False
        self._last_response_text = ""
        self._stream_start_time = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )
            self._process = proc

            current_text = ""
            log = self.query_one("#chat-log", RichLog)
            async for raw_line in proc.stdout:
                line = raw_line.decode().strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)

                    # Handle permission requests specially (async dialog)
                    if event.get("type") == "control_request":
                        current_text = self._flush_text(log, current_text)
                        await self._handle_permission_request(event)
                        continue

                    current_text = self._handle_stream_event(event, current_text)
                except json.JSONDecodeError:
                    pass

            # Flush any remaining text
            if current_text:
                self._flush_text(log, current_text)

            await proc.wait()

            if proc.returncode and proc.returncode != 0:
                stderr_bytes = await proc.stderr.read()
                stderr = stderr_bytes.decode().strip()
                if stderr:
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
            self._stream_start_time = 0

            # Show final token usage
            tokens = self._format_tokens()
            if tokens:
                log = self.query_one("#chat-log", RichLog)
                log.write(f"[dim #585b70]  tokens: {tokens}[/dim #585b70]")

            # Check for quick-reply options in the response
            if self._last_response_text:
                options = self._parse_options_from_text(self._last_response_text)
                if options:
                    self._show_quick_replies(options)

    def _handle_stream_event(self, event: dict, current_text: str) -> str:
        """Process a stream-json event and update the chat log.

        Returns the accumulated text buffer (for batching assistant text).
        """
        log = self.query_one("#chat-log", RichLog)
        event_type = event.get("type", "")

        if event_type == "assistant":
            # Flush previous text if any
            current_text = self._flush_text(log, current_text)
            # Note: do NOT stop thinking animation here — keep it running until "result"

            # Extract text from the assistant message content (buffer it, don't write header yet)
            message = event.get("message", {})
            content_blocks = message.get("content", [])
            for block in content_blocks:
                if block.get("type") == "text":
                    text = block.get("text", "")
                    if text:
                        current_text += text

            # Track token usage from assistant message
            usage = message.get("usage", {})
            if usage:
                self._total_input_tokens += usage.get("input_tokens", 0)
                self._total_output_tokens += usage.get("output_tokens", 0)

        elif event_type == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                current_text += delta.get("text", "")

        elif event_type == "tool_use":
            current_text = self._flush_text(log, current_text)
            tool_name = event.get("name", event.get("tool", {}).get("name", "unknown"))
            tool_input = event.get("input", event.get("tool", {}).get("input", {}))
            input_summary = ""
            if isinstance(tool_input, dict):
                for _key, val in list(tool_input.items())[:1]:
                    val_str = str(val)[:60]
                    input_summary += f" {val_str}"
            # Show tool activity in the thinking indicator (ephemeral, not in chat log)
            self._thinking_message = f"Using {tool_name}{input_summary}"

        elif event_type == "tool_result":
            # Don't persist tool results in chat — shown ephemerally via thinking indicator
            pass

        elif event_type == "result":
            # If no text was displayed yet, use the result field as fallback
            result_text = event.get("result", "")
            if not current_text and result_text:
                current_text = result_text
            current_text = self._flush_text(log, current_text)
            # Capture session_id for conversation continuity
            sid = event.get("session_id")
            if sid:
                self.session_id = sid
            # Track final token usage
            usage = event.get("usage", {})
            if usage:
                self._total_input_tokens += usage.get("input_tokens", 0)
                self._total_output_tokens += usage.get("output_tokens", 0)
            # Stop thinking animation only on final result
            self._stop_thinking_animation()
            log.write("")  # blank line separator

        return current_text

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Show/hide command palette based on input."""
        if event.text_area.id != "chat-input":
            return
        value = event.text_area.text.strip()

        # Hide quick replies when user starts typing
        self._hide_quick_replies()

        if value.startswith("/"):
            self._show_command_palette(value)
        else:
            self._hide_command_palette()

    def _show_command_palette(self, filter_text: str) -> None:
        """Show the command palette with filtered commands."""
        from cadre.tui.commands import COMMANDS

        palette = self.query_one("#command-palette", Vertical)

        # Remove existing items
        palette.remove_children()

        # Filter commands
        prefix = filter_text.lower()
        matches = [
            cmd for name, cmd in COMMANDS.items() if name.startswith(prefix) or prefix == "/"
        ]

        if not matches:
            self._hide_command_palette()
            return

        for cmd in matches:
            label = Label(
                f"[bold #89b4fa]{cmd.name:<12}[/bold #89b4fa] [#6c7086]{cmd.description}[/#6c7086]",
                classes="cmd-item",
            )
            label.data = cmd.name  # store command name for click handling
            palette.mount(label)

        palette.display = True

    def _hide_command_palette(self) -> None:
        """Hide the command palette."""
        try:
            palette = self.query_one("#command-palette", Vertical)
            palette.display = False
        except Exception:
            pass

    def on_click(self, event) -> None:
        """Handle clicks on command palette items."""
        widget = event.widget if hasattr(event, "widget") else None
        if widget and hasattr(widget, "data") and isinstance(getattr(widget, "data", None), str):
            cmd_name = widget.data
            if cmd_name.startswith("/"):
                text_area = self.query_one("#chat-input", TextArea)
                text_area.clear()
                text_area.insert(cmd_name)
                self._hide_command_palette()
                self._submit_input()

    def set_agent(self, agent_name: str, agent_info: AgentInfo | None = None) -> None:
        """Switch the active agent mid-session."""
        self.agent = agent_name
        self._agent_info = agent_info
        self.session_id = None  # reset session for new agent

        # Update header
        agent_label = f"  agent: {self.agent}" if self.agent else ""
        self.query_one("#chat-title", Label).update(f"Chat with Claude Code{agent_label}")

        # Update settings from agent info
        if agent_info:
            self._session_settings.permission_mode = agent_info.permission_mode or ""
            self._session_settings.model = agent_info.model or ""
            self._session_settings.effort = agent_info.effort or "medium"
            self._update_settings_summary()

    def action_go_back(self) -> None:
        if self._is_streaming:
            self._stop_streaming()
        # Only navigate back if not the root screen
        if len(self.app.screen_stack) > 2:
            self.post_message(self.GoBack())
