"""Tests for configuration system."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml

from cadre.config import CadreConfig


def test_default_config():
    config = CadreConfig()
    assert config.project.name == "My Project"
    assert config.team.mode == "full"
    assert "lead" in config.team.agents


def test_get_model(sample_config):
    assert sample_config.get_model("lead") == "anthropic/claude-opus-4-6"
    assert sample_config.get_model("engineer") == "anthropic/claude-sonnet-4-6"
    assert "sonnet" in sample_config.get_model("unknown")  # fallback


def test_get_enabled_agents(sample_config):
    agents = sample_config.get_enabled_agents()
    assert "lead" in agents
    assert "architect" in agents
    assert "engineer" in agents
    assert "qa" in agents


def test_solo_mode_agents(solo_config):
    agents = solo_config.get_enabled_agents()
    assert agents == ["solo"]


def test_save_and_load():
    config = CadreConfig()
    with tempfile.NamedTemporaryFile(suffix=".yml", delete=False, mode="w") as f:
        config.save(f.name)
        loaded = CadreConfig.load(f.name)
        assert loaded.project.name == config.project.name
        os.unlink(f.name)


def test_load_nonexistent():
    config = CadreConfig.load("nonexistent.yml")
    assert config.project.name == "My Project"  # defaults


def test_env_var_resolution():
    os.environ["TEST_CADRE_KEY"] = "resolved-key"
    try:
        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False, mode="w") as f:
            yaml.dump(
                {"providers": {"test": {"api_key": "${TEST_CADRE_KEY}"}}},
                f,
            )
        config = CadreConfig.load(f.name)
        assert config.providers["test"].api_key == "resolved-key"
        os.unlink(f.name)
    finally:
        del os.environ["TEST_CADRE_KEY"]
