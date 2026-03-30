"""Auto-detect project type, warehouse, and CI platform."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class DetectionResult:
    """Result of project auto-detection."""

    project_type: str = "generic"  # dbt | generic
    project_name: str | None = None
    warehouse: str | None = None
    dbt_version: str | None = None
    ci_platform: str = "none"
    detected_providers: list[str] | None = None
    details: list[str] | None = None

    def __post_init__(self):
        if self.detected_providers is None:
            self.detected_providers = []
        if self.details is None:
            self.details = []


def detect_project(path: Path | None = None) -> DetectionResult:
    """Auto-detect project characteristics from the filesystem."""
    if path is None:
        path = Path.cwd()

    result = DetectionResult()

    # Detect dbt project
    _detect_dbt(path, result)

    # Detect CI platform
    _detect_ci(path, result)

    # Detect available LLM providers (via env vars)
    _detect_providers(result)

    return result


def _detect_dbt(path: Path, result: DetectionResult) -> None:
    """Detect dbt project and warehouse adapter."""
    dbt_project = path / "dbt_project.yml"
    if not dbt_project.exists():
        return

    result.project_type = "dbt"
    result.details.append(f"Detected: {dbt_project.name}")

    try:
        with open(dbt_project) as f:
            data = yaml.safe_load(f) or {}
        result.project_name = data.get("name")
        result.dbt_version = data.get("require-dbt-version") or data.get("version")
        if result.project_name:
            result.details.append(f"  dbt project: {result.project_name}")
    except Exception:
        pass

    # Detect warehouse from profiles.yml or packages
    _detect_warehouse(path, result)


def _detect_warehouse(path: Path, result: DetectionResult) -> None:
    """Detect warehouse from dbt profiles or adapter packages."""
    # Check packages.yml for adapter
    adapter_map = {
        "dbt-snowflake": "snowflake",
        "dbt-bigquery": "bigquery",
        "dbt-redshift": "redshift",
        "dbt-postgres": "postgres",
        "dbt-databricks": "databricks",
        "dbt-duckdb": "duckdb",
    }

    # Check requirements.txt, setup.cfg, pyproject.toml for adapter
    for req_file in ["requirements.txt", "packages.txt"]:
        req_path = path / req_file
        if req_path.exists():
            try:
                content = req_path.read_text()
                for adapter, warehouse in adapter_map.items():
                    if adapter in content:
                        result.warehouse = warehouse
                        result.details.append(f"  Detected {adapter} adapter → {warehouse}")
                        return
            except Exception:
                pass

    # Check profiles.yml
    profiles_path = path / "profiles.yml"
    if not profiles_path.exists():
        profiles_path = Path.home() / ".dbt" / "profiles.yml"

    if profiles_path.exists():
        try:
            with open(profiles_path) as f:
                profiles = yaml.safe_load(f) or {}
            for profile_name, profile in profiles.items():
                if isinstance(profile, dict):
                    outputs = profile.get("outputs", {})
                    for output_name, output in outputs.items():
                        if isinstance(output, dict) and "type" in output:
                            result.warehouse = output["type"]
                            result.details.append(f"  Detected warehouse: {result.warehouse} (from profiles.yml)")
                            return
        except Exception:
            pass


def _detect_ci(path: Path, result: DetectionResult) -> None:
    """Detect CI platform."""
    if (path / ".github" / "workflows").exists():
        result.ci_platform = "github_actions"
        result.details.append("Detected: .github/workflows/ → GitHub Actions")
    elif (path / ".gitlab-ci.yml").exists():
        result.ci_platform = "gitlab_ci"
        result.details.append("Detected: .gitlab-ci.yml → GitLab CI")


def _detect_providers(result: DetectionResult) -> None:
    """Detect available LLM providers from environment variables."""
    import os

    provider_env_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }

    for provider, env_var in provider_env_map.items():
        if os.environ.get(env_var):
            result.detected_providers.append(provider)
            result.details.append(f"Detected: {env_var} → {provider}")
