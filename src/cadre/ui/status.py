"""Team status display."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from cadre.orchestrator.team import Team


def render_status(team: "Team", console: Console | None = None) -> None:
    """Render team status as a Rich table."""
    if console is None:
        console = Console()

    table = Table(title="Team Status", show_header=True, header_style="bold")
    table.add_column("Agent", style="cyan")
    table.add_column("Model", style="dim")
    table.add_column("Status")

    status_icons = {
        "idle": "[green]● idle[/green]",
        "thinking": "[yellow]◉ thinking...[/yellow]",
        "tool_calling": "[blue]◉ calling tools...[/blue]",
        "waiting_for_approval": "[magenta]⏸ waiting for approval[/magenta]",
        "error": "[red]✗ error[/red]",
    }

    for name, info in team.get_status().items():
        status_display = status_icons.get(info["status"], info["status"])
        table.add_row(name.capitalize(), info["model"], status_display)

    console.print(table)
