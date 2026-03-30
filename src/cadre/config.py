"""Configuration system — loads and validates .cadre/ directory structure."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

CADRE_DIR = ".cadre"
CONFIG_FILE = "config.yml"
CONTEXT_FILE = "context.yml"
AGENTS_DIR = "agents"


class ProjectConfig(BaseModel):
    """Project-level configuration."""

    name: str = "My Project"
    type: str = "generic"  # dbt | generic
    warehouse: str = "snowflake"  # snowflake | bigquery | redshift | postgres
    ci_platform: str = "none"  # github_actions | gitlab_ci | none


class ProviderConfig(BaseModel):
    """Provider configuration."""

    api_key: str | None = None
    api_base: str | None = None


class AgentConfig(BaseModel):
    """Per-agent configuration — loaded from .cadre/agents/<name>.yml."""

    model: str = "anthropic/claude-sonnet-4-6"
    enabled: bool = True
    extra_context: str = ""


class TeamConfig(BaseModel):
    """Team configuration."""

    mode: str = "full"  # full | solo
    agents: dict[str, AgentConfig] = Field(
        default_factory=lambda: {
            "lead": AgentConfig(model="anthropic/claude-opus-4-6"),
            "architect": AgentConfig(model="anthropic/claude-sonnet-4-6"),
            "engineer": AgentConfig(model="anthropic/claude-sonnet-4-6"),
            "qa": AgentConfig(model="anthropic/claude-sonnet-4-6"),
        }
    )


class ToolsConfig(BaseModel):
    """Tool permission configuration."""

    shell_allow: list[str] = Field(
        default_factory=lambda: [
            "git *",
            "dbt compile*",
            "dbt ls*",
            "dbt test*",
            "sqlfluff*",
            "ruff*",
        ]
    )
    shell_deny: list[str] = Field(
        default_factory=lambda: [
            "rm -rf*",
            "dbt run --full-refresh*",
            "DROP*",
            "DELETE FROM*",
            "TRUNCATE*",
        ]
    )


class WorkflowsConfig(BaseModel):
    """Workflow configuration."""

    default: str = "design-implement-review"
    custom: dict[str, Any] = Field(default_factory=dict)


class ProjectContext(BaseModel):
    """Project context discovered by `cadre explore`."""

    description: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    conventions: list[str] = Field(default_factory=list)
    key_paths: dict[str, str] = Field(default_factory=dict)
    notes: str = ""


class UIConfig(BaseModel):
    """TUI display configuration."""

    theme: str = "dark"
    sidebar_visible: bool = True
    sidebar_width: int = 32
    tool_panel_visible: bool = True
    tool_panel_height: int = 12


class CadreConfig(BaseModel):
    """Root configuration — loaded from .cadre/ directory."""

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    team: TeamConfig = Field(default_factory=TeamConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    workflows: WorkflowsConfig = Field(default_factory=WorkflowsConfig)
    context: ProjectContext = Field(default_factory=ProjectContext)
    ui: UIConfig = Field(default_factory=UIConfig)

    def get_model(self, agent_name: str) -> str:
        """Get the model string for an agent, with fallback to solo model."""
        if self.team.mode == "solo":
            solo_config = self.team.agents.get("solo")
            if solo_config:
                return solo_config.model
        agent_config = self.team.agents.get(agent_name)
        if agent_config:
            return agent_config.model
        return "anthropic/claude-sonnet-4-6"

    def get_agent_config(self, agent_name: str) -> AgentConfig:
        """Get config for a specific agent."""
        return self.team.agents.get(agent_name, AgentConfig())

    def get_enabled_agents(self) -> list[str]:
        """Get list of enabled agent names."""
        if self.team.mode == "solo":
            return ["solo"]
        return [name for name, cfg in self.team.agents.items() if cfg.enabled]

    def get_context_block(self) -> str:
        """Build a context string from project context for injection into prompts."""
        parts = []
        if self.context.description:
            parts.append(self.context.description)
        if self.context.tech_stack:
            parts.append("Tech stack: " + ", ".join(self.context.tech_stack))
        if self.context.conventions:
            parts.append("Conventions:\n" + "\n".join(f"- {c}" for c in self.context.conventions))
        if self.context.notes:
            parts.append(self.context.notes)
        return "\n\n".join(parts)

    @classmethod
    def load(cls, base_path: str | Path | None = None) -> CadreConfig:
        """Load config from .cadre/ directory.

        Args:
            base_path: Project root containing .cadre/. Defaults to cwd.
        """
        base_path = Path(base_path) if base_path is not None else Path.cwd()

        cadre_dir = base_path / CADRE_DIR

        # Fall back to legacy cadre.yml if .cadre/ doesn't exist
        legacy_path = base_path / "cadre.yml"
        if not cadre_dir.exists() and legacy_path.exists():
            return _load_legacy(legacy_path)

        if not cadre_dir.exists():
            return cls()

        # Load main config
        config_path = cadre_dir / CONFIG_FILE
        if config_path.exists():
            with open(config_path) as f:
                raw = yaml.safe_load(f) or {}
            raw = _resolve_env_vars(raw)
            config_kwargs = _parse_raw_config(raw)
        else:
            config_kwargs = {}

        # Load agent configs from .cadre/agents/
        agents_dir = cadre_dir / AGENTS_DIR
        if agents_dir.exists():
            agents = {}
            for agent_file in sorted(agents_dir.glob("*.yml")):
                agent_name = agent_file.stem
                with open(agent_file) as f:
                    agent_raw = yaml.safe_load(f) or {}
                agents[agent_name] = AgentConfig(**agent_raw)
            if agents:
                team_kwargs = config_kwargs.get("team", TeamConfig())
                if isinstance(team_kwargs, TeamConfig):
                    team_kwargs.agents = agents
                    config_kwargs["team"] = team_kwargs
                else:
                    team_kwargs.agents = agents

        # Load project context
        context_path = cadre_dir / CONTEXT_FILE
        if context_path.exists():
            with open(context_path) as f:
                context_raw = yaml.safe_load(f) or {}
            config_kwargs["context"] = ProjectContext(**context_raw)

        return cls(**config_kwargs)

    def save(self, base_path: str | Path | None = None) -> None:
        """Save config to .cadre/ directory structure."""
        base_path = Path(base_path) if base_path is not None else Path.cwd()

        cadre_dir = base_path / CADRE_DIR
        cadre_dir.mkdir(exist_ok=True)

        # Save main config (without agents or context — those are separate files)
        config_data = _config_to_dict(self)
        config_path = cadre_dir / CONFIG_FILE
        with open(config_path, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

        # Save per-agent configs
        agents_dir = cadre_dir / AGENTS_DIR
        agents_dir.mkdir(exist_ok=True)
        for name, agent_cfg in self.team.agents.items():
            agent_path = agents_dir / f"{name}.yml"
            agent_data = {
                "model": agent_cfg.model,
                "enabled": agent_cfg.enabled,
            }
            if agent_cfg.extra_context:
                agent_data["extra_context"] = agent_cfg.extra_context
            with open(agent_path, "w") as f:
                yaml.dump(agent_data, f, default_flow_style=False, sort_keys=False)

        # Save context
        context_path = cadre_dir / CONTEXT_FILE
        context_data: dict[str, Any] = {}
        if self.context.description:
            context_data["description"] = self.context.description
        if self.context.tech_stack:
            context_data["tech_stack"] = self.context.tech_stack
        if self.context.conventions:
            context_data["conventions"] = self.context.conventions
        if self.context.key_paths:
            context_data["key_paths"] = self.context.key_paths
        if self.context.notes:
            context_data["notes"] = self.context.notes
        with open(context_path, "w") as f:
            if context_data:
                yaml.dump(context_data, f, default_flow_style=False, sort_keys=False)
            else:
                f.write("# Auto-populated by `cadre explore`\n")


def _resolve_env_vars(obj: Any) -> Any:
    """Recursively resolve ${VAR_NAME} references in config values."""
    if isinstance(obj, str):
        pattern = r"\$\{(\w+)\}"

        def replacer(match: re.Match) -> str:
            return os.environ.get(match.group(1), match.group(0))

        return re.sub(pattern, replacer, obj)
    elif isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


def _parse_raw_config(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse raw YAML dict into config constructor kwargs."""
    result: dict[str, Any] = {}

    if "project" in raw:
        result["project"] = ProjectConfig(**raw["project"])

    if "providers" in raw:
        result["providers"] = {
            name: ProviderConfig(**cfg) if isinstance(cfg, dict) else ProviderConfig()
            for name, cfg in raw["providers"].items()
        }

    if "team" in raw:
        team_raw = raw["team"]
        agents = {}
        for name, cfg in team_raw.get("agents", {}).items():
            if isinstance(cfg, dict):
                agents[name] = AgentConfig(**cfg)
            else:
                agents[name] = AgentConfig()
        result["team"] = TeamConfig(
            mode=team_raw.get("mode", "full"),
            agents=agents,
        )

    if "tools" in raw:
        tools_raw = raw["tools"]
        shell_raw = tools_raw.get("shell", {})
        result["tools"] = ToolsConfig(
            shell_allow=shell_raw.get("allow", ToolsConfig().shell_allow),
            shell_deny=shell_raw.get("deny", ToolsConfig().shell_deny),
        )

    if "workflows" in raw:
        wf_raw = raw["workflows"]
        result["workflows"] = WorkflowsConfig(
            default=wf_raw.get("default", "design-implement-review"),
            custom={k: v for k, v in wf_raw.items() if k != "default"},
        )

    if "ui" in raw:
        result["ui"] = UIConfig(**raw["ui"])

    return result


