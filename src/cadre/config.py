"""Configuration system — loads and validates cadre.yml."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


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
    """Per-agent configuration."""

    model: str = "anthropic/claude-sonnet-4-6"
    enabled: bool = True


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


class CadreConfig(BaseModel):
    """Root configuration — loaded from cadre.yml."""

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    team: TeamConfig = Field(default_factory=TeamConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    workflows: WorkflowsConfig = Field(default_factory=WorkflowsConfig)

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

    def get_enabled_agents(self) -> list[str]:
        """Get list of enabled agent names."""
        if self.team.mode == "solo":
            return ["solo"]
        return [name for name, cfg in self.team.agents.items() if cfg.enabled]

    @classmethod
    def load(cls, path: str | Path | None = None) -> CadreConfig:
        """Load config from a cadre.yml file."""
        path = Path("cadre.yml") if path is None else Path(path)

        if not path.exists():
            return cls()

        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        # Resolve environment variable references like ${VAR_NAME}
        raw = _resolve_env_vars(raw)

        return cls(**_parse_raw_config(raw))

    def save(self, path: str | Path | None = None) -> None:
        """Save config to a cadre.yml file."""
        path = Path("cadre.yml") if path is None else Path(path)

        data = _config_to_dict(self)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)


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

    return result


def _config_to_dict(config: CadreConfig) -> dict[str, Any]:
    """Convert config to a YAML-friendly dict."""
    return {
        "project": {
            "name": config.project.name,
            "type": config.project.type,
            "warehouse": config.project.warehouse,
            "ci_platform": config.project.ci_platform,
        },
        "providers": {
            name: {"api_key": f"${{{name.upper()}_API_KEY}}"} for name in config.providers
        }
        if config.providers
        else {
            "anthropic": {"api_key": "${ANTHROPIC_API_KEY}"},
        },
        "team": {
            "mode": config.team.mode,
            "agents": {
                name: {"model": cfg.model, "enabled": cfg.enabled}
                for name, cfg in config.team.agents.items()
            },
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
    }
