"""Tests for configuration system."""

from __future__ import annotations

import os
import tempfile

import yaml

from cadre.config import CADRE_DIR, CadreConfig, ProjectContext


def test_default_config():
    config = CadreConfig()
    assert config.project.name == "My Project"
    assert config.team.mode == "full"
    assert "lead" in config.team.agents


def test_get_model(sample_config):
    assert sample_config.get_model("lead") == "anthropic/claude-opus-4-6"
    assert sample_config.get_model("analytics_engineer") == "anthropic/claude-sonnet-4-6"
    assert "sonnet" in sample_config.get_model("unknown")  # fallback


def test_get_enabled_agents(sample_config):
    agents = sample_config.get_enabled_agents()
    assert "lead" in agents
    assert "data_architect" in agents
    assert "analytics_engineer" in agents
    assert "data_qa" in agents


def test_solo_mode_agents(solo_config):
    agents = solo_config.get_enabled_agents()
    assert agents == ["solo"]


def test_save_and_load():
    config = CadreConfig()
    with tempfile.TemporaryDirectory() as tmpdir:
        config.save(tmpdir)
        loaded = CadreConfig.load(tmpdir)
        assert loaded.project.name == config.project.name
        assert loaded.team.mode == config.team.mode


def test_save_creates_agent_files():
    config = CadreConfig()
    with tempfile.TemporaryDirectory() as tmpdir:
        config.save(tmpdir)
        agents_dir = os.path.join(tmpdir, CADRE_DIR, "agents")
        assert os.path.isdir(agents_dir)
        assert os.path.exists(os.path.join(agents_dir, "lead.yml"))


def test_load_nonexistent():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = CadreConfig.load(tmpdir)
        assert config.project.name == "My Project"  # defaults


def test_env_var_resolution():
    os.environ["TEST_CADRE_KEY"] = "resolved-key"
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cadre_dir = os.path.join(tmpdir, CADRE_DIR)
            os.makedirs(cadre_dir)
            config_path = os.path.join(cadre_dir, "config.yml")
            with open(config_path, "w") as f:
                yaml.dump(
                    {"providers": {"test": {"api_key": "${TEST_CADRE_KEY}"}}},
                    f,
                )
            config = CadreConfig.load(tmpdir)
            assert config.providers["test"].api_key == "resolved-key"
    finally:
        del os.environ["TEST_CADRE_KEY"]


def test_context_block():
    config = CadreConfig(
        context=ProjectContext(
            description="A test project",
            tech_stack=["dbt", "snowflake"],
            conventions=["Use CTEs"],
        )
    )
    block = config.get_context_block()
    assert "A test project" in block
    assert "dbt" in block
    assert "Use CTEs" in block


def test_context_save_and_load():
    config = CadreConfig(
        context=ProjectContext(
            description="Test project description",
            tech_stack=["python", "dbt"],
        )
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        config.save(tmpdir)
        loaded = CadreConfig.load(tmpdir)
        assert loaded.context.description == "Test project description"
        assert "python" in loaded.context.tech_stack


def test_config_sanitizes_raw_keys():
    """Config should never write raw API keys — always env var references."""
    from cadre.config import ProviderConfig, _config_to_dict

    config = CadreConfig(providers={"anthropic": ProviderConfig(api_key="sk-ant-raw-key-value")})
    result = _config_to_dict(config)
    # Should be sanitized to env var reference
    assert result["providers"]["anthropic"]["api_key"] == "${ANTHROPIC_API_KEY}"


def test_default_config_is_lead_only():
    """Default config should start with only the lead agent."""
    config = CadreConfig()
    assert list(config.team.agents.keys()) == ["lead"]


def test_legacy_agent_name_mapping():
    """Old agent names (architect, engineer) should be mapped to new names on load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cadre_dir = os.path.join(tmpdir, CADRE_DIR)
        os.makedirs(cadre_dir)
        agents_dir = os.path.join(cadre_dir, "agents")
        os.makedirs(agents_dir)

        # Write config
        config_path = os.path.join(cadre_dir, "config.yml")
        with open(config_path, "w") as f:
            yaml.dump({"team": {"mode": "full"}}, f)

        # Write legacy agent files
        for name in ["lead", "architect", "engineer", "qa"]:
            with open(os.path.join(agents_dir, f"{name}.yml"), "w") as f:
                yaml.dump({"model": "auto", "enabled": True}, f)

        config = CadreConfig.load(tmpdir)
        agents = config.team.agents
        assert "data_architect" in agents  # architect -> data_architect
        assert "analytics_engineer" in agents  # engineer -> analytics_engineer
        assert "architect" not in agents
        assert "engineer" not in agents
        assert "lead" in agents
        assert "qa" in agents


def test_save_agent_and_remove_agent_file():
    """Test save_agent and remove_agent_file helper methods."""
    from cadre.config import AgentConfig, TeamConfig

    config = CadreConfig(
        team=TeamConfig(
            agents={
                "lead": AgentConfig(model="auto"),
                "backend": AgentConfig(model="auto", extra_context="Backend stuff"),
            }
        )
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save just the backend agent
        config.save_agent("backend", tmpdir)
        agent_path = os.path.join(tmpdir, CADRE_DIR, "agents", "backend.yml")
        assert os.path.exists(agent_path)

        with open(agent_path) as f:
            data = yaml.safe_load(f)
        assert data["extra_context"] == "Backend stuff"

        # Remove it
        config.remove_agent_file("backend", tmpdir)
        assert not os.path.exists(agent_path)


def test_agent_extra_context_save_and_load():
    from cadre.config import AgentConfig, TeamConfig

    config = CadreConfig(
        team=TeamConfig(
            mode="solo",
            agents={"solo": AgentConfig(extra_context="This is a dbt project")},
        )
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        config.save(tmpdir)
        loaded = CadreConfig.load(tmpdir)
        assert loaded.team.agents["solo"].extra_context == "This is a dbt project"
