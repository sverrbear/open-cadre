"""Init screen — in-TUI project setup wizard."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from cadre.config import (
    AUTO_MODEL,
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
from cadre.keys import ENV_FILE, PROVIDER_ENV_VARS, generate_env_file


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
        width: 64;
        height: auto;
        max-height: 85%;
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
    }

    .provider-row {
        height: 3;
        margin-bottom: 0;
    }

    .provider-row Checkbox {
        width: auto;
        min-width: 16;
    }

    .api-status {
        color: #a6e3a1;
        margin-left: 2;
    }

    .api-key-input {
        margin-bottom: 0;
    }

    Input {
        margin-bottom: 1;
    }

    Select {
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

            # Provider selection
            yield Label("Providers", classes="section-label")

            for provider, env_var in PROVIDER_ENV_VARS.items():
                env_value = os.environ.get(env_var)
                with Horizontal(classes="provider-row"):
                    yield Checkbox(
                        provider.capitalize(),
                        value=bool(env_value),
                        id=f"provider-check-{provider}",
                    )
                    if env_value:
                        masked = env_value[:6] + "..." + env_value[-4:]
                        yield Static(
                            f"[green]\u2713[/green] {masked}",
                            classes="api-status",
                        )

                # Key input — only show if no key in environment
                if not env_value:
                    yield Input(
                        placeholder=f"{env_var}",
                        password=True,
                        id=f"api-key-{provider}",
                        classes="api-key-input",
                    )

            # Team mode
            yield Label("Team mode", classes="section-label")
            yield Select(
                [("Full team (4 agents)", "full"), ("Solo (1 agent)", "solo")],
                value="full",
                id="team-mode",
            )

            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("Create Project", variant="primary", id="create-btn")

    def on_mount(self) -> None:
        """Hide API key inputs for unchecked providers."""
        for provider in PROVIDER_ENV_VARS:
            self._toggle_key_visibility(provider)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Show/hide API key input when a provider checkbox is toggled."""
        checkbox_id = event.checkbox.id or ""
        if checkbox_id.startswith("provider-check-"):
            provider = checkbox_id.replace("provider-check-", "")
            self._toggle_key_visibility(provider)

    def _toggle_key_visibility(self, provider: str) -> None:
        """Show or hide the API key input for a provider."""
        try:
            key_input = self.query_one(f"#api-key-{provider}", Input)
        except Exception:
            return  # No input (key already in env)
        try:
            checkbox = self.query_one(f"#provider-check-{provider}", Checkbox)
            key_input.display = checkbox.value
        except Exception:
            pass

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

        # Collect providers and API keys
        providers: dict[str, ProviderConfig] = {}
        entered_keys: dict[str, str] = {}

        for provider, env_var in PROVIDER_ENV_VARS.items():
            try:
                checkbox = self.query_one(f"#provider-check-{provider}", Checkbox)
            except Exception:
                continue

            if not checkbox.value:
                continue

            # Check if key is already in environment — persist it to cadre.env
            env_value = os.environ.get(env_var)
            if env_value:
                entered_keys[provider] = env_value
                providers[provider] = ProviderConfig(api_key=f"${{{env_var}}}")
                continue

            # Check if user entered a key manually
            try:
                key_input = self.query_one(f"#api-key-{provider}", Input)
                manual_key = key_input.value.strip()
                if manual_key:
                    entered_keys[provider] = manual_key
                    providers[provider] = ProviderConfig(api_key=f"${{{env_var}}}")
            except Exception:
                pass

        # Fallback: if nothing selected, add anthropic placeholder
        if not providers:
            providers["anthropic"] = ProviderConfig(
                api_key=f"${{{PROVIDER_ENV_VARS['anthropic']}}}"
            )

        # Create agents in auto mode — models resolved at runtime from configured providers
        agent_names = ["solo"] if mode == "solo" else ["lead", "architect", "engineer", "qa"]
        agents = {name: AgentConfig(model=AUTO_MODEL) for name in agent_names}

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
        # Load keys into os.environ for immediate use in this session
        for provider, value in entered_keys.items():
            env_var = PROVIDER_ENV_VARS.get(provider, f"{provider.upper()}_API_KEY")
            os.environ[env_var] = value
        _ensure_gitignored(self.base_path)

        self.dismiss(config)


def _ensure_gitignored(base_path: Path) -> None:
    """Make sure .cadre/ and cadre.env are listed in .gitignore."""
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
