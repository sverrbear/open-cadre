"""Main Textual application for OpenCadre."""

from __future__ import annotations

import os
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
        self.config = config
        self.team = Team(config=config)
        self.router: MessageRouter
        self.bridge: EventBridge
        self.theme_registry = ThemeRegistry(project_path=Path.cwd())
        self.main_screen: MainScreen | None = None

        # Set CSS path based on configured theme (must be before super().__init__
        # because Textual reads CSS_PATH during App.__init__)
        theme_name = config.ui.theme
        self._css_path = [self.theme_registry.get_css_path(theme_name)]

        super().__init__()

    @property
    def CSS_PATH(self) -> list[Path]:  # noqa: N802
        """Dynamic CSS path based on theme."""
        return self._css_path

    def _query_main(self, widget_type: type):
        """Safely query a widget from the MainScreen. Returns None if not found."""
        if self.main_screen is None:
            return None
        try:
            return self.main_screen.query_one(widget_type)
        except Exception:
            return None

    def on_mount(self) -> None:
        """Set up the team and push the main screen."""
        setup_error: str | None = None
        try:
            self.team.setup()
        except Exception as e:
            from cadre.errors import classify_llm_error, format_error_for_display

            setup_error = format_error_for_display(classify_llm_error(e))

        self.router = MessageRouter(team=self.team)
        if not setup_error:
            self.team.inject_router(self.router)
        self.bridge = EventBridge(app=self, router=self.router)
        self.main_screen = MainScreen(config=self.config, team=self.team)
        self.push_screen(self.main_screen)

        # Apply initial UI config
        self.call_after_refresh(self._apply_ui_config)

        if setup_error:
            self.call_after_refresh(lambda: self._show_setup_error(setup_error))
            return

        # Check if API keys are missing and warn
        self.call_after_refresh(self._check_api_keys)

        # Hint if no project config exists
        cadre_dir = Path.cwd() / ".cadre"
        if not cadre_dir.exists():
            self.call_after_refresh(self._show_init_hint)

    def _check_api_keys(self) -> None:
        """Check if any API keys are available and warn if not."""
        from cadre.keys import PROVIDER_ENV_VARS

        has_key = any(os.environ.get(v) for v in PROVIDER_ENV_VARS.values())
        if not has_key:
            team_pane = self._get_team_pane()
            if team_pane:
                team_pane.log.write(
                    "[bold yellow]⚠ No API keys detected.[/bold yellow]\n"
                    "Run [bold]/keys set anthropic[/bold] to add your key, "
                    "or use [bold]/init[/bold] to configure your project.\n"
                )

    def _show_init_hint(self) -> None:
        """Show a hint that the project isn't configured yet."""
        team_pane = self._get_team_pane()
        if team_pane:
            team_pane.log.write(
                "[bold yellow]No project configured.[/bold yellow]\n"
                "Run [bold]/init[/bold] to set up your project.\n"
            )

    def _show_setup_error(self, error_msg: str) -> None:
        """Display a team setup error in the chat pane."""
        team_pane = self._get_team_pane()
        if team_pane:
            team_pane.append_error(error_msg)
            team_pane.log.write(
                "\n[dim]Use /keys to manage API keys, "
                "/init to reconfigure, or /help for commands.[/dim]\n"
            )

    def _apply_ui_config(self) -> None:
        """Apply UI config settings to widgets."""
        ui = self.config.ui
        sidebar = self._query_main(StatusSidebar)
        if sidebar is not None:
            sidebar.display = ui.sidebar_visible
        tool_panel = self._query_main(ToolOutputPanel)
        if tool_panel is not None:
            tool_panel.display = ui.tool_panel_visible

    def _get_team_pane(self):
        """Get the team ChatPane safely."""
        agent_tabs = self._query_main(AgentTabs)
        if agent_tabs is None:
            return None
        try:
            return agent_tabs.get_team_pane()
        except Exception:
            return None

    def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
        """Handle user input submission."""
        message = event.value

        # Handle slash commands
        if message.startswith("/"):
            self._handle_slash_command(message)
            return

        # Show user message in the appropriate pane
        agent_tabs = self._query_main(AgentTabs)
        if agent_tabs is None:
            return

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
        agent_tabs = self._query_main(AgentTabs)
        tool_panel = self._query_main(ToolOutputPanel)
        sidebar = self._query_main(StatusSidebar)

        if agent_tabs is None:
            return

        # Get the target panes
        agent_pane = agent_tabs.get_chat_pane(agent_name)
        team_pane = agent_tabs.get_team_pane()

        if event.type == "response_start":
            if agent_pane:
                agent_pane.append_agent_prefix(agent_name)
            if team_pane and agent_name != "team":
                team_pane.append_agent_prefix(agent_name)

        elif event.type == "status":
            if sidebar:
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
            if tool_panel:
                tool_panel.append_tool_call(agent_name, event.tool, event.args)
            if agent_pane:
                agent_pane.append_tool_call(event.tool, event.args)
            if team_pane and agent_name != "team":
                team_pane.append_tool_call(event.tool, event.args)

        elif event.type == "tool_result":
            if tool_panel:
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
            # Show API key status alongside API errors to help debugging
            if team_pane and any(
                kw in event.content.lower()
                for kw in ("connect", "authentication", "api key", "api_key")
            ):
                self._show_keys()

    def _handle_slash_command(self, command: str) -> None:
        """Handle slash commands within the TUI."""
        parts = command.strip().split()
        cmd = parts[0]
        team_pane = self._get_team_pane()

        if cmd in ("/quit", "/exit", "/q"):
            self.exit()
        elif cmd == "/help":
            if team_pane:
                team_pane.log.write(
                    "[bold]Commands:[/bold]\n"
                    "  /help                         Show this help\n"
                    "  /init                         Initialize/reconfigure project\n"
                    "  /agents                       View and configure agents\n"
                    "  /keys                         Show API key status\n"
                    "  /keys set <provider> <key>    Set an API key\n"
                    "  /models                       Show configured models\n"
                    "  /models set <agent> <model>   Change agent model\n"
                    "  /models list                  Show available models\n"
                    "  /status                       Show team status\n"
                    "  /settings                     Open settings (or /config)\n"
                    "  /doctor                       Check prerequisites\n"
                    "  /workflow                     Show workflows\n"
                    "  /quit                         Exit\n"
                    "\n[bold]Shortcuts:[/bold]\n"
                    "  ctrl+b      Toggle sidebar\n"
                    "  ctrl+t      Toggle tool panel\n"
                    "  ctrl+p      Open settings\n"
                    "  ctrl+q      Quit\n"
                    "  escape      Focus input\n"
                )
        elif cmd == "/init":
            self._run_init()
        elif cmd == "/keys":
            if len(parts) >= 4 and parts[1] == "set":
                self._set_key(parts[2], parts[3])
            elif len(parts) == 3 and parts[1] == "set":
                if team_pane:
                    team_pane.append_error("Usage: /keys set <provider> <key>")
            else:
                self._show_keys()
        elif cmd == "/models":
            if len(parts) >= 4 and parts[1] == "set":
                self._set_model(parts[2], parts[3])
            elif len(parts) >= 2 and parts[1] == "set":
                if team_pane:
                    team_pane.append_error("Usage: /models set <agent> <model>")
            elif len(parts) >= 2 and parts[1] == "list":
                self._show_model_list()
            else:
                self._show_models()
        elif cmd == "/status":
            sidebar = self._query_main(StatusSidebar)
            if sidebar is not None and not sidebar.display:
                sidebar.display = True
        elif cmd in ("/settings", "/config"):
            self.action_open_settings()
        elif cmd == "/agents":
            self._run_agents()
        elif cmd == "/doctor":
            self._show_doctor()
        elif cmd == "/workflow":
            self._show_workflows()
        else:
            if team_pane:
                team_pane.append_error(f"Unknown command: {cmd}")

    def _show_keys(self) -> None:
        """Show API key status in team pane."""
        team_pane = self._get_team_pane()
        if not team_pane:
            return
        from cadre.keys import PROVIDER_DASHBOARDS, PROVIDER_ENV_VARS, show_keys

        key_status = show_keys()
        lines = ["[bold]API Keys:[/bold]"]
        for provider in PROVIDER_ENV_VARS:
            masked = key_status.get(provider)
            if masked:
                lines.append(f"  [green]✓[/green] {provider:12s} {masked}")
            else:
                dashboard = PROVIDER_DASHBOARDS.get(provider, "")
                lines.append(f"  [red]✗[/red] {provider:12s} not set")
                if dashboard:
                    lines.append(f"    [dim]{dashboard}[/dim]")
        lines.append("\n[dim]Set a key: /keys set <provider> <key>[/dim]")
        team_pane.log.write("\n".join(lines) + "\n")

    def _set_key(self, provider: str, value: str) -> None:
        """Set an API key from the TUI."""
        team_pane = self._get_team_pane()
        if not team_pane:
            return
        from cadre.keys import key_set

        key_set(provider=provider, value=value)
        team_pane.log.write(f"[green]✓[/green] {provider} API key saved to cadre.env\n")

    def _show_models(self) -> None:
        """Show configured models in team pane."""
        team_pane = self._get_team_pane()
        if not team_pane:
            return
        from cadre.keys import check_key_for_model

        lines = ["[bold]Configured Models:[/bold]"]
        for name, agent_cfg in self.config.team.agents.items():
            status = "enabled" if agent_cfg.enabled else "disabled"
            has_key = check_key_for_model(agent_cfg.model)
            key_icon = "[green]✓[/green]" if has_key else "[yellow]⚠[/yellow]"
            lines.append(f"  {name:12s} {agent_cfg.model} ({status}) {key_icon}")
        lines.append(f"\n  Team mode: {self.config.team.mode}")
        lines.append("[dim]Change: /models set <agent> <model>[/dim]")
        team_pane.log.write("\n".join(lines) + "\n")

    def _set_model(self, agent_name: str, model: str) -> None:
        """Change an agent's model from the TUI."""
        team_pane = self._get_team_pane()
        if not team_pane:
            return

        if agent_name not in self.config.team.agents:
            available = ", ".join(self.config.team.agents.keys())
            team_pane.append_error(f"Agent '{agent_name}' not found. Available: {available}")
            return

        from cadre.keys import check_key_for_model, get_provider_for_model

        provider = get_provider_for_model(model)
        if provider and not check_key_for_model(model):
            team_pane.log.write(
                f"[yellow]Warning: No API key for '{provider}'. "
                f"Use /keys set {provider} <key> first.[/yellow]\n"
            )

        old_model = self.config.team.agents[agent_name].model
        self.config.team.agents[agent_name].model = model

        # Update the live agent object
        if agent_name in self.team.agents:
            self.team.agents[agent_name].model = model

        import contextlib

        with contextlib.suppress(Exception):
            self.config.save()

        team_pane.log.write(f"[green]✓[/green] {agent_name}: {old_model} → {model}\n")

    def _show_model_list(self) -> None:
        """Show available models from benchmark data."""
        team_pane = self._get_team_pane()
        if not team_pane:
            return
        from cadre.benchmarks.data import BenchmarkData

        bench = BenchmarkData()
        models = bench.get_models()
        lines = ["[bold]Available Models:[/bold]"]
        for model_id in sorted(models):
            info = models[model_id]
            cost_in = info.get("cost_input_1m", 0)
            speed = info.get("speed", "?")
            cost = "free" if cost_in == 0 else f"${cost_in}/1M in"
            lines.append(f"  {model_id:40s} {speed:8s} {cost}")
        lines.append("\n[dim]Any LiteLLM-compatible model string is accepted.[/dim]")
        team_pane.log.write("\n".join(lines) + "\n")

    def _show_doctor(self) -> None:
        """Run basic prerequisite checks and show results."""
        team_pane = self._get_team_pane()
        if not team_pane:
            return
        lines = ["[bold]Doctor — Prerequisite Check:[/bold]"]

        # Check API keys
        from cadre.keys import PROVIDER_ENV_VARS

        for provider, env_var in PROVIDER_ENV_VARS.items():
            if os.environ.get(env_var):
                lines.append(f"  [green]✓[/green] {provider} API key set (${env_var})")
            else:
                lines.append(f"  [red]✗[/red] {provider} API key missing — /keys set {provider}")

        # Check .cadre dir
        cadre_dir = Path.cwd() / ".cadre"
        if cadre_dir.exists():
            lines.append("  [green]✓[/green] .cadre/ directory found")
        else:
            lines.append("  [red]✗[/red] .cadre/ directory not found — run /init")

        team_pane.log.write("\n".join(lines) + "\n")

    def _show_workflows(self) -> None:
        """Show available workflows in team pane."""
        team_pane = self._get_team_pane()
        if not team_pane:
            return
        lines = [
            "[bold]Workflows:[/bold]",
            f"  Default: {self.config.workflows.default}",
            "",
            "  Built-in:",
            "    design-implement-review",
            "    code-review",
            "    model-creation",
        ]
        if self.config.workflows.custom:
            lines.append("  Custom:")
            for name in self.config.workflows.custom:
                lines.append(f"    {name}")
        team_pane.log.write("\n".join(lines) + "\n")

    def _run_agents(self) -> None:
        """Show the agents screen for viewing/editing agent configuration."""
        from cadre.tui.screens.agents_screen import AgentsScreen

        self.push_screen(AgentsScreen(config=self.config), callback=self._on_agents_result)

    def _on_agents_result(self, result: CadreConfig | None) -> None:
        """Handle agents screen result — reload team with updated config."""
        if result is None:
            return

        self.config = result
        self.team = Team(config=self.config)
        setup_error: str | None = None
        try:
            self.team.setup()
        except Exception as e:
            from cadre.errors import classify_llm_error, format_error_for_display

            setup_error = format_error_for_display(classify_llm_error(e))

        self.router = MessageRouter(team=self.team)
        if not setup_error:
            self.team.inject_router(self.router)
        self.bridge = EventBridge(app=self, router=self.router)
        self.pop_screen()
        self.main_screen = MainScreen(config=self.config, team=self.team)
        self.push_screen(self.main_screen)

        if setup_error:
            self.call_after_refresh(lambda: self._show_setup_error(setup_error))

    def _run_init(self) -> None:
        """Show the init screen for project setup."""
        from cadre.tui.screens.init_screen import InitScreen

        self.push_screen(InitScreen(), callback=self._on_init_result)

    def _on_init_result(self, result: CadreConfig | None) -> None:
        """Handle init screen result — reload everything with new config."""
        if result is None:
            return

        self.config = result
        # Re-setup team with new config
        self.team = Team(config=self.config)
        setup_error: str | None = None
        try:
            self.team.setup()
        except Exception as e:
            from cadre.errors import classify_llm_error, format_error_for_display

            setup_error = format_error_for_display(classify_llm_error(e))

        self.router = MessageRouter(team=self.team)
        if not setup_error:
            self.team.inject_router(self.router)
        self.bridge = EventBridge(app=self, router=self.router)
        # Refresh the main screen
        self.pop_screen()
        self.main_screen = MainScreen(config=self.config, team=self.team)
        self.push_screen(self.main_screen)

        if setup_error:
            self.call_after_refresh(lambda: self._show_setup_error(setup_error))
        else:
            self.call_after_refresh(self._show_agents_hint)

    def _show_agents_hint(self) -> None:
        """Prompt the user to configure agents after init."""
        team_pane = self._get_team_pane()
        if team_pane:
            team_pane.log.write(
                "[green]Project created![/green] "
                "Type [bold]/agents[/bold] to view and configure your team.\n"
            )

    def action_toggle_sidebar(self) -> None:
        """Toggle the status sidebar visibility."""
        sidebar = self._query_main(StatusSidebar)
        if sidebar is not None:
            sidebar.display = not sidebar.display
            self.config.ui.sidebar_visible = sidebar.display

    def action_toggle_tools(self) -> None:
        """Toggle the tool output panel visibility."""
        tool_panel = self._query_main(ToolOutputPanel)
        if tool_panel is not None:
            tool_panel.display = not tool_panel.display
            self.config.ui.tool_panel_visible = tool_panel.display

    def action_open_settings(self) -> None:
        """Open the settings screen."""
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

        # Apply theme change if needed
        if result.ui.theme != old_theme:
            new_css_path = self.theme_registry.get_css_path(result.ui.theme)
            self._css_path = [new_css_path]
            self.stylesheet.read(new_css_path)
            self.stylesheet.reparse()
            self.refresh_css()

        # Apply UI layout changes
        sidebar = self._query_main(StatusSidebar)
        if sidebar is not None:
            sidebar.display = result.ui.sidebar_visible
        tool_panel = self._query_main(ToolOutputPanel)
        if tool_panel is not None:
            tool_panel.display = result.ui.tool_panel_visible

        # Save to disk
        import contextlib

        with contextlib.suppress(Exception):
            result.save()

    def action_focus_input(self) -> None:
        """Focus the input bar."""
        input_bar = self._query_main(InputBar)
        if input_bar is not None:
            input_bar.focus_input()

    def action_switch_tab(self, agent_name: str) -> None:
        """Switch to a specific agent tab by name."""
        agent_tabs = self._query_main(AgentTabs)
        if agent_tabs is not None:
            agent_tabs.switch_to_agent(agent_name)

    def action_switch_tab_index(self, index: int) -> None:
        """Switch to an agent tab by index (0-based, among enabled agents)."""
        agent_tabs = self._query_main(AgentTabs)
        if agent_tabs is not None and 0 <= index < len(agent_tabs.agent_names):
            agent_tabs.switch_to_agent(agent_tabs.agent_names[index])

    def on_unmount(self) -> None:
        """Clean up and persist config on exit."""
        import contextlib

        with contextlib.suppress(Exception):
            self.config.save()
        self.team.shutdown()