def _config_to_dict(config: CadreConfig) -> dict[str, Any]:
    """Convert config to a YAML-friendly dict (main config only, no agents/context)."""
    return {
        "project": {
            "name": config.project.name,
            "type": config.project.type,
            "warehouse": config.project.warehouse,
            "ci_platform": config.project.ci_platform,
        },
        "providers": {
            name: {
                k: v
                for k, v in {
                    "api_key": pcfg.api_key or f"${{{name.upper()}_API_KEY}}",
                    "api_base": pcfg.api_base,
                }.items()
                if v is not None
            }
            for name, pcfg in config.providers.items()
        }
        if config.providers
        else {"anthropic": {"api_key": "${ANTHROPIC_API_KEY}"}},
        "team": {
            "mode": config.team.mode,
        },
        "tools": {
            "shell": {
                "allow": config.tools.shell_allow,
                "deny": config.tools.shell_deny,
            },
        },
        "workflows": {
            "default": config.workflows.default,
        },
        "ui": {
            "theme": config.ui.theme,
            "sidebar_visible": config.ui.sidebar_visible,
            "sidebar_width": config.ui.sidebar_width,
            "tool_panel_visible": config.ui.tool_panel_visible,
            "tool_panel_height": config.ui.tool_panel_height,
        },
    }


def _load_legacy(path: Path) -> CadreConfig:
    """Load from legacy cadre.yml format for backward compatibility."""
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    raw = _resolve_env_vars(raw)
    return CadreConfig(**_parse_raw_config(raw))
