"""Init screen — in-TUI project setup wizard."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, OptionList, Select, Static
from textual.widgets.option_list import Option

from cadre.config import (
    CADRE_DIR,
    AgentConfig,
    CadreConfig,
    ProjectConfig,
    ProviderConfig,
    TeamConfig,
    ToolsConfig,
    WorkflowsConfig,
)
from cadre.detect import detect_project
from cadre.keys import PROVIDER_ENV_VARS, generate_env_file, key_set

STRATEGIES = {
    "balanced": {
        "description": "Opus lead, Sonnet team (~$0.28/task)",
        "agents": {
            "lead": "anthropic/claude-opus-4-6",
            "architect": "anthropic/claude-sonnet-4-6",
            "engineer": "anthropic/claude-sonnet-4-6",
            "qa": "anthropic/claude-sonnet-4-6",
            "solo": "anthropic/claude-sonnet-4-6",
        },
    },
    "quality": {
        "description": "Opus design, Sonnet code (~$0.45/task)",
        "agents": {
            "lead": "anthropic/claude-opus-4-6",
            "architect": "anthropic/claude-opus-4-6",
            "engineer": "anthropic/claude-sonnet-4-6",
            "qa": "anthropic/claude-sonnet-4-6",
            "solo": "anthropic/claude-opus-4-6",
        },
    },
    "cost": {
        "description": "Sonnet lead, Haiku team (~$0.09/task)",
        "agents": {
            "lead": "anthropic/claude-sonnet-4-6",
            "architect": "anthropic/claude-haiku-4-5-20251001",
            "engineer": "anthropic/claude-haiku-4-5-20251001",
            "qa": "anthropic/claude-haiku-4-5-20251001",
            "solo": "anthropic/claude-sonnet-4-6",
        },
    },
    "mixed": {
        "description": "Best model per provider per role",
        "agents": {
            "lead": "anthropic/claude-opus-4-6",
            "architect": "openai/o3",
            "engineer": "anthropic/claude-sonnet-4-6",
            "qa": "openai/gpt-4o",
            "solo": "anthropic/claude-sonnet-4-6",
        },
    },
    "local": {
        "description": "Ollama only, free (~$0.00/task)",
        "agents": {
            "lead": "ollama/llama3.3-70b",
            "architect": "ollama/llama3.3-70b",
            "engineer": "ollama/llama3.3-70b",
            "qa": "ollama/llama3.3-70b",
            "solo": "ollama/llama3.3-70b",
        },
    },
}


class InitScreen(Screen[CadreConfig | None]):
    """In-TUI project initialization wizard."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    InitScreen {
        align: center middle;
    }

    #init-container {
        width: 60;
        height: auto;
        max-height: 80%;
        background: #1e1e2e;
        border: thick #313244;
        padding: 1 2;
    }

    #init-title {
        text-style: bold;
        color: #89b4fa;
        text-align: center;
        margin-bottom: 1;
    }

    .field-label {
        color: #6c7086;
    }

    Input {
        margin-bottom: 1;
    }

    Select {
        margin-bottom: 1;
    }

    OptionList {
        height: 6;
        margin-bottom: 1;
    }

    .api-status {
        color: #a6e3a1;
    }

    .api-key-input {
        margin-bottom: 1;
    }

    #button-row {
        height: 3;
        align: right middle;
        margin-top: 1;
    }

    Button {
        margin-left: 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.base_path = Path.cwd()
        self.detection = detect_project(self.base_path)

    def compose(self) -> ComposeResult:
        with Vertical(id="init-container"):
            yield Label("OpenCadre Setup", id="init-title")

            # Project name
            yield Label("Project name", classes="field-label")
            default_name = self.detection.project_name or self.base_path.name
            yield Input(value=default_name, id="project-name")

            # API key — show one field if no key is set
            has_any_key = any(os.environ.get(v) for v in PROVIDER_ENV_VARS.values())
            if has_any_key:
                yield Static("[green]✓[/green] API key detected", classes="api-status")
            else:
                yield Label("Anthropic API key", classes="field-label")
                yield Input(
                    placeholder="sk-ant-...",
                    password=True,
                    id="api-key-anthropic",
                    classes="api-key-input",
                )

            # Team mode
            yield Label("Team mode", classes="field-label")
            yield Select(
                [("Full team (4 agents)", "full"), ("Solo (1 agent)", "solo")],
                value="full",
                id="team-mode",
            )

            # Strategy
            yield Label("Model strategy", classes="field-label")
            strategy_options = [
                Option(f"{name:10s} — {s['description']}", id=name)
                for name, s in STRATEGIES.items()
            ]
            yield OptionList(*strategy_options, id="strategy-list")

            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("Create Project", variant="primary", id="create-btn")

    def on_mount(self) -> None:
        """Set default strategy selection."""
        self.query_one("#strategy-list", OptionList).highlighted = 0

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "create-btn":
            self._create_project()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _create_project(self) -> None:
        """Build config and save."""
        project_name = self.query_one("#project-name", Input).value or self.base_path.name
        project_type = self.detection.project_type or "generic"
        warehouse = self.detection.warehouse or "snowflake"
        mode = self.query_one("#team-mode", Select).value or "full"

        # Get selected strategy
        strategy_list = self.query_one("#strategy-list", OptionList)
        highlighted = strategy_list.highlighted
        strategy_names = list(STRATEGIES.keys())
        strategy_name = strategy_names[highlighted] if highlighted is not None else "balanced"
        strategy = STRATEGIES[strategy_name]

        # Detect providers from env or manual input
        providers: dict[str, ProviderConfig] = {}
        entered_keys: dict[str, str] = {}
        for provider, env_var in PROVIDER_ENV_VARS.items():
            env_value = os.environ.get(env_var)
            if env_value:
                providers[provider] = ProviderConfig(api_key=f"${{{env_var}}}")

        # Check if user entered an anthropic key manually
        try:
            key_input = self.query_one("#api-key-anthropic", Input)
            manual_key = key_input.value.strip()
            if manual_key:
                entered_keys["anthropic"] = manual_key
                key_set(self.base_path, provider="anthropic", value=manual_key)
                providers["anthropic"] = ProviderConfig(
                    api_key=f"${{{PROVIDER_ENV_VARS['anthropic']}}}"
                )
        except Exception:
            pass

        if not providers:
            providers["anthropic"] = ProviderConfig(
                api_key=f"${{{PROVIDER_ENV_VARS['anthropic']}}}"
            )

        # Build agent configs
        agent_names = ["solo"] if mode == "solo" else ["lead", "architect", "engineer", "qa"]
        agents = {
            name: AgentConfig(model=strategy["agents"].get(name, "anthropic/claude-sonnet-4-6"))
            for name in agent_names
        }

        config = CadreConfig(
            project=ProjectConfig(
                name=str(project_name),
                type=str(project_type),
                warehouse=str(warehouse),
                ci_platform=self.detection.ci_platform,
            ),
            providers=providers,
            team=TeamConfig(mode=str(mode), agents=agents),
            tools=ToolsConfig(),
            workflows=WorkflowsConfig(),
        )

        config.save(self.base_path)
        generate_env_file(self.base_path, keys=entered_keys)
        _ensure_gitignored(self.base_path)

        self.dismiss(config)


def _ensure_gitignored(base_path: Path) -> None:
    """Make sure .cadre/ and cadre.env are listed in .gitignore."""
    from cadre.keys import ENV_FILE

    gitignore = base_path / ".gitignore"
    markers = [f"{CADRE_DIR}/", ENV_FILE]

    content = gitignore.read_text() if gitignore.exists() else ""
    missing = [m for m in markers if m not in content]
    if not missing:
        return

    if content and not content.endswith("\n"):
        content += "\n"
    for m in missing:
        content += f"{m}\n"
    gitignore.write_text(content)
