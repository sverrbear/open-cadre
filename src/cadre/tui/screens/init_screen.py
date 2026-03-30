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

PROVIDER_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}

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
        width: 70;
        height: auto;
        max-height: 90%;
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

    .section-label {
        text-style: bold;
        color: #cdd6f4;
        margin-top: 1;
    }

    .field-label {
        color: #6c7086;
        margin-top: 1;
    }

    .detected-info {
        color: #a6e3a1;
        margin-bottom: 1;
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

    .api-missing {
        color: #6c7086;
    }

    .api-warning {
        color: #f9e2af;
        text-style: bold;
        margin-bottom: 1;
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

            # Detection info
            if self.detection.details:
                yield Static(
                    "[dim]" + " | ".join(self.detection.details) + "[/dim]",
                    classes="detected-info",
                )

            # Project section
            yield Label("Project", classes="section-label")

            yield Label("Name", classes="field-label")
            default_name = self.detection.project_name or self.base_path.name
            yield Input(value=default_name, id="project-name")

            yield Label("Type", classes="field-label")
            detected_type = self.detection.project_type or "generic"
            yield Select(
                [(t, t) for t in ["dbt", "generic"]],
                value=detected_type,
                id="project-type",
            )

            yield Label("Warehouse", classes="field-label")
            detected_wh = self.detection.warehouse or "snowflake"
            yield Select(
                [
                    (w, w)
                    for w in [
                        "snowflake",
                        "bigquery",
                        "redshift",
                        "postgres",
                        "databricks",
                        "duckdb",
                    ]
                ],
                value=detected_wh,
                id="warehouse",
            )

            # API Keys section
            yield Label("API Keys", classes="section-label")
            any_key_set = any(os.environ.get(v) for v in PROVIDER_ENV_VARS.values())
            if not any_key_set:
                yield Static(
                    "⚠ No API keys found in environment. Enter a key below or set env vars.",
                    classes="api-warning",
                )
            for provider, env_var in PROVIDER_ENV_VARS.items():
                env_value = os.environ.get(env_var)
                if env_value:
                    masked = env_value[:4] + "..." + env_value[-4:]
                    yield Static(
                        f"  [green]✓[/green] {provider}: {masked} (from ${env_var})",
                        classes="api-status",
                    )
                else:
                    yield Static(
                        f"  {provider} (${env_var}):",
                        classes="api-missing",
                    )
                    yield Input(
                        placeholder=f"Paste {provider} API key (optional)",
                        password=True,
                        id=f"api-key-{provider}",
                        classes="api-key-input",
                    )

            # Team section
            yield Label("Team", classes="section-label")

            yield Label("Mode", classes="field-label")
            yield Select(
                [("Full team (4 agents)", "full"), ("Solo (1 agent)", "solo")],
                value="full",
                id="team-mode",
            )

            yield Label("Model Strategy", classes="field-label")
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
        project_type = self.query_one("#project-type", Select).value or "generic"
        warehouse = self.query_one("#warehouse", Select).value or "snowflake"
        mode = self.query_one("#team-mode", Select).value or "full"

        # Get selected strategy
        strategy_list = self.query_one("#strategy-list", OptionList)
        highlighted = strategy_list.highlighted
        strategy_names = list(STRATEGIES.keys())
        strategy_name = strategy_names[highlighted] if highlighted is not None else "balanced"
        strategy = STRATEGIES[strategy_name]

        # Detect providers from env or manual input
        providers: dict[str, ProviderConfig] = {}
        for provider, env_var in PROVIDER_ENV_VARS.items():
            env_value = os.environ.get(env_var)
            if env_value:
                providers[provider] = ProviderConfig(api_key=f"${{{env_var}}}")
            else:
                # Check if user entered a key manually
                try:
                    key_input = self.query_one(f"#api-key-{provider}", Input)
                    manual_key = key_input.value.strip()
                    if manual_key:
                        # Set in current process env so it's available immediately
                        os.environ[env_var] = manual_key
                        providers[provider] = ProviderConfig(api_key=f"${{{env_var}}}")
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
        _ensure_gitignored(self.base_path)

        self.dismiss(config)


def _ensure_gitignored(base_path: Path) -> None:
    """Make sure .cadre/ is listed in .gitignore."""
    gitignore = base_path / ".gitignore"
    marker = f"{CADRE_DIR}/"

    if gitignore.exists():
        content = gitignore.read_text()
        if marker in content:
            return
        if not content.endswith("\n"):
            content += "\n"
        content += f"{marker}\n"
        gitignore.write_text(content)
    else:
        gitignore.write_text(f"{marker}\n")
