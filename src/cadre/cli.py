"""CLI entry point — all `cadre` / `opencadre` commands."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

from cadre import __version__

console = Console()


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="opencadre")
@click.pass_context
def main(ctx):
    """OpenCadre — Claude Code team management frontend."""
    if ctx.invoked_subcommand is None:
        _launch_tui()


@main.command()
@click.argument("team_preset", default="full")
def init(team_preset: str):
    """Install a team preset into .claude/agents/.

    TEAM_PRESET: full (default), solo, dev, or review
    """
    from cadre.agents.manager import install_team
    from cadre.presets import TEAM_PRESETS

    if team_preset not in TEAM_PRESETS:
        console.print(
            f"[red]Unknown preset '{team_preset}'.[/red] "
            f"Available: {', '.join(TEAM_PRESETS.keys())}"
        )
        return

    agents = install_team(team_preset)
    console.print(f"[green]Installed {len(agents)} agents:[/green]")
    for agent in agents:
        console.print(f"  [cyan]{agent.name}[/cyan] — {agent.description[:60]}")
    console.print("\n[dim]Files written to .claude/agents/[/dim]")
    console.print("[dim]Run [bold]opencadre[/bold] to manage your team.[/dim]")


@main.command()
def agents():
    """List installed agents from .claude/agents/."""
    from cadre.agents.manager import list_agents

    agent_list = list_agents()
    if not agent_list:
        console.print("[yellow]No agents found.[/yellow]")
        console.print("Run [bold]opencadre init[/bold] to install a team.")
        return

    console.print(f"[bold]{len(agent_list)} agents[/bold]\n")
    for agent in agent_list:
        model = agent.model or "default"
        tools = ", ".join(agent.tools[:4])
        if len(agent.tools) > 4:
            tools += f" +{len(agent.tools) - 4}"
        console.print(f"  [cyan]{agent.name:12s}[/cyan] model={model:8s} tools=[{tools}]")
        if agent.description:
            desc = agent.description[:70]
            console.print(f"  {'':12s} [dim]{desc}[/dim]")
    console.print("\n[dim]Agent files: .claude/agents/*.md[/dim]")


@main.command()
@click.argument("agent", required=False)
def chat(agent: str | None):
    """Launch Claude Code (optionally with a specific agent)."""
    from cadre.agents.manager import check_claude_cli

    available, version_or_error = check_claude_cli()
    if not available:
        console.print(f"[red]Claude Code not found:[/red] {version_or_error}")
        console.print("[dim]Install: npm install -g @anthropic-ai/claude-code[/dim]")
        return

    cmd = ["claude"]
    if agent:
        cmd.extend(["--agent", agent])

    console.print(f"[dim]Launching Claude Code...{f' (agent: {agent})' if agent else ''}[/dim]\n")
    subprocess.run(cmd)


@main.command()
def doctor():
    """Check prerequisites for OpenCadre."""

    from cadre.agents.manager import check_claude_cli, list_agents

    console.print("[bold]OpenCadre Doctor[/bold]\n")

    # Python version
    py = sys.version_info
    if py >= (3, 10):
        console.print(f"  [green]OK[/green] Python {py.major}.{py.minor}.{py.micro}")
    else:
        console.print(f"  [red]FAIL[/red] Python {py.major}.{py.minor} (need >= 3.10)")

    # Claude CLI
    available, version_or_error = check_claude_cli()
    if available:
        console.print(f"  [green]OK[/green] Claude Code {version_or_error}")
    else:
        console.print(f"  [red]FAIL[/red] {version_or_error}")
        console.print("         Install: npm install -g @anthropic-ai/claude-code")

    # .claude/agents/
    agents = list_agents()
    if agents:
        console.print(f"  [green]OK[/green] {len(agents)} agents in .claude/agents/")
    else:
        console.print("  [yellow]WARN[/yellow] No agents — run `opencadre init`")

    # .claude directory
    claude_dir = Path.cwd() / ".claude"
    if claude_dir.exists():
        console.print("  [green]OK[/green] .claude/ directory")
    else:
        console.print("  [yellow]WARN[/yellow] .claude/ not found")

    console.print()


@main.command()
@click.argument("team_preset", default="full")
def team(team_preset: str):
    """Launch team chat in the TUI.

    TEAM_PRESET: full (default), dev, or review
    """
    from cadre.presets import TEAM_PRESETS

    if team_preset not in TEAM_PRESETS:
        console.print(
            f"[red]Unknown team preset '{team_preset}'.[/red] "
            f"Available: {', '.join(TEAM_PRESETS.keys())}"
        )
        return

    from cadre.tui.app import CadreTUI

    cfg = _load_config()
    app = CadreTUI(cfg, launch_team=team_preset)
    app.run()


@main.command()
def up():
    """Start the OpenCadre TUI."""
    _launch_tui()


def _launch_tui() -> None:
    """Launch the Textual TUI."""
    from cadre.tui.app import CadreTUI

    cfg = _load_config()
    app = CadreTUI(cfg)
    app.run()


def _load_config():
    """Load config, returning defaults if none exists."""
    from cadre.config import CadreConfig

    try:
        return CadreConfig.load()
    except Exception:
        return CadreConfig()
