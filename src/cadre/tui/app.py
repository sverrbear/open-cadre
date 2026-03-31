"""Main Textual application for OpenCadre — Claude Code team management frontend."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import ClassVar

from textual.app import App
from textual.binding import Binding

from cadre.agents.manager import check_claude_cli, list_agents
from cadre.config import CadreConfig
from cadre.tui.screens.main_screen import MainScreen
from cadre.tui.themes.registry import ThemeRegistry


class CadreTUI(App):
    """OpenCadre — Claude Code team management frontend."""

    TITLE = "OpenCadre"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+b", "toggle_sidebar", "Toggle sidebar", show=True),
        Binding("ctrl+p", "open_settings", "Settings", show=True),
        Binding("escape", "focus_input", "Focus input", show=False),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(self, config: CadreConfig) -> None:
        self.config = config
        self.theme_registry = ThemeRegistry(project_path=Path.cwd())
        self.main_screen: MainScreen | None = None

        theme_name = config.ui.theme
        self._css_path = [self.theme_registry.get_css_path(theme_name)]

        super().__init__()

    @property
    def CSS_PATH(self) -> list[Path]:  # noqa: N802
        """Dynamic CSS path based on theme."""
        return self._css_path

    def _query_main(self, widget_type: type):
        """Safely query a widget from the MainScreen."""
        if self.main_screen is None:
            return None
        try:
            return self.main_screen.query_one(widget_type)
        except Exception:
            return None

    def on_mount(self) -> None:
        """Push the main screen."""
        agents = list_agents()
        self.main_screen = MainScreen(config=self.config, agents=agents)
        self.push_screen(self.main_screen)

        # Check claude CLI
        self.call_after_refresh(self._check_claude)

        # Show init hint if no agents
        if not agents:
            self.call_after_refresh(self._show_init_hint)

    def _check_claude(self) -> None:
        """Check if claude CLI is available."""
        available, version_or_error = check_claude_cli()
        log = self._get_log()
        if not log:
            return
        if available:
            log.write(f"[green]Claude Code[/green] {version_or_error}\n")
        else:
            log.write(
                f"[bold red]Claude Code not found:[/bold red] {version_or_error}\n"
                "[dim]Install: npm install -g @anthropic-ai/claude-code[/dim]\n"
            )

    def _show_init_hint(self) -> None:
        """Show hint when no agents are configured."""
        log = self._get_log()
        if log:
            log.write(
                "[bold yellow]No agents configured.[/bold yellow]\n"
                "Press [bold]I[/bold] to install a team preset, "
                "or [bold]N[/bold] to create a new agent.\n"
            )

    def _get_log(self):
        """Get the main screen's RichLog."""
        if self.main_screen is None:
            return None
        try:
            return self.main_screen.get_log()
        except Exception:
            return None

    def on_main_screen_launch_claude(self, event: MainScreen.LaunchClaude) -> None:
        """Handle launch claude request — suspend TUI and run claude."""
        cmd = ["claude"]
        if event.agent:
            cmd.extend(["--agent", event.agent])
        with self.suspend():
            subprocess.run(cmd)

    def on_main_screen_agents_changed(self, _event: MainScreen.AgentsChanged) -> None:
        """Refresh the main screen when agents change."""
        agents = list_agents()
        self.pop_screen()
        self.main_screen = MainScreen(config=self.config, agents=agents)
        self.push_screen(self.main_screen)

    def action_toggle_sidebar(self) -> None:
        """Toggle the sidebar visibility."""
        if self.main_screen:
            self.main_screen.toggle_sidebar()

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
        """Focus the input bar."""
        from cadre.tui.widgets.input_bar import InputBar

        input_bar = self._query_main(InputBar)
        if input_bar is not None:
            input_bar.focus_input()

    def on_unmount(self) -> None:
        """Persist config on exit."""
        import contextlib

        with contextlib.suppress(Exception):
            self.config.save()
