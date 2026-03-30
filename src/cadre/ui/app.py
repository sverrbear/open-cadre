"""Main application — sets up team, router, and runs the chat loop."""

from __future__ import annotations

import asyncio

from rich.console import Console
from rich.panel import Panel

from cadre import __version__
from cadre.config import CadreConfig
from cadre.orchestrator.router import MessageRouter
from cadre.orchestrator.team import Team
from cadre.ui.chat import ChatUI
from cadre.ui.status import render_status


class App:
    """Main OpenCadre application."""

    def __init__(self, config: CadreConfig) -> None:
        self.config = config
        self.console = Console()
        self.team = Team(config=config)
        self.router: MessageRouter | None = None
        self.chat_ui: ChatUI | None = None

    def setup(self) -> None:
        """Initialize the team and UI."""
        self.team.setup()
        self.router = MessageRouter(team=self.team)
        self.chat_ui = ChatUI(router=self.router, console=self.console)

    def show_header(self) -> None:
        """Display the application header."""
        project = self.config.project
        header = f"[bold]OpenCadre v{__version__}[/bold] — {project.name}"
        if project.type == "dbt":
            header += f" ({project.warehouse} + dbt)"
        self.console.print(Panel(header, style="blue"))
        self.console.print()

    async def run(self) -> None:
        """Run the main application loop."""
        self.show_header()
        render_status(self.team, self.console)

        if self.chat_ui:
            await self.chat_ui.run_chat_loop()

        self.team.shutdown()
        self.console.print("\n[dim]Goodbye![/dim]")

    def run_sync(self) -> None:
        """Run the application synchronously."""
        self.setup()
        asyncio.run(self.run())
