"""Main Textual application for OpenCadre."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual.app import App
from textual.binding import Binding

from cadre.config import CadreConfig
from cadre.orchestrator.router import MessageRouter
from cadre.orchestrator.team import Team
from cadre.tui.bridge import AgentEventMessage, EventBridge
from cadre.tui.screens.main_screen import MainScreen
from cadre.tui.themes.registry import ThemeRegistry
from cadre.tui.widgets.agent_tabs import AgentTabs
from cadre.tui.widgets.input_bar import InputBar
from cadre.tui.widgets.status_sidebar import StatusSidebar
from cadre.tui.widgets.tool_output import ToolOutputPanel


class CadreTUI(App):
    """OpenCadre multi-window terminal UI."""

    TITLE = "OpenCadre"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+b", "toggle_sidebar", "Toggle sidebar", show=True),
        Binding("ctrl+t", "toggle_tools", "Toggle tools", show=True),
        Binding("ctrl+p", "open_settings", "Settings", show=True),
        Binding("escape", "focus_input", "Focus input", show=False),
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+0", "switch_tab('team')", "Team tab", show=False),
        Binding("ctrl+1", "switch_tab_index(0)", "Tab 1", show=False),
        Binding("ctrl+2", "switch_tab_index(1)", "Tab 2", show=False),
        Binding("ctrl+3", "switch_tab_index(2)", "Tab 3", show=False),
        Binding("ctrl+4", "switch_tab_index(3)", "Tab 4", show=False),
    ]

    def __init__(self, config: CadreConfig) -> None:
        super().__init__()
        self.config = config
        self.team = Team(config=config)
        self.router: MessageRouter
        self.bridge: EventBridge
        self.theme_registry = ThemeRegistry(project_path=Path.cwd())

        # Set CSS path based on configured theme
        theme_name = config.ui.theme
        self.css_path = [self.theme_registry.get_css_path(theme_name)]

    @property
    def CSS_PATH(self) -> list[Path]:  # noqa: N802
        """Dynamic CSS path based on theme."""
        return self.css_path

    def on_mount(self) -> None:
        """Set up the team and push the main screen."""
        self.team.setup()
        self.router = MessageRouter(team=self.team)
        self.bridge = EventBridge(app=self, router=self.router)
        self.push_screen(MainScreen(config=self.config, team=self.team))

        # Apply initial UI config
        self.call_after_refresh(self._apply_ui_config)

    def _apply_ui_config(self) -> None:
        """Apply UI config settings to widgets."""
        ui = self.config.ui
        try:
            sidebar = self.query_one(StatusSidebar)
            sidebar.display = ui.sidebar_visible
        except Exception:
            pass
        try:
            tool_panel = self.query_one(ToolOutputPanel)
            tool_panel.display = ui.tool_panel_visible
        except Exception:
            pass

    def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
        """Handle user input submission."""
        message = event.value

        # Handle slash commands
        if message.startswith("/"):
            self._handle_slash_command(message)
            return

        # Show user message in the appropriate pane
        agent_tabs = self.query_one(AgentTabs)
        target = self.bridge._resolve_target(message)

        # Show in agent-specific pane
        agent_pane = agent_tabs.get_chat_pane(target)
        if agent_pane:
            agent_pane.append_user_message(message)

        # Also show in team pane
        team_pane = agent_tabs.get_team_pane()
        if team_pane and target != "team":
            team_pane.append_user_message(message)

        # Switch to agent tab if explicitly mentioned
        if message.strip().startswith("@"):
            agent_tabs.switch_to_agent(target)

        # Send to agents via bridge (in a worker to avoid blocking)
        self.run_worker(self.bridge.send_message(message), exclusive=False)

    def on_agent_event_message(self, msg: AgentEventMessage) -> None:
        """Handle agent events from the bridge."""
        event = msg.event
        agent_name = msg.agent_name
        agent_tabs = self.query_one(AgentTabs)
        tool_panel = self.query_one(ToolOutputPanel)
        sidebar = self.query_one(StatusSidebar)

        # Get the target panes
        agent_pane = agent_tabs.get_chat_pane(agent_name)
        team_pane = agent_tabs.get_team_pane()

        if event.type == "response_start":
            # Show agent name prefix before streaming begins
            if agent_pane:
                agent_pane.append_agent_prefix(agent_name)
            if team_pane and agent_name != "team":
                team_pane.append_agent_prefix(agent_name)

        elif event.type == "status":
            sidebar.update_agent_status(agent_name, event.content)

        elif event.type == "content_delta":
            if agent_pane:
                agent_pane.append_content_delta(event.content)
            if team_pane and agent_name != "team":
                team_pane.append_content_delta(event.content)

        elif event.type == "response":
            if agent_pane:
                agent_pane.flush_stream()
            if team_pane and agent_name != "team":
                team_pane.flush_stream()

        elif event.type == "tool_call":
            tool_panel.append_tool_call(agent_name, event.tool, event.args)
            if agent_pane:
                agent_pane.append_tool_call(event.tool, event.args)
            if team_pane and agent_name != "team":
                team_pane.append_tool_call(event.tool, event.args)

        elif event.type == "tool_result":
            tool_panel.append_tool_result(agent_name, event.tool, event.result)
            if agent_pane:
                agent_pane.append_tool_result(event.tool, event.result)
            if team_pane and agent_name != "team":
                team_pane.append_tool_result(event.tool, event.result)

        elif event.type == "confirmation_needed":
            if agent_pane:
                agent_pane.append_confirmation_needed(event.tool)
            if team_pane and agent_name != "team":
                team_pane.append_confirmation_needed(event.tool)

        elif event.type == "error":
            if agent_pane:
                agent_pane.append_error(event.content)
            if team_pane and agent_name != "team":
                team_pane.append_error(event.content)

    def _handle_slash_command(self, command: str) -> None:
        """Handle slash commands within the TUI."""
        cmd = command.strip()
        team_pane = self.query_one(AgentTabs).get_team_pane()

        if cmd in ("/quit", "/exit", "/q"):
            self.exit()
        elif cmd == "/help":
            if team_pane:
                team_pane.log.write(
                    "[bold]Commands:[/bold]\n"
                    "  /help       Show this help\n"
                    "  /status     Show team status\n"
                    "  /settings   Open settings\n"
                    "  /quit       Exit\n"
                    "\n[bold]Shortcuts:[/bold]\n"
                    "  ctrl+b      Toggle sidebar\n"
                    "  ctrl+t      Toggle tool panel\n"
                    "  ctrl+p      Open settings\n"
                    "  ctrl+q      Quit\n"
                    "  escape      Focus input\n"
                )
        elif cmd == "/status":
            sidebar = self.query_one(StatusSidebar)
            if not sidebar.display:
                sidebar.display = True
        elif cmd == "/settings":
            self.action_open_settings()
        else:
            if team_pane:
                team_pane.append_error(f"Unknown command: {cmd}")

    def action_toggle_sidebar(self) -> None:
        """Toggle the status sidebar visibility."""
        sidebar = self.query_one(StatusSidebar)
        sidebar.display = not sidebar.display
        self.config.ui.sidebar_visible = sidebar.display

    def action_toggle_tools(self) -> None:
        """Toggle the tool output panel visibility."""
        tool_panel = self.query_one(ToolOutputPanel)
        tool_panel.display = not tool_panel.display
        self.config.ui.tool_panel_visible = tool_panel.display

    def action_open_settings(self) -> None:
        """Open the settings screen."""
        from cadre.tui.screens.settings_screen import SettingsScreen

        themes = self.theme_registry.list_themes()
        self.push_screen(
            SettingsScreen(ui_config=self.config.ui, available_themes=themes),
            callback=self._on_settings_result,
        )

    def _on_settings_result(self, result: str | None) -> None:
        """Handle settings screen result."""
        if result is not None:
            self.config.ui.theme = result
            # Reload CSS with new theme
            new_css_path = self.theme_registry.get_css_path(result)
            self.css_path = [new_css_path]
            self.stylesheet.read(new_css_path)
            self.stylesheet.reparse()
            self.refresh_css()

    def action_focus_input(self) -> None:
        """Focus the input bar."""
        self.query_one(InputBar).focus_input()

    def action_switch_tab(self, agent_name: str) -> None:
        """Switch to a specific agent tab by name."""
        self.query_one(AgentTabs).switch_to_agent(agent_name)

    def action_switch_tab_index(self, index: int) -> None:
        """Switch to an agent tab by index (0-based, among enabled agents)."""
        agent_tabs = self.query_one(AgentTabs)
        if 0 <= index < len(agent_tabs.agent_names):
            agent_tabs.switch_to_agent(agent_tabs.agent_names[index])

    def on_unmount(self) -> None:
        """Clean up and persist config on exit."""
        import contextlib

        with contextlib.suppress(Exception):
            self.config.save()
        self.team.shutdown()
