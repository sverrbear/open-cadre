"""Settings screen — full configuration editor."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    OptionList,
    Select,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option

from cadre.config import CadreConfig


class SettingsScreen(ModalScreen[CadreConfig | None]):
    """Modal screen for TUI settings — theme, team, tools, and UI configuration."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-container {
        width: 72;
        height: 36;
        background: #1e1e2e;
        border: thick #313244;
        padding: 1 2;
    }

    #settings-title {
        text-style: bold;
        color: #89b4fa;
        margin-bottom: 1;
    }

    .section-label {
        text-style: bold;
        color: #cdd6f4;
        margin-top: 1;
    }

    .field-label {
        color: #6c7086;
        margin-top: 1;
    }

    .field-hint {
        color: #585b70;
    }

    Input {
        margin-bottom: 1;
    }

    Select {
        margin-bottom: 1;
    }

    Checkbox {
        margin-bottom: 1;
    }

    OptionList {
        height: 6;
        background: #313244;
        border: tall #45475a;
    }

    .agent-row {
        height: 3;
        margin-bottom: 1;
    }

    .agent-row Label {
        width: 12;
        padding-top: 1;
    }

    .agent-row Input {
        width: 1fr;
    }

    .agent-row Checkbox {
        width: 12;
    }

    #button-row {
        height: 3;
        align: right middle;
        dock: bottom;
    }

    Button {
        margin-left: 1;
    }

    TabbedContent {
        height: 1fr;
    }
    """

    def __init__(
        self,
        config: CadreConfig,
        available_themes: list[str],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.available_themes = available_themes

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("Settings", id="settings-title")

            with TabbedContent():
                # Theme tab
                with TabPane("Theme", id="tab-theme"):
                    options = [Option(name, id=name) for name in self.available_themes]
                    yield OptionList(*options, id="theme-list")

                # Team tab
                with TabPane("Team", id="tab-team"):
                    yield Label("Mode", classes="field-label")
                    yield Select(
                        [
                            ("Full team (4 agents)", "full"),
                            ("Solo (1 agent)", "solo"),
                        ],
                        value=self.config.team.mode,
                        id="team-mode",
                    )

                    yield Label("Agent Models", classes="section-label")
                    for name, agent_cfg in self.config.team.agents.items():
                        with Horizontal(classes="agent-row"):
                            yield Label(f"  {name}")
                            yield Input(
                                value=agent_cfg.model,
                                id=f"agent-model-{name}",
                            )
                            yield Checkbox(
                                "On",
                                value=agent_cfg.enabled,
                                id=f"agent-enabled-{name}",
                            )

                # Tools tab
                with TabPane("Tools", id="tab-tools"):
                    yield Label("Shell Allow Patterns", classes="field-label")
                    yield Static(
                        "[dim]One pattern per line[/dim]",
                        classes="field-hint",
                    )
                    yield Input(
                        value=", ".join(self.config.tools.shell_allow),
                        id="shell-allow",
                    )

                    yield Label("Shell Deny Patterns", classes="field-label")
                    yield Static(
                        "[dim]One pattern per line[/dim]",
                        classes="field-hint",
                    )
                    yield Input(
                        value=", ".join(self.config.tools.shell_deny),
                        id="shell-deny",
                    )

                # UI tab
                with TabPane("UI", id="tab-ui"):
                    yield Checkbox(
                        "Show sidebar",
                        value=self.config.ui.sidebar_visible,
                        id="ui-sidebar-visible",
                    )
                    yield Label("Sidebar width", classes="field-label")
                    yield Input(
                        value=str(self.config.ui.sidebar_width),
                        id="ui-sidebar-width",
                    )

                    yield Checkbox(
                        "Show tool panel",
                        value=self.config.ui.tool_panel_visible,
                        id="ui-tool-visible",
                    )
                    yield Label("Tool panel height", classes="field-label")
                    yield Input(
                        value=str(self.config.ui.tool_panel_height),
                        id="ui-tool-height",
                    )

            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("Apply", variant="primary", id="apply-btn")

    def on_mount(self) -> None:
        """Highlight the current theme."""
        option_list = self.query_one("#theme-list", OptionList)
        for i, name in enumerate(self.available_themes):
            if name == self.config.ui.theme:
                option_list.highlighted = i
                break

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "apply-btn":
            self._apply_and_dismiss()
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _apply_and_dismiss(self) -> None:
        """Collect all settings and dismiss with updated config."""
        # Theme
        theme_list = self.query_one("#theme-list", OptionList)
        highlighted = theme_list.highlighted
        if highlighted is not None and 0 <= highlighted < len(self.available_themes):
            self.config.ui.theme = self.available_themes[highlighted]

        # Team mode
        mode_val = self.query_one("#team-mode", Select).value
        if mode_val:
            self.config.team.mode = str(mode_val)

        # Agent models and enabled status
        for name in list(self.config.team.agents.keys()):
            try:
                model_input = self.query_one(f"#agent-model-{name}", Input)
                self.config.team.agents[name].model = model_input.value
            except Exception:
                pass
            try:
                enabled_cb = self.query_one(f"#agent-enabled-{name}", Checkbox)
                self.config.team.agents[name].enabled = enabled_cb.value
            except Exception:
                pass

        # Tools
        try:
            allow_val = self.query_one("#shell-allow", Input).value
            self.config.tools.shell_allow = [p.strip() for p in allow_val.split(",") if p.strip()]
        except Exception:
            pass
        try:
            deny_val = self.query_one("#shell-deny", Input).value
            self.config.tools.shell_deny = [p.strip() for p in deny_val.split(",") if p.strip()]
        except Exception:
            pass

        # UI
        import contextlib

        with contextlib.suppress(Exception):
            self.config.ui.sidebar_visible = self.query_one("#ui-sidebar-visible", Checkbox).value
        with contextlib.suppress(ValueError, Exception):
            width = int(self.query_one("#ui-sidebar-width", Input).value)
            self.config.ui.sidebar_width = max(16, min(80, width))
        with contextlib.suppress(Exception):
            self.config.ui.tool_panel_visible = self.query_one("#ui-tool-visible", Checkbox).value
        with contextlib.suppress(ValueError, Exception):
            height = int(self.query_one("#ui-tool-height", Input).value)
            self.config.ui.tool_panel_height = max(4, min(40, height))

        self.dismiss(self.config)
