"""Agents screen — view and edit agent configuration."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from cadre.config import AUTO_MODEL, AgentConfig, CadreConfig
from cadre.keys import check_key_for_model

# Short descriptions for preset agent roles
AGENT_DESCRIPTIONS: dict[str, str] = {
    "lead": "Coordinates the team, routes tasks, never writes code",
    "architect": "Designs data models, classifies risk, read-only",
    "engineer": "Writes SQL/dbt code, implements designs",
    "qa": "Reviews code quality, validates designs, read-only",
    "solo": "All-in-one agent for solo mode",
}

# Recommended models per role — shown as suggestions in the detail editor
RECOMMENDED_MODELS: dict[str, list[tuple[str, str]]] = {
    "lead": [
        ("anthropic/claude-sonnet-4-6", "Recommended — fast, good at coordination"),
        ("anthropic/claude-opus-4-6", "Premium — best reasoning"),
        ("openai/gpt-4o", "OpenAI alternative"),
        ("deepseek/deepseek-chat", "Budget option"),
    ],
    "architect": [
        ("anthropic/claude-sonnet-4-6", "Recommended — strong at design"),
        ("anthropic/claude-opus-4-6", "Premium — deepest analysis"),
        ("openai/o3", "OpenAI reasoning model"),
        ("deepseek/deepseek-chat", "Budget option"),
    ],
    "engineer": [
        ("anthropic/claude-sonnet-4-6", "Recommended — best for code generation"),
        ("openai/gpt-4o", "OpenAI alternative"),
        ("deepseek/deepseek-coder", "Budget — strong at code"),
        ("anthropic/claude-haiku-4-5-20251001", "Fast and cheap"),
    ],
    "qa": [
        ("anthropic/claude-sonnet-4-6", "Recommended — thorough reviews"),
        ("openai/gpt-4o", "OpenAI alternative"),
        ("anthropic/claude-haiku-4-5-20251001", "Fast and cheap"),
        ("deepseek/deepseek-chat", "Budget option"),
    ],
    "solo": [
        ("anthropic/claude-sonnet-4-6", "Recommended — good all-rounder"),
        ("anthropic/claude-opus-4-6", "Premium — best quality"),
        ("openai/gpt-4o", "OpenAI alternative"),
        ("deepseek/deepseek-chat", "Budget option"),
    ],
}


class AgentsScreen(ModalScreen[CadreConfig | None]):
    """Modal screen for viewing and editing agent configuration."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "back", "Back"),
    ]

    DEFAULT_CSS = """
    AgentsScreen {
        align: center middle;
    }

    #agents-container {
        width: 72;
        height: 38;
        background: #1e1e2e;
        border: thick #313244;
        padding: 1 2;
    }

    #agents-title {
        text-style: bold;
        color: #89b4fa;
        margin-bottom: 1;
    }

    #agent-list {
        height: 100%;
    }

    /* Detail view */
    #detail-container {
        height: 100%;
    }

    .detail-header {
        text-style: bold;
        color: #89b4fa;
        margin-bottom: 1;
    }

    .field-label {
        color: #6c7086;
    }

    .role-desc {
        color: #a6adc8;
        margin-bottom: 1;
    }

    Input {
        margin-bottom: 1;
    }

    TextArea {
        height: 6;
        margin-bottom: 1;
    }

    #model-suggestions {
        height: 5;
        margin-bottom: 1;
    }

    #list-button-row {
        height: 3;
        align: right middle;
        margin-top: 1;
        dock: bottom;
    }

    #detail-button-row {
        height: 3;
        align: right middle;
        margin-top: 1;
        dock: bottom;
    }

    Button {
        margin-left: 1;
    }
    """

    def __init__(self, config: CadreConfig, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        self._editing_agent: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="agents-container"):
            yield Label("Agents", id="agents-title")

            # List view (shown by default)
            with Vertical(id="list-view"):
                yield OptionList(id="agent-list")
                with Horizontal(id="list-button-row"):
                    yield Button("Close", variant="default", id="close-btn")

            # Detail view (hidden by default)
            with Vertical(id="detail-view"):
                yield Static("", id="detail-header", classes="detail-header")
                yield Static("", id="role-desc", classes="role-desc")

                yield Label("Model", classes="field-label")
                yield Input(id="agent-model")
                yield Label("Suggestions (select to apply)", classes="field-label")
                yield OptionList(id="model-suggestions")

                yield Label("Enabled", classes="field-label")
                yield Checkbox("Agent is active", value=True, id="agent-enabled")

                yield Label("Extra context", classes="field-label")
                yield TextArea(id="agent-context")

                with Horizontal(id="detail-button-row"):
                    yield Button("Back", variant="default", id="back-btn")
                    yield Button("Save", variant="primary", id="save-btn")

    def on_mount(self) -> None:
        """Populate the agent list and hide detail view."""
        self.query_one("#detail-view").display = False
        self._refresh_agent_list()

    def _refresh_agent_list(self) -> None:
        """Rebuild the agent list from current config."""
        agent_list = self.query_one("#agent-list", OptionList)
        agent_list.clear_options()
        for name, agent_cfg in self.config.team.agents.items():
            status = "on" if agent_cfg.enabled else "off"
            if not agent_cfg.model or agent_cfg.model == AUTO_MODEL:
                resolved = self.config.get_model(name)
                model_display = f"{resolved} (auto)"
            else:
                model_display = agent_cfg.model
            label = f"{name:12s} {model_display:36s} [{status}]"
            agent_list.add_option(Option(label, id=name))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle selection in both agent list and model suggestions."""
        if event.option_list.id == "agent-list":
            agent_name = str(event.option.id)
            self._show_detail(agent_name)
        elif event.option_list.id == "model-suggestions":
            # Apply the selected model to the input field
            model_id = str(event.option.id)
            if model_id == AUTO_MODEL:
                self.query_one("#agent-model", Input).value = ""
            else:
                self.query_one("#agent-model", Input).value = model_id

    def _show_detail(self, agent_name: str) -> None:
        """Switch to the detail editor for an agent."""
        self._editing_agent = agent_name
        agent_cfg = self.config.team.agents.get(agent_name, AgentConfig())
        desc = AGENT_DESCRIPTIONS.get(agent_name, "Custom agent")

        self.query_one("#detail-header", Static).update(agent_name.capitalize())
        self.query_one("#role-desc", Static).update(desc)
        model_value = agent_cfg.model if agent_cfg.model and agent_cfg.model != AUTO_MODEL else ""
        self.query_one("#agent-model", Input).value = model_value
        self.query_one("#agent-enabled", Checkbox).value = agent_cfg.enabled
        self.query_one("#agent-context", TextArea).text = agent_cfg.extra_context

        # Populate model suggestions — auto first, then role-based (filtered by available keys)
        suggestions = self.query_one("#model-suggestions", OptionList)
        suggestions.clear_options()
        resolved = self.config.get_model(agent_name)
        suggestions.add_option(Option(f"{'auto':35s} Auto-select ({resolved})", id=AUTO_MODEL))
        recommended = RECOMMENDED_MODELS.get(agent_name, RECOMMENDED_MODELS["solo"])
        for model_id, hint in recommended:
            if check_key_for_model(model_id):
                suggestions.add_option(Option(f"{model_id:35s} {hint}", id=model_id))

        self.query_one("#list-view").display = False
        self.query_one("#detail-view").display = True

    def _show_list(self) -> None:
        """Switch back to the list view."""
        self._editing_agent = None
        self._refresh_agent_list()
        self.query_one("#list-view").display = True
        self.query_one("#detail-view").display = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.dismiss(self.config)
        elif event.button.id == "back-btn":
            self._show_list()
        elif event.button.id == "save-btn":
            self._save_agent()

    def action_back(self) -> None:
        if self._editing_agent:
            self._show_list()
        else:
            self.dismiss(self.config)

    def _save_agent(self) -> None:
        """Save the current agent detail edits."""
        if not self._editing_agent:
            return

        agent_name = self._editing_agent
        model = self.query_one("#agent-model", Input).value.strip()
        enabled = self.query_one("#agent-enabled", Checkbox).value
        extra_context = self.query_one("#agent-context", TextArea).text

        # Empty or "auto" means auto-select at runtime
        if not model or model == AUTO_MODEL:
            model = AUTO_MODEL

        self.config.team.agents[agent_name] = AgentConfig(
            model=model,
            enabled=enabled,
            extra_context=extra_context,
        )
        self.config.save()
        self._show_list()
