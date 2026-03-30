"""Chat display and input handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from cadre.agents.base import AgentEvent

if TYPE_CHECKING:
    from cadre.orchestrator.router import MessageRouter


class ChatUI:
    """Terminal chat interface for interacting with agents."""

    def __init__(self, router: MessageRouter, console: Console | None = None) -> None:
        self.router = router
        self.console = console or Console()

    def display_event(self, event: AgentEvent) -> None:
        """Display an agent event in the terminal."""
        if event.type == "content_delta":
            self.console.print(event.content, end="")
        elif event.type == "response":
            self.console.print()  # Newline after streaming
        elif event.type == "tool_call":
            self.console.print(f"  [dim]→ {event.tool}({_format_args(event.args)})[/dim]")
        elif event.type == "tool_result":
            result_preview = event.result[:200] + "..." if len(event.result) > 200 else event.result
            self.console.print(f"  [dim]  ← {result_preview}[/dim]")
        elif event.type == "confirmation_needed":
            self.console.print(f"  [magenta]⏸ {event.tool} requires approval[/magenta]")
        elif event.type == "error":
            self.console.print(f"  [red]✗ {event.content}[/red]")
        elif event.type == "status":
            pass  # Status updates are shown in the status bar

    async def run_chat_loop(self) -> None:
        """Run the interactive chat loop."""
        self.console.print(
            Panel(
                "[bold]OpenCadre Chat[/bold]\n"
                "[dim]@agent to direct message │ /status │ /workflow │ /quit[/dim]",
                style="blue",
            )
        )

        while True:
            try:
                user_input = Prompt.ask("\n[bold green]You[/bold green]")
            except (EOFError, KeyboardInterrupt):
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            if user_input in ("/quit", "/exit", "/q"):
                break

            if user_input == "/status":
                from cadre.ui.status import render_status

                render_status(self.router.team, self.console)
                continue

            # Route message to agent
            self.console.print()
            async for event in self.router.route(user_input):
                self.display_event(event)


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
