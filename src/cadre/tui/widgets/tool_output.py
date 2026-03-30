"""Tool output panel — collapsible panel showing tool calls and results."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, RichLog


class ToolOutputPanel(Widget):
    """Collapsible panel showing tool call/result stream."""

    def compose(self) -> ComposeResult:
        yield Label(" [bold dim]Tool Output[/bold dim]", id="tool-header")
        yield RichLog(highlight=True, markup=True, wrap=True, auto_scroll=True)

    @property
    def log(self) -> RichLog:
        return self.query_one(RichLog)

    def append_tool_call(self, agent_name: str, tool: str, args: dict) -> None:
        """Log a tool call."""
        args_str = _format_args(args)
        msg = Text()
        msg.append(f"[{agent_name}] ", style="bold cyan")
        msg.append(f"→ {tool}", style="yellow")
        msg.append(f"({args_str})", style="dim")
        self.log.write(msg)

    def append_tool_result(self, agent_name: str, tool: str, result: str) -> None:
        """Log a tool result."""
        preview = result[:300] + "..." if len(result) > 300 else result
        msg = Text()
        msg.append(f"[{agent_name}] ", style="bold cyan")
        msg.append(f"← {tool}: ", style="dim green")
        msg.append(preview, style="dim")
        self.log.write(msg)


def _format_args(args: dict) -> str:
    if not args:
        return ""
    parts = []
    for k, v in args.items():
        val = str(v)
        if len(val) > 50:
            val = val[:50] + "..."
        parts.append(f"{k}={val}")
    return ", ".join(parts)
