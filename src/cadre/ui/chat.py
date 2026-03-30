"""Chat display and input handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from cadre.agents.base import AgentEvent

if TYPE_CHECKING:
    from cadre.orchestrator.router import MessageRouter


# Slash command definitions: (description, handler_method_name)
SLASH_COMMANDS = {
    "/help": "Show available commands",
    "/status": "Show team and agent status",
    "/explore": "Explore codebase and update agent context",
    "/models": "Show model benchmarks and recommendations",
    "/doctor": "Check prerequisites and configuration",
    "/config": "Show current configuration",
    "/workflow list": "List available workflows",
    "/workflow run": "Run a workflow: /workflow run <name> <request>",
    "/quit": "Exit the chat",
}


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
                "[dim]@agent to direct message │ /help for commands[/dim]",
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

            if user_input.startswith("/"):
                if self._handle_slash_command(user_input):
                    break  # /quit was called
                continue

            # Route message to agent
            self.console.print()
            async for event in self.router.route(user_input):
                self.display_event(event)

    def _handle_slash_command(self, command: str) -> bool:
        """Handle a slash command. Returns True if chat should exit."""
        cmd = command.strip()

        if cmd in ("/quit", "/exit", "/q"):
            return True

        if cmd == "/help":
            self._cmd_help()
        elif cmd == "/status":
            self._cmd_status()
        elif cmd == "/explore":
            self._cmd_explore()
        elif cmd == "/models":
            self._cmd_models()
        elif cmd == "/doctor":
            self._cmd_doctor()
        elif cmd == "/config":
            self._cmd_config()
        elif cmd == "/workflow list":
            self._cmd_workflow_list()
        elif cmd.startswith("/workflow run "):
            self._cmd_workflow_run(cmd[len("/workflow run ") :])
        else:
            self.console.print(
                f"  [yellow]Unknown command: {cmd}[/yellow]\n"
                "  Type [bold]/help[/bold] for available commands."
            )

        return False

    def _cmd_help(self) -> None:
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column(style="dim")
        for cmd, desc in SLASH_COMMANDS.items():
            table.add_row(cmd, desc)
        self.console.print()
        self.console.print(table)

    def _cmd_status(self) -> None:
        from cadre.ui.status import render_status

        render_status(self.router.team, self.console)

    def _cmd_explore(self) -> None:
        from cadre.explore import run_explore

        self.console.print()
        run_explore()
        self.console.print()

    def _cmd_models(self) -> None:
        from cadre.benchmarks.data import BenchmarkData

        self.console.print()
        bench = BenchmarkData()
        bench.render_table(self.console)
        self.console.print()
        bench.render_strategies(self.console)

    def _cmd_doctor(self) -> None:
        import os
        import shutil
        import sys

        from cadre.config import CADRE_DIR

        self.console.print("\n[bold]OpenCadre Doctor[/bold]\n")

        py_version = sys.version_info
        if py_version >= (3, 10):
            self.console.print(
                f"  [green]✓[/green] Python "
                f"{py_version.major}.{py_version.minor}.{py_version.micro}"
            )
        else:
            self.console.print(
                f"  [red]✗[/red] Python {py_version.major}.{py_version.minor} (need ≥3.10)"
            )

        from pathlib import Path

        cadre_dir = Path.cwd() / CADRE_DIR
        if cadre_dir.exists():
            self.console.print(f"  [green]✓[/green] {CADRE_DIR}/ found")
        else:
            self.console.print(f"  [yellow]![/yellow] {CADRE_DIR}/ not found — run `cadre init`")

        provider_vars = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        for provider, env_var in provider_vars.items():
            if os.environ.get(env_var):
                self.console.print(f"  [green]✓[/green] {provider} ({env_var})")

        for tool_name in ["git", "dbt", "rg", "sqlfluff", "ruff"]:
            if shutil.which(tool_name):
                self.console.print(f"  [green]✓[/green] {tool_name}")
        self.console.print()

    def _cmd_config(self) -> None:
        from pathlib import Path

        from cadre.config import CadreConfig

        self.console.print("\n[bold]Current Configuration[/bold]\n")
        try:
            cfg = CadreConfig.load(Path.cwd())
        except Exception as e:
            self.console.print(f"  [red]Error loading config: {e}[/red]")
            return

        self.console.print(f"  Project:   {cfg.project.name} ({cfg.project.type})")
        self.console.print(f"  Warehouse: {cfg.project.warehouse}")
        self.console.print(f"  Mode:      {cfg.team.mode}")
        self.console.print()
        self.console.print("  [bold]Agents:[/bold]")
        for name, agent_cfg in cfg.team.agents.items():
            status = "[green]enabled[/green]" if agent_cfg.enabled else "[red]disabled[/red]"
            self.console.print(f"    {name:12s} {agent_cfg.model:40s} {status}")
        self.console.print()

    def _cmd_workflow_list(self) -> None:
        from cadre.workflows.presets import PRESET_WORKFLOWS

        self.console.print("\n[bold]Available Workflows[/bold]\n")
        for name, wf in PRESET_WORKFLOWS.items():
            self.console.print(f"  [cyan]{name}[/cyan] — {wf.description}")
        self.console.print()

    def _cmd_workflow_run(self, args: str) -> None:
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            self.console.print("  [yellow]Usage: /workflow run <name> <request>[/yellow]")
            return

        name, request = parts
        from cadre.workflows.presets import PRESET_WORKFLOWS

        if name not in PRESET_WORKFLOWS:
            self.console.print(
                f"  [red]Workflow '{name}' not found.[/red] "
                f"Available: {', '.join(PRESET_WORKFLOWS.keys())}"
            )
            return

        self.console.print(f"\n  [blue]Running workflow: {name}[/blue]")
        self.console.print(f"  [dim]{request}[/dim]\n")

        import asyncio

        from cadre.workflows.engine import WorkflowEngine

        engine = WorkflowEngine(team=self.router.team, router=self.router)
        wf = PRESET_WORKFLOWS[name]

        async def _run():
            async for event in engine.run(wf, request):
                if hasattr(event, "tool"):
                    self.display_event(event)
                else:
                    if event.type == "step_start":
                        self.console.print(f"\n[bold]→ {event.agent}[/bold]: {event.instruction}\n")
                    elif event.type == "approval_needed":
                        from rich.prompt import Confirm

                        if not Confirm.ask("[magenta]Approve and continue?[/magenta]"):
                            self.console.print("[yellow]Workflow cancelled.[/yellow]")
                            return
                    elif event.type == "workflow_complete":
                        self.console.print(f"\n[green]✓ {event.content}[/green]")

        asyncio.run(_run())


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
