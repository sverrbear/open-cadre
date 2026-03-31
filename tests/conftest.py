"""Shared test fixtures."""

from __future__ import annotations

import pytest

from cadre.config import CadreConfig, ProjectConfig, TeamConfig


@pytest.fixture
def sample_config() -> CadreConfig:
    """Create a sample config for testing."""
    return CadreConfig(
        project=ProjectConfig(name="Test Project"),
        team=TeamConfig(mode="full", preset="full"),
    )
