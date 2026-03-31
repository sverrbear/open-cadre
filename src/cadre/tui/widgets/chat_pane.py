"""Chat pane widget — scrollable message log for one agent conversation."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import RichLog


class ChatPane(Widget):
    """Displays a scrollable chat log for a single agent or the team view."""

    def __init__(self, agent_name: str = "team", **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_name = agent_name
        self._streaming_buffer = ""

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True, wrap=True, auto_scroll=True)

    @property
    def log(self) -> RichLog:
        return self.query_one(RichLog)

    def append_user_message(self, text: str) -> None:
        """Display a user message."""
        msg = Text()
        msg.append("\nYou", style="bold green")
        msg.append(f"\n{text}\n")
        self.log.write(msg)

    def append_agent_prefix(self, agent_name: str) -> None:
        """Display the agent name prefix for a new response."""
        msg = Text()
        msg.append(f"\n{agent_name}", style="bold cyan")
        self.log.write(msg)

    def append_content_delta(self, content: str) -> None:
        """Handle streaming content — buffer and flush on newlines."""
        self._streaming_buffer += content
        if "\n" in self._streaming_buffer:
            lines = self._streaming_buffer.split("\n")
            # Write all complete lines
            for line in lines[:-1]:
                if line:
                    self.log.write(Text(line))
            # Keep the incomplete last part in the buffer
            self._streaming_buffer = lines[-1]

    def flush_stream(self) -> None:
        """Flush any remaining streaming buffer."""
        if self._streaming_buffer:
            self.log.write(Text(self._streaming_buffer))
            self._streaming_buffer = ""
        self.log.write(Text(""))  # blank line after response

    def append_tool_call(self, tool: str, args: dict) -> None:
        """Display a tool call."""
        args_str = _format_args(args)
        msg = Text()
        msg.append(f"  → {tool}({args_str})", style="dim")
        self.log.write(msg)

    def append_tool_result(self, tool: str, result: str) -> None:
        """Display a tool result."""
        preview = result[:200] + "..." if len(result) > 200 else result
        msg = Text()
        msg.append(f"  ← {preview}", style="dim")
        self.log.write(msg)

    def append_error(self, content: str) -> None:
        """Display an error with optional hint line."""
        for line in content.split("\n"):
            msg = Text()
            if line.strip().startswith("Hint:"):
                msg.append(f"  {line.strip()}", style="yellow")
            else:
                msg.append(f"  ✗ {line}", style="bold red")
            self.log.write(msg)

    def append_confirmation_needed(self, tool: str) -> None:
        """Display a confirmation request."""
        msg = Text()
        msg.append(f"  ⏸ {tool} requires approval", style="magenta")
        self.log.write(msg)

    def clear(self) -> None:
        """Clear the chat log and streaming buffer."""
        self._streaming_buffer = ""
        self.log.clear()


def _format_args(args: dict) -> str:
    """Format tool call arguments for display."""
    if not args:
        return ""
    parts = []
    for k, v in args.items():
        val = str(v)
        if len(val) > 50:
            val = val[:50] + "..."
        parts.append(f"{k}={val}")
    return ", ".join(parts)
