"""Configuration — minimal config for the Claude Code team frontend."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

CADRE_DIR = ".cadre"
CONFIG_FILE = "config.yml"


class ProjectConfig(BaseModel):
    """Project-level configuration."""

    name: str = "My Project"


class TeamConfig(BaseModel):
    """Team configuration."""

    mode: str = "full"  # full | solo | dev | review | custom
    preset: str = "full"  # which team preset was installed


class UIConfig(BaseModel):
    """TUI display configuration."""

    theme: str = "dark"
    sidebar_visible: bool = True


class CadreConfig(BaseModel):
    """Root configuration."""

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    team: TeamConfig = Field(default_factory=TeamConfig)
    ui: UIConfig = Field(default_factory=UIConfig)

    @classmethod
    def load(cls, base_path: str | Path | None = None) -> CadreConfig:
        """Load config from .cadre/config.yml."""
        base_path = Path(base_path) if base_path is not None else Path.cwd()
        config_path = base_path / CADRE_DIR / CONFIG_FILE

        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}

        kwargs: dict[str, Any] = {}
        if "project" in raw:
            kwargs["project"] = ProjectConfig(**raw["project"])
        if "team" in raw:
            kwargs["team"] = TeamConfig(**raw["team"])
        if "ui" in raw:
            kwargs["ui"] = UIConfig(**raw["ui"])

        return cls(**kwargs)

    def save(self, base_path: str | Path | None = None) -> None:
        """Save config to .cadre/config.yml."""
        base_path = Path(base_path) if base_path is not None else Path.cwd()
        cadre_dir = base_path / CADRE_DIR
        cadre_dir.mkdir(exist_ok=True)

        config_data = {
            "project": {"name": self.project.name},
            "team": {
                "mode": self.team.mode,
                "preset": self.team.preset,
            },
            "ui": {
                "theme": self.ui.theme,
                "sidebar_visible": self.ui.sidebar_visible,
            },
        }

        config_path = cadre_dir / CONFIG_FILE
        with open(config_path, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
