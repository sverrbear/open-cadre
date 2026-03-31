"""Shared test fixtures."""

from __future__ import annotations

import pytest

from cadre.config import (
    AgentConfig,
    CadreConfig,
    ProjectConfig,
    ProviderConfig,
    TeamConfig,
    ToolsConfig,
    WorkflowsConfig,
)


@pytest.fixture
def sample_config() -> CadreConfig:
    """Create a sample config for testing."""
    return CadreConfig(
        project=ProjectConfig(
            name="Test Project",
            type="dbt",
            warehouse="snowflake",
            ci_platform="github_actions",
        ),
        providers={
            "anthropic": ProviderConfig(api_key="test-key"),
        },
        team=TeamConfig(
            mode="full",
            agents={
                "lead": AgentConfig(model="anthropic/claude-opus-4-6"),
                "data_architect": AgentConfig(model="anthropic/claude-sonnet-4-6"),
                "analytics_engineer": AgentConfig(model="anthropic/claude-sonnet-4-6"),
                "data_qa": AgentConfig(model="anthropic/claude-sonnet-4-6"),
            },
        ),
        tools=ToolsConfig(),
        workflows=WorkflowsConfig(),
    )


@pytest.fixture
def lead_only_config() -> CadreConfig:
    """Create a lead-only config for testing (default init state)."""
    return CadreConfig(
        project=ProjectConfig(name="Lead Only Project", type="generic"),
        providers={"anthropic": ProviderConfig(api_key="test-key")},
        team=TeamConfig(
            mode="full",
            agents={"lead": AgentConfig(model="anthropic/claude-opus-4-6")},
        ),
    )


@pytest.fixture
def solo_config() -> CadreConfig:
    """Create a solo-mode config for testing."""
    return CadreConfig(
        project=ProjectConfig(name="Solo Project", type="generic"),
        providers={"anthropic": ProviderConfig(api_key="test-key")},
        team=TeamConfig(
            mode="solo",
            agents={"solo": AgentConfig(model="anthropic/claude-sonnet-4-6")},
        ),
    )
