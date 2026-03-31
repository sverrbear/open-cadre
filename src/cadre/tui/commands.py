"""Slash command registry for the chat-first TUI."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cadre.tui.screens.chat_screen import ChatScreen


@dataclass
class SlashCommand:
    """A slash command with name, description, and async handler."""

    name: str
    description: str
    handler: Callable[[ChatScreen, str], Awaitable[None]]


async def _handle_init(screen: ChatScreen, _args: str) -> None:
    """Install the lead agent and set it as active."""
    from cadre.agents.manager import install_preset, load_agent

    log = screen.query_one("#chat-log")

    try:
        install_preset("lead")
        agent_info = load_agent("lead")
        screen.set_agent("lead", agent_info)
        log.write(
            "[bold green]\u2713 Installed lead agent.[/bold green]\n"
            "[dim]You're now chatting with the lead. "
            "Type [bold]/explore[/bold] to have it analyze your repo "
            "and help you build a team, or just start chatting.[/dim]\n"
        )
    except Exception as e:
        log.write(f"[bold red]Error installing lead agent:[/bold red] {e}\n")


async def _handle_explore(screen: ChatScreen, _args: str) -> None:
    """Launch collaborative team-building with the lead agent."""
    from cadre.agents.manager import list_agents, load_agent

    log = screen.query_one("#chat-log")

    agents = list_agents()
    lead = next((a for a in agents if a.name == "lead"), None)
    if not lead:
        log.write(
            "[bold yellow]Lead agent not installed.[/bold yellow]\n"
            "[dim]Run [bold]/init[/bold] first to set up your lead agent.[/dim]\n"
        )
        return

    # Ensure we're chatting with the lead
    if screen.agent != "lead":
        agent_info = load_agent("lead")
        screen.set_agent("lead", agent_info)

    prompt = (
        "I'd like you to help me build my team. Here's what I need you to do:\n\n"
        "1. First, explore this repository — read the CLAUDE.md file, check the .claude/ "
        "directory, and analyze the codebase structure, tech stack, and development patterns.\n\n"
        "2. Then, ask me questions about how I like to work — my strengths, weaknesses, "
        "what I want help with most, and how I prefer to collaborate with AI agents.\n\n"
        "IMPORTANT: Ask me questions ONE AT A TIME. For each question, provide 3-4 "
        "numbered answer options that I can choose from. Format them like:\n"
        "1. Option one\n"
        "2. Option two\n"
        "3. Option three\n\n"
        "Wait for my response before asking the next question.\n\n"
        "3. Based on the repo analysis AND my responses, recommend a team composition. "
        "We'll decide together which agents to create, what their roles should be, "
        "and how they should be configured.\n\n"
        "4. Once we agree on a team, help me create the agent files.\n\n"
        "Let's start — explore the repo and then ask me your first question."
    )

    log.write("\n[bold #cdd6f4]You:[/bold #cdd6f4] /explore\n")
    screen._set_streaming(True)
    screen._thinking = True
    log.write("[dim italic #89b4fa]Claude is thinking...[/dim italic #89b4fa]")
    screen._do_send(prompt)


async def _handle_agents(screen: ChatScreen, _args: str) -> None:
    """List installed agents."""
    from cadre.agents.manager import list_agents

    log = screen.query_one("#chat-log")
    agents = list_agents()

    if not agents:
        log.write(
            "[bold yellow]No agents installed.[/bold yellow]\n"
            "[dim]Run [bold]/init[/bold] to get started.[/dim]\n"
        )
        return

    log.write("[bold]Installed agents:[/bold]")
    for agent in agents:
        model = f"[dim]({agent.model})[/dim]" if agent.model else ""
        log.write(f"  [bold #89b4fa]{agent.name}[/bold #89b4fa] {model} — {agent.description}")
    log.write("")


async def _handle_settings(screen: ChatScreen, _args: str) -> None:
    """Open the session settings modal."""
    screen.action_open_settings()


async def _handle_dashboard(screen: ChatScreen, _args: str) -> None:
    """Open the dashboard view."""
    screen.post_message(screen.OpenDashboard())


async def _handle_clear(screen: ChatScreen, _args: str) -> None:
    """Clear chat history and reset the conversation context."""
    from textual.widgets import RichLog

    log = screen.query_one("#chat-log", RichLog)
    log.clear()
    screen.session_id = None
    screen._total_input_tokens = 0
    screen._total_output_tokens = 0
    screen._last_response_text = ""
    screen._shown_claude_header = False
    log.write("[dim]Context cleared. Starting a fresh conversation.[/dim]\n")


async def _handle_team(screen: ChatScreen, args: str) -> None:
    """Launch team chat mode."""
    from cadre.agents.manager import list_agents
    from cadre.presets import TEAM_PRESETS
    from cadre.tui.screens.team_chat_screen import TeamChatScreen

    log = screen.query_one("#chat-log")
    team_name = args.strip() or "full"

    if team_name not in TEAM_PRESETS:
        available = ", ".join(TEAM_PRESETS.keys())
        log.write(
            f"[bold red]Unknown team preset '{team_name}'.[/bold red]\n"
            f"[dim]Available: {available}[/dim]\n"
        )
        return

    agents = list_agents()
    team_agent_names = TEAM_PRESETS[team_name]
    team_agents = [a for a in agents if a.name in team_agent_names]

    if not team_agents:
        missing = set(team_agent_names) - {a.name for a in agents}
        log.write(
            f"[bold yellow]Missing agents: {', '.join(missing)}[/bold yellow]\n"
            "[dim]Run [bold]/init[/bold] or [bold]opencadre init[/bold] first.[/dim]\n"
        )
        return

    if len(team_agents) < len(team_agent_names):
        missing = set(team_agent_names) - {a.name for a in team_agents}
        found = [a.name for a in team_agents]
        log.write(
            f"[dim]Note: missing {', '.join(missing)}. Starting with: {', '.join(found)}[/dim]\n"
        )

    screen.app.push_screen(TeamChatScreen(team_name=team_name, agents=team_agents))


async def _handle_help(screen: ChatScreen, _args: str) -> None:
    """Show all available commands."""
    log = screen.query_one("#chat-log")
    log.write("[bold]Available commands:[/bold]")
    for cmd in COMMANDS.values():
        log.write(f"  [bold #89b4fa]{cmd.name:<12}[/bold #89b4fa] {cmd.description}")
    log.write("")


COMMANDS: dict[str, SlashCommand] = {
    "/init": SlashCommand("/init", "Set up your lead agent", _handle_init),
    "/explore": SlashCommand("/explore", "Analyze your repo and build a team", _handle_explore),
    "/agents": SlashCommand("/agents", "List installed agents", _handle_agents),
    "/settings": SlashCommand("/settings", "Open session settings", _handle_settings),
    "/clear": SlashCommand("/clear", "Clear context and start fresh", _handle_clear),
    "/dashboard": SlashCommand("/dashboard", "Open the dashboard view", _handle_dashboard),
    "/team": SlashCommand("/team", "Start team chat (full/dev/review)", _handle_team),
    "/help": SlashCommand("/help", "Show available commands", _handle_help),
}


async def dispatch(screen: ChatScreen, text: str) -> bool:
    """Dispatch a slash command. Returns True if handled."""
    parts = text.strip().split(maxsplit=1)
    cmd_name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    command = COMMANDS.get(cmd_name)
    if command:
        await command.handler(screen, args)
        return True
    return False
