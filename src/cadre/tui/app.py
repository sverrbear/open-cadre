"""Main Textual application for OpenCadre — Claude Code team management frontend."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual.app import App
from textual.binding import Binding

from cadre.agents.manager import check_claude_auth, check_claude_cli, list_agents
from cadre.config import CadreConfig
from cadre.tui.screens.chat_screen import ChatScreen
from cadre.tui.themes.registry import ThemeRegistry


class CadreTUI(App):
    """OpenCadre — Claude Code team management frontend."""

    TITLE = "OpenCadre"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+p", "open_settings", "Settings", show=True),
        Binding("escape", "focus_input", "Focus input", show=False),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(self, config: CadreConfig, launch_team: str = "") -> None:
        self.config = config
        self.theme_registry = ThemeRegistry(project_path=Path.cwd())
        self.main_screen = None
        self._active_agents: set[str] = set()
        self._launch_team = launch_team

        theme_name = config.ui.theme
        self._css_path = [self.theme_registry.get_css_path(theme_name)]

        super().__init__()

    @property
    def CSS_PATH(self) -> list[Path]:  # noqa: N802
        """Dynamic CSS path based on theme."""
        return self._css_path

    def on_mount(self) -> None:
        """Push the chat screen (or team chat) as the default view."""
        agents = list_agents()

        # Launch directly into team chat if requested
        if self._launch_team:
            self._start_team_chat(self._launch_team, agents)
            self.call_after_refresh(self._check_claude)
            return

        show_welcome = len(agents) == 0

        # Default to lead agent if it exists
        lead = next((a for a in agents if a.name == "lead"), None)
        agent_name = lead.name if lead else ""
        agent_info = lead if lead else None

        self.push_screen(
            ChatScreen(
                agent=agent_name,
                agent_info=agent_info,
                show_welcome=show_welcome,
            )
        )

        self.call_after_refresh(self._check_claude)

    def _start_team_chat(self, team_name: str, agents: list | None = None) -> None:
        """Launch team chat screen for the given team preset."""
        from cadre.presets import TEAM_PRESETS
        from cadre.tui.screens.team_chat_screen import TeamChatScreen

        if agents is None:
            agents = list_agents()

        team_agent_names = TEAM_PRESETS.get(team_name, [])
        team_agents = [a for a in agents if a.name in team_agent_names]

        if not team_agents:
            # Fall back to regular chat if no team agents found
            self.push_screen(ChatScreen(show_welcome=True))
            return

        self.push_screen(TeamChatScreen(team_name=team_name, agents=team_agents))

    def _check_claude(self) -> None:
        """Check if claude CLI is available and log to chat."""
        available, version_or_error = check_claude_cli()
        if not available:
            try:
                from textual.widgets import RichLog

                log = self.screen.query_one("#chat-log", RichLog)
                log.write(
                    f"[bold red]Claude Code not found:[/bold red] {version_or_error}\n"
                    "[dim]Install: npm install -g @anthropic-ai/claude-code[/dim]\n"
                )
            except Exception:
                pass

    def on_main_screen_launch_claude(self, event) -> None:
        """Handle launch claude request from dashboard — check auth, then open chat."""
        auth = check_claude_auth()
        if not auth.logged_in:
            from cadre.tui.screens.auth_dialog import AuthRequiredDialog

            self.push_screen(AuthRequiredDialog(error=auth.error))
            return

        if event.agent:
            self._active_agents.add(event.agent)
        self.push_screen(ChatScreen(agent=event.agent, agent_info=event.agent_info))

    def on_team_chat_screen_go_back(self, _event) -> None:
        """Handle team chat screen back navigation."""
        self.pop_screen()

    def on_main_screen_launch_team(self, event) -> None:
        """Handle team launch from dashboard."""
        self._start_team_chat(event.team_name)

    def on_chat_screen_go_back(self, _event) -> None:
        """Handle chat screen back navigation."""
        screen = self.screen
        if hasattr(screen, "agent") and screen.agent:
            self._active_agents.discard(screen.agent)
        self.pop_screen()

    def on_chat_screen_open_dashboard(self, _event) -> None:
        """Handle dashboard request from chat — push the main screen."""
        from cadre.tui.screens.main_screen import MainScreen

        agents = list_agents()
        self.main_screen = MainScreen(
            config=self.config, agents=agents, active_agents=self._active_agents
        )
        self.push_screen(self.main_screen)

    def on_main_screen_agents_changed(self, _event) -> None:
        """Refresh the main screen when agents change."""
        from cadre.tui.screens.main_screen import MainScreen

        agents = list_agents()
        self.pop_screen()
        self.main_screen = MainScreen(
            config=self.config, agents=agents, active_agents=self._active_agents
        )
        self.push_screen(self.main_screen)

    def action_open_settings(self) -> None:
        """Open settings screen."""
        from cadre.tui.screens.settings_screen import SettingsScreen

        themes = self.theme_registry.list_themes()
        self.push_screen(
            SettingsScreen(config=self.config, available_themes=themes),
            callback=self._on_settings_result,
        )

    def _on_settings_result(self, result: CadreConfig | None) -> None:
        """Handle settings screen result."""
        if result is None:
            return

        old_theme = self.config.ui.theme
        self.config = result

        if result.ui.theme != old_theme:
            new_css_path = self.theme_registry.get_css_path(result.ui.theme)
            self._css_path = [new_css_path]
            self.stylesheet.read(new_css_path)
            self.stylesheet.reparse()
            self.refresh_css()

        import contextlib

        with contextlib.suppress(Exception):
            result.save()

    def action_focus_input(self) -> None:
        """Focus the input bar on the active screen."""
        import contextlib

        from textual.widgets import TextArea

        with contextlib.suppress(Exception):
            self.screen.query_one("#chat-input", TextArea).focus()

    def on_unmount(self) -> None:
        """Persist config on exit."""
        import contextlib

        with contextlib.suppress(Exception):
            self.config.save()
